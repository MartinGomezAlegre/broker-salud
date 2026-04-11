import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.comercial.admin import BROKER_COMMISSION_SQL, DIRECT_COMMISSION_SQL
from app.services.comercial.common import COMMISSIONABLE_STATES, ensure_commercial_schema

logger = logging.getLogger(__name__)


def dashboard_comercial(db: Session, usuario_id: int):
    try:
        ensure_commercial_schema(db)
        usuario = db.execute(text("""
            SELECT id, nombre, apellido, email, rol
            FROM usuarios
            WHERE id = :id
        """), {"id": usuario_id}).fetchone()

        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if usuario.rol == "broker":
            return _dashboard_broker(db, usuario)
        if usuario.rol == "direct_seller":
            return _dashboard_direct_seller(db, usuario)
        if usuario.rol == "broker_seller":
            return _dashboard_broker_seller(db, usuario)

        raise HTTPException(status_code=403, detail="Tu usuario no pertenece al canal comercial")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en dashboard_comercial: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar el dashboard comercial")


def _dashboard_broker(db: Session, usuario):
    broker = db.execute(text(f"""
        SELECT
            b.id,
            b.nombre,
            b.contacto,
            b.comision_tipo,
            b.comision_valor,
            b.estado,
            b.fecha_alta,
            COALESCE(sellers.total_sellers, 0) AS total_sellers,
            COALESCE(sellers.active_sellers, 0) AS active_sellers,
            COALESCE(sales.ventas_asociadas, 0) AS ventas_asociadas,
            COALESCE(sales.revenue_generado, 0) AS revenue_generado,
            COALESCE(sales.comision_acumulada, 0) AS comision_acumulada,
            COALESCE(liq.total_liquidado, 0) AS total_liquidado
        FROM brokers b
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS total_sellers,
                   COUNT(*) FILTER (WHERE estado = 'activo') AS active_sellers
            FROM broker_sellers bs
            WHERE bs.broker_id = b.id
        ) sellers ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS ventas_asociadas,
                   COALESCE(SUM(s.precio_pagado), 0) AS revenue_generado,
                   COALESCE(SUM({BROKER_COMMISSION_SQL}), 0) AS comision_acumulada
            FROM suscripciones s
            JOIN broker_sellers bs ON bs.id = s.broker_seller_id
            WHERE bs.broker_id = b.id
              AND s.estado = ANY(:states)
        ) sales ON true
        LEFT JOIN LATERAL (
            SELECT COALESCE(SUM(monto), 0) AS total_liquidado
            FROM commission_liquidations cl
            WHERE cl.destinatario_tipo = 'broker'
              AND cl.destinatario_id = b.id
        ) liq ON true
        WHERE b.usuario_id = :usuario_id
           OR LOWER(COALESCE(b.contacto, '')) = LOWER(:email)
        ORDER BY CASE WHEN b.usuario_id = :usuario_id THEN 0 ELSE 1 END
        LIMIT 1
    """), {
        "usuario_id": usuario.id,
        "email": usuario.email,
        "states": list(COMMISSIONABLE_STATES),
    }).fetchone()

    if not broker:
        raise HTTPException(status_code=404, detail="No encontramos un broker asociado a tu cuenta")

    equipo = db.execute(text("""
        SELECT
            id,
            nombre,
            email,
            referral_code,
            estado,
            fecha_alta
        FROM broker_sellers
        WHERE broker_id = :broker_id
        ORDER BY fecha_alta DESC, id DESC
    """), {"broker_id": broker.id}).fetchall()

    ventas = db.execute(text(f"""
        SELECT
            s.id,
            s.referral_code,
            s.estado,
            s.precio_pagado,
            s.created_at,
            u.nombre || ' ' || u.apellido AS cliente_nombre,
            u.email AS cliente_email,
            p.nombre AS plan_nombre,
            bs.nombre AS broker_seller_nombre,
            {BROKER_COMMISSION_SQL} AS comision_generada
        FROM suscripciones s
        JOIN usuarios u ON u.id = s.usuario_id
        JOIN planes p ON p.id = s.plan_id
        JOIN broker_sellers bs ON bs.id = s.broker_seller_id
        WHERE bs.broker_id = :broker_id
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT 20
    """), {"broker_id": broker.id}).fetchall()

    liquidaciones = db.execute(text("""
        SELECT id, monto, periodo_desde, periodo_hasta, estado, notas, paid_at, created_at
        FROM commission_liquidations
        WHERE destinatario_tipo = 'broker'
          AND destinatario_id = :broker_id
        ORDER BY COALESCE(paid_at, created_at) DESC, id DESC
        LIMIT 20
    """), {"broker_id": broker.id}).fetchall()

    return {
        "rol": "broker",
        "usuario": _serialize_usuario(usuario),
        "perfil": {
            "id": broker.id,
            "nombre": broker.nombre,
            "contacto": broker.contacto,
            "estado": broker.estado,
            "fecha_alta": broker.fecha_alta.isoformat() if broker.fecha_alta else None,
        },
        "metricas": {
            "ventas_asociadas": broker.ventas_asociadas,
            "revenue_generado": float(broker.revenue_generado or 0),
            "comision_acumulada": float(broker.comision_acumulada or 0),
            "total_liquidado": float(broker.total_liquidado or 0),
            "comision_pendiente": float((broker.comision_acumulada or 0) - (broker.total_liquidado or 0)),
            "total_sellers": broker.total_sellers,
            "active_sellers": broker.active_sellers,
        },
        "equipo": [
            {
                "id": item.id,
                "nombre": item.nombre,
                "email": item.email,
                "referral_code": item.referral_code,
                "estado": item.estado,
                "fecha_alta": item.fecha_alta.isoformat() if item.fecha_alta else None,
                "link_referido": f"/?ref={item.referral_code}",
            }
            for item in equipo
        ],
        "ventas": [_serialize_sale(row, "broker") for row in ventas],
        "liquidaciones": [_serialize_liquidacion(row) for row in liquidaciones],
    }


