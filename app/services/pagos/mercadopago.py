from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.jobs.queue import enqueue_job
from app.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TASK_PROCESAR_MERCADOPAGO_WEBHOOK = "payments.process_mercadopago_webhook"


def _json_dump(data: dict | list | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False, separators=(",", ":"))


def _extract_payment_id(payload: dict) -> str | None:
    data = payload.get("data") or {}
    value = (
        data.get("id")
        or payload.get("payment_id")
        or payload.get("id")
    )
    return str(value).strip() if value not in (None, "") else None


def _extract_external_reference(payload: dict) -> str | None:
    data = payload.get("data") or {}
    metadata = payload.get("metadata") or {}
    data_metadata = data.get("metadata") or {}
    value = (
        payload.get("external_reference")
        or data.get("external_reference")
        or metadata.get("external_reference")
        or data_metadata.get("external_reference")
    )
    return str(value).strip() if value not in (None, "") else None


def _extract_status(payload: dict) -> str:
    data = payload.get("data") or {}
    value = payload.get("status") or data.get("status") or payload.get("action") or "pending"
    return str(value).strip().lower() or "pending"


def _extract_amount(payload: dict) -> float | None:
    data = payload.get("data") or {}
    for key in ("transaction_amount", "amount", "monto"):
        value = payload.get(key)
        if value is not None:
            return float(value)
        value = data.get(key)
        if value is not None:
            return float(value)
    return None


def _extract_currency(payload: dict) -> str:
    data = payload.get("data") or {}
    value = payload.get("currency_id") or data.get("currency_id") or "ARS"
    return str(value).strip().upper() or "ARS"


def _signature_parts(header_value: str | None) -> dict[str, str]:
    if not header_value:
        return {}

    parts: dict[str, str] = {}
    for chunk in header_value.split(","):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def _firma_mercadopago_valida(
    payload: dict,
    signature_header: str | None,
    request_id: str | None,
) -> bool:
    if not settings.mercadopago_webhook_secret:
        return settings.app_env != "production"

    payment_id = _extract_payment_id(payload)
    if not payment_id or not request_id:
        return False

    parts = _signature_parts(signature_header)
    ts = parts.get("ts")
    provided = parts.get("v1")
    if not ts or not provided:
        return False

    try:
        ts_value = int(ts)
    except ValueError:
        return False

    now = int(datetime.now(timezone.utc).timestamp())
    if abs(now - ts_value) > settings.mercadopago_webhook_tolerance_seconds:
        return False

    message = f"id:{payment_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(
        settings.mercadopago_webhook_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, provided)