def _dashboard_direct_seller(db: Session, usuario):
    seller = db.execute(text(f"""
        SELECT
            ds.id,
            ds.nombre,
            ds.email,
            ds.referral_code,
            ds.comision_tipo,
            ds.comision_valor,
            ds.estado,
            ds.fecha_alta,
            COALESCE(COUNT(s.id), 0) AS ventas_asociadas,
            COALESCE(SUM(s.precio_pagado), 0) AS revenue_generado,
            COALESCE(SUM({DIRECT_COMMISSION_SQL}), 0) AS comision_acumulada,
            COALESCE(liq.total_liquidado, 0) AS total_liquidado
        FROM direct_sellers ds
        LEFT JOIN suscripciones s
            ON s.direct_seller_id = ds.id
           AND s.estado = ANY(:states)
        LEFT JOIN LATERAL (
            SELECT COALESCE(SUM(monto), 0) AS total_liquidado
            FROM commission_liquidations cl
            WHERE cl.destinatario_tipo = 'direct_seller'
              AND cl.destinatario_id = ds.id
        ) liq ON true
        WHERE ds.usuario_id = :usuario_id
           OR LOWER(ds.email) = LOWER(:email)
        GROUP BY ds.id, liq.total_liquidado
        ORDER BY CASE WHEN ds.usuario_id = :usuario_id THEN 0 ELSE 1 END
        LIMIT 1
    """), {
        "usuario_id": usuario.id,
        "email": usuario.email,
        "states": list(COMMISSIONABLE_STATES),
    }).fetchone()

    if not seller:
        raise HTTPException(status_code=404, detail="No encontramos un vendedor directo asociado a tu cuenta")

    ventas = db.execute(text(f"""
        SELECT
            s.id,
            s.referral_code,
            s.estado,
            s.precio_pagado,
            s.created_at,
            u.nombre || ' ' || u.apellido AS cliente_nombre,
            u.email AS cliente_email,
            p.nombre AS plan_nombre,
            {DIRECT_COMMISSION_SQL} AS comision_generada
        FROM suscripciones s
        JOIN usuarios u ON u.id = s.usuario_id
        JOIN planes p ON p.id = s.plan_id
        JOIN direct_sellers ds ON ds.id = s.direct_seller_id
        WHERE ds.id = :seller_id
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT 20
    """), {"seller_id": seller.id}).fetchall()

    liquidaciones = db.execute(text("""
        SELECT id, monto, periodo_desde, periodo_hasta, estado, notas, paid_at, created_at
        FROM commission_liquidations
        WHERE destinatario_tipo = 'direct_seller'
          AND destinatario_id = :seller_id
        ORDER BY COALESCE(paid_at, created_at) DESC, id DESC
        LIMIT 20
    """), {"seller_id": seller.id}).fetchall()

    return {
        "rol": "direct_seller",
        "usuario": _serialize_usuario(usuario),
        "perfil": {
            "id": seller.id,
            "nombre": seller.nombre,
            "email": seller.email,
            "referral_code": seller.referral_code,
            "estado": seller.estado,
            "fecha_alta": seller.fecha_alta.isoformat() if seller.fecha_alta else None,
            "link_referido": f"/?ref={seller.referral_code}",
        },
        "metricas": {
            "ventas_asociadas": seller.ventas_asociadas,
            "revenue_generado": float(seller.revenue_generado or 0),
            "comision_acumulada": float(seller.comision_acumulada or 0),
            "total_liquidado": float(seller.total_liquidado or 0),
            "comision_pendiente": float((seller.comision_acumulada or 0) - (seller.total_liquidado or 0)),
            "comision_tipo": seller.comision_tipo,
            "comision_valor": float(seller.comision_valor or 0),
        },
        "equipo": [],
        "ventas": [_serialize_sale(row, "directo") for row in ventas],
        "liquidaciones": [_serialize_liquidacion(row) for row in liquidaciones],
    }