def _serialize_intent(row) -> dict:
    return {
        "id": row.id,
        "suscripcion_id": row.suscripcion_id,
        "usuario_id": row.usuario_id,
        "proveedor": row.proveedor,
        "external_reference": row.external_reference,
        "estado": row.estado,
        "monto": float(row.monto) if row.monto is not None else None,
        "moneda": row.moneda,
        "checkout_url": row.checkout_url,
        "payment_id": row.payment_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def crear_intento_pago(
    db: Session,
    usuario_id: int,
    suscripcion_id: int,
    proveedor: str = "mercadopago",
):
    suscripcion = db.execute(text("""
        SELECT s.id, s.usuario_id, s.estado, s.plan_id, s.precio_pagado, p.precio_mensual
        FROM suscripciones s
        JOIN planes p ON p.id = s.plan_id
        WHERE s.id = :suscripcion_id AND s.usuario_id = :usuario_id
        LIMIT 1
    """), {
        "suscripcion_id": suscripcion_id,
        "usuario_id": usuario_id,
    }).fetchone()
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripcion no encontrada")

    if suscripcion.estado != "pendiente_pago":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden iniciar pagos para suscripciones pendientes de pago",
        )

    monto = float(suscripcion.precio_mensual or 0)
    if monto <= 0:
        raise HTTPException(status_code=400, detail="La suscripcion no tiene un monto valido para cobrar")

    monto_actualizado = False
    if float(suscripcion.precio_pagado or 0) != monto:
        db.execute(
            text(
                """
                UPDATE suscripciones
                SET precio_pagado = :monto
                WHERE id = :suscripcion_id
                """
            ),
            {"monto": monto, "suscripcion_id": suscripcion.id},
        )
        monto_actualizado = True

    existente = db.execute(text("""
        SELECT id, suscripcion_id, usuario_id, proveedor, external_reference, estado, monto,
               moneda, checkout_url, payment_id, created_at, updated_at
        FROM intentos_pago
        WHERE suscripcion_id = :suscripcion_id
          AND proveedor = :proveedor
          AND estado IN ('created', 'pending')
        ORDER BY created_at DESC
        LIMIT 1
    """), {
        "suscripcion_id": suscripcion_id,
        "proveedor": proveedor,
    }).fetchone()
    if existente:
        if float(existente.monto or 0) != monto:
            existente = db.execute(
                text(
                    """
                    UPDATE intentos_pago
                    SET monto = :monto,
                        updated_at = NOW()
                    WHERE id = :id
                    RETURNING id, suscripcion_id, usuario_id, proveedor, external_reference, estado, monto,
                              moneda, checkout_url, payment_id, created_at, updated_at
                    """
                ),
                {"id": existente.id, "monto": monto},
            ).fetchone()
            monto_actualizado = True
        if monto_actualizado:
            db.commit()
        return _serialize_intent(existente)

    external_reference = uuid4().hex
    metadata = {
        "suscripcion_id": suscripcion.id,
        "usuario_id": suscripcion.usuario_id,
        "plan_id": suscripcion.plan_id,
    }
    intento = db.execute(text("""
        INSERT INTO intentos_pago (
            suscripcion_id,
            usuario_id,
            proveedor,
            external_reference,
            estado,
            monto,
            moneda,
            metadata,
            created_at,
            updated_at
        )
        VALUES (
            :suscripcion_id,
            :usuario_id,
            :proveedor,
            :external_reference,
            'pending',
            :monto,
            :moneda,
            CAST(:metadata AS JSONB),
            NOW(),
            NOW()
        )
        RETURNING id, suscripcion_id, usuario_id, proveedor, external_reference, estado, monto,
                  moneda, checkout_url, payment_id, created_at, updated_at
    """), {
        "suscripcion_id": suscripcion.id,
        "usuario_id": suscripcion.usuario_id,
        "proveedor": proveedor,
        "external_reference": external_reference,
        "monto": monto,
        "moneda": "ARS",
        "metadata": _json_dump(metadata),
    }).fetchone()
    db.commit()
    return _serialize_intent(intento)


def estado_pago_suscripcion(
    db: Session,
    usuario_id: int,
    suscripcion_id: int,
):
    suscripcion = db.execute(text("""
        SELECT id, estado
        FROM suscripciones
        WHERE id = :suscripcion_id AND usuario_id = :usuario_id
        LIMIT 1
    """), {
        "suscripcion_id": suscripcion_id,
        "usuario_id": usuario_id,
    }).fetchone()
    if not suscripcion:
        raise HTTPException(status_code=404, detail="Suscripcion no encontrada")

    intento = db.execute(text("""
        SELECT id, suscripcion_id, usuario_id, proveedor, external_reference, estado, monto,
               moneda, checkout_url, payment_id, created_at, updated_at
        FROM intentos_pago
        WHERE suscripcion_id = :suscripcion_id
        ORDER BY created_at DESC
        LIMIT 1
    """), {"suscripcion_id": suscripcion_id}).fetchone()

    pago_procesado = db.execute(text("""
        SELECT id, proveedor, payment_id, estado, suscripcion_id, pago_id, monto, moneda, processed_at
        FROM pagos_procesados
        WHERE suscripcion_id = :suscripcion_id
        ORDER BY processed_at DESC NULLS LAST, created_at DESC
        LIMIT 1
    """), {"suscripcion_id": suscripcion_id}).fetchone()

    pago = None
    if pago_procesado and pago_procesado.pago_id:
        pago = db.execute(text("""
            SELECT id, monto, moneda, pasarela, estado, tipo, fecha_aprobacion, created_at
            FROM pagos
            WHERE id = :id
            LIMIT 1
        """), {"id": pago_procesado.pago_id}).fetchone()

    return {
        "suscripcion_id": suscripcion.id,
        "estado_suscripcion": suscripcion.estado,
        "intento": _serialize_intent(intento) if intento else None,
        "pago_procesado": {
            "id": pago_procesado.id,
            "proveedor": pago_procesado.proveedor,
            "payment_id": pago_procesado.payment_id,
            "estado": pago_procesado.estado,
            "suscripcion_id": pago_procesado.suscripcion_id,
            "pago_id": pago_procesado.pago_id,
            "monto": float(pago_procesado.monto) if pago_procesado.monto is not None else None,
            "moneda": pago_procesado.moneda,
            "processed_at": pago_procesado.processed_at.isoformat() if pago_procesado.processed_at else None,
        } if pago_procesado else None,
        "pago": {
            "id": pago.id,
            "monto": float(pago.monto) if pago.monto is not None else None,
            "moneda": pago.moneda,
            "pasarela": pago.pasarela,
            "estado": pago.estado,
            "tipo": pago.tipo,
            "fecha_aprobacion": pago.fecha_aprobacion.isoformat() if pago.fecha_aprobacion else None,
            "created_at": pago.created_at.isoformat() if pago.created_at else None,
        } if pago else None,
    }


async def registrar_webhook_mercadopago(
    db: Session,
    request: Request,
    signature_header: str | None,
    request_id: str | None,
):
    payload = await request.json()
    firma_valida = _firma_mercadopago_valida(payload, signature_header, request_id)
    webhook = db.execute(text("""
        INSERT INTO webhooks_recibidos (
            proveedor,
            event_id,
            payment_id,
            topic,
            firma_valida,
            payload,
            headers,
            created_at
        )
        VALUES (
            'mercadopago',
            :event_id,
            :payment_id,
            :topic,
            :firma_valida,
            CAST(:payload AS JSONB),
            CAST(:headers AS JSONB),
            NOW()
        )
        RETURNING id
    """), {
        "event_id": str(payload.get("id")) if payload.get("id") is not None else None,
        "payment_id": _extract_payment_id(payload),
        "topic": str(payload.get("type") or payload.get("topic") or "unknown"),
        "firma_valida": firma_valida,
        "payload": _json_dump(payload),
        "headers": _json_dump(dict(request.headers)),
    }).fetchone()
    db.commit()
    return webhook.id, firma_valida


def _procesar_webhook_background(webhook_id: int) -> None:
    with SessionLocal() as db:
        procesar_webhook_mercadopago(db, webhook_id)


def despachar_procesamiento_webhook_mercadopago(
    background_tasks: BackgroundTasks | None,
    webhook_id: int,
) -> bool:
    if enqueue_job(TASK_PROCESAR_MERCADOPAGO_WEBHOOK, webhook_id):
        return True

    if background_tasks is not None:
        background_tasks.add_task(_procesar_webhook_background, webhook_id)
        return False

    _procesar_webhook_background(webhook_id)
    return False