def _dashboard_broker_seller(db: Session, usuario):
    seller = db.execute(text("""
        SELECT
            bs.id,
            bs.nombre,
            bs.email,
            bs.referral_code,
            bs.estado,
            bs.fecha_alta,
            b.id AS broker_id,
            b.nombre AS broker_nombre
        FROM broker_sellers bs
        JOIN brokers b ON b.id = bs.broker_id
        WHERE bs.usuario_id = :usuario_id
           OR LOWER(bs.email) = LOWER(:email)
        ORDER BY CASE WHEN bs.usuario_id = :usuario_id THEN 0 ELSE 1 END
        LIMIT 1
    """), {"usuario_id": usuario.id, "email": usuario.email}).fetchone()

    if not seller:
        raise HTTPException(status_code=404, detail="No encontramos un vendedor de broker asociado a tu cuenta")

    ventas = db.execute(text("""
        SELECT
            s.id,
            s.referral_code,
            s.estado,
            s.precio_pagado,
            s.created_at,
            u.nombre || ' ' || u.apellido AS cliente_nombre,
            u.email AS cliente_email,
            p.nombre AS plan_nombre
        FROM suscripciones s
        JOIN usuarios u ON u.id = s.usuario_id
        JOIN planes p ON p.id = s.plan_id
        WHERE s.broker_seller_id = :seller_id
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT 20
    """), {"seller_id": seller.id}).fetchall()

    revenue = sum(float(item.precio_pagado or 0) for item in ventas)

    return {
        "rol": "broker_seller",
        "usuario": _serialize_usuario(usuario),
        "perfil": {
            "id": seller.id,
            "nombre": seller.nombre,
            "email": seller.email,
            "referral_code": seller.referral_code,
            "estado": seller.estado,
            "fecha_alta": seller.fecha_alta.isoformat() if seller.fecha_alta else None,
            "broker_id": seller.broker_id,
            "broker_nombre": seller.broker_nombre,
            "link_referido": f"/?ref={seller.referral_code}",
        },
        "metricas": {
            "ventas_asociadas": len(ventas),
            "revenue_generado": revenue,
        },
        "equipo": [],
        "ventas": [_serialize_sale(row, "broker") for row in ventas],
        "liquidaciones": [],
    }


def _serialize_usuario(usuario) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "email": usuario.email,
        "rol": usuario.rol,
    }


def _serialize_sale(row, canal: str) -> dict:
    return {
        "id": row.id,
        "referral_code": row.referral_code,
        "estado": row.estado,
        "precio_pagado": float(row.precio_pagado or 0),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "cliente_nombre": row.cliente_nombre,
        "cliente_email": row.cliente_email,
        "plan_nombre": row.plan_nombre,
        "canal": canal,
        "broker_seller_nombre": getattr(row, "broker_seller_nombre", None),
        "comision_generada": float(getattr(row, "comision_generada", 0) or 0),
    }


def _serialize_liquidacion(row) -> dict:
    return {
        "id": row.id,
        "monto": float(row.monto or 0),
        "periodo_desde": row.periodo_desde.isoformat() if row.periodo_desde else None,
        "periodo_hasta": row.periodo_hasta.isoformat() if row.periodo_hasta else None,
        "estado": row.estado,
        "notas": row.notas,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