def procesar_webhook_mercadopago(
    db: Session,
    webhook_id: int,
):
    webhook = db.execute(text("""
        SELECT id, firma_valida, payload, processed_at
        FROM webhooks_recibidos
        WHERE id = :webhook_id AND proveedor = 'mercadopago'
        LIMIT 1
    """), {"webhook_id": webhook_id}).fetchone()
    if not webhook:
        raise ValueError(f"Webhook {webhook_id} no encontrado")

    if webhook.processed_at:
        return {"ok": True, "already_processed": True}

    if not webhook.firma_valida:
        db.execute(text("""
            UPDATE webhooks_recibidos
            SET processed_at = NOW(),
                last_error = :last_error
            WHERE id = :id
        """), {
            "id": webhook_id,
            "last_error": "Firma invalida o secreto no configurado",
        })
        db.commit()
        return {"ok": True, "ignored": True}

    payload = json.loads(webhook.payload or "{}")
    payment_id = _extract_payment_id(payload)
    if not payment_id:
        db.execute(text("""
            UPDATE webhooks_recibidos
            SET processed_at = NOW(),
                last_error = :last_error
            WHERE id = :id
        """), {
            "id": webhook_id,
            "last_error": "Webhook sin payment_id",
        })
        db.commit()
        return {"ok": True, "ignored": True}

    external_reference = _extract_external_reference(payload)
    status = _extract_status(payload)
    monto = _extract_amount(payload)
    moneda = _extract_currency(payload)

    intento = None
    if external_reference:
        intento = db.execute(text("""
            SELECT id, suscripcion_id, usuario_id, monto, moneda
            FROM intentos_pago
            WHERE external_reference = :external_reference
            LIMIT 1
        """), {"external_reference": external_reference}).fetchone()

    existente = db.execute(text("""
        SELECT id, pago_id, suscripcion_id
        FROM pagos_procesados
        WHERE proveedor = 'mercadopago' AND payment_id = :payment_id
        LIMIT 1
    """), {"payment_id": payment_id}).fetchone()

    if existente:
        processed_id = existente.id
        db.execute(text("""
            UPDATE pagos_procesados
            SET estado = :estado,
                suscripcion_id = COALESCE(:suscripcion_id, suscripcion_id),
                monto = :monto,
                moneda = :moneda,
                webhook_id = :webhook_id,
                raw_data = CAST(:raw_data AS JSONB),
                processed_at = NOW(),
                updated_at = NOW()
            WHERE id = :id
        """), {
            "id": processed_id,
            "estado": status,
            "suscripcion_id": intento.suscripcion_id if intento else existente.suscripcion_id,
            "monto": monto,
            "moneda": moneda,
            "webhook_id": webhook_id,
            "raw_data": _json_dump(payload),
        })
    else:
        processed_id = db.execute(text("""
            INSERT INTO pagos_procesados (
                proveedor,
                payment_id,
                estado,
                suscripcion_id,
                monto,
                moneda,
                webhook_id,
                raw_data,
                processed_at,
                created_at,
                updated_at
            )
            VALUES (
                'mercadopago',
                :payment_id,
                :estado,
                :suscripcion_id,
                :monto,
                :moneda,
                :webhook_id,
                CAST(:raw_data AS JSONB),
                NOW(),
                NOW(),
                NOW()
            )
            RETURNING id
        """), {
            "payment_id": payment_id,
            "estado": status,
            "suscripcion_id": intento.suscripcion_id if intento else None,
            "monto": monto,
            "moneda": moneda,
            "webhook_id": webhook_id,
            "raw_data": _json_dump(payload),
        }).fetchone().id

    if intento:
        db.execute(text("""
            UPDATE intentos_pago
            SET estado = :estado,
                payment_id = :payment_id,
                updated_at = NOW()
            WHERE id = :id
        """), {
            "id": intento.id,
            "estado": status,
            "payment_id": payment_id,
        })

    if status == "approved" and intento:
        pago_id = existente.pago_id if existente else None
        if not pago_id:
            pago_id = db.execute(text("""
                INSERT INTO pagos (
                    usuario_id,
                    monto,
                    moneda,
                    pasarela,
                    estado,
                    tipo,
                    fecha_aprobacion
                )
                VALUES (
                    :usuario_id,
                    :monto,
                    :moneda,
                    'mercadopago',
                    'aprobado',
                    :tipo,
                    NOW()
                )
                RETURNING id
            """), {
                "usuario_id": intento.usuario_id,
                "monto": monto if monto is not None else float(intento.monto or 0),
                "moneda": moneda or intento.moneda or "ARS",
                "tipo": f"mercadopago:{payment_id}",
            }).fetchone().id

        fecha_inicio = date.today()
        fecha_vencimiento = fecha_inicio + timedelta(days=30)
        db.execute(text("""
            UPDATE suscripciones
            SET estado = 'activa',
                fecha_inicio = COALESCE(fecha_inicio, :fecha_inicio),
                fecha_vencimiento = COALESCE(:fecha_vencimiento, fecha_vencimiento),
                precio_pagado = COALESCE(:monto, precio_pagado)
            WHERE id = :suscripcion_id
        """), {
            "suscripcion_id": intento.suscripcion_id,
            "fecha_inicio": fecha_inicio,
            "fecha_vencimiento": fecha_vencimiento,
            "monto": monto if monto is not None else float(intento.monto or 0),
        })
        db.execute(text("""
            UPDATE pagos_procesados
            SET pago_id = :pago_id,
                suscripcion_id = :suscripcion_id,
                updated_at = NOW()
            WHERE id = :id
        """), {
            "id": processed_id,
            "pago_id": pago_id,
            "suscripcion_id": intento.suscripcion_id,
        })

    db.execute(text("""
        UPDATE webhooks_recibidos
        SET processed_at = NOW(),
            last_error = NULL
        WHERE id = :id
    """), {"id": webhook_id})
    db.commit()
    return {
        "ok": True,
        "payment_id": payment_id,
        "estado": status,
        "processed_id": processed_id,
    }
