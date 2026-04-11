import logging

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.comercial import (
    BrokerActualizar,
    BrokerCrear,
    BrokerSellerActualizar,
    BrokerSellerCrear,
    DirectSellerActualizar,
    DirectSellerCrear,
    LiquidacionCrear,
)
from app.services.comercial.accounts import create_commercial_user, update_commercial_user
from app.services.comercial.common import (
    COMMISSIONABLE_STATES,
    compute_commission_sql,
    ensure_commercial_schema,
    generate_referral_code,
    referral_code_exists,
)

logger = logging.getLogger(__name__)

BROKER_COMMISSION_SQL = compute_commission_sql("s.precio_pagado", "b.comision_tipo", "b.comision_valor")
DIRECT_COMMISSION_SQL = compute_commission_sql("s.precio_pagado", "ds.comision_tipo", "ds.comision_valor")


def resumen_comercial(db: Session):
    try:
        ensure_commercial_schema(db)

        row = db.execute(text(f"""
            WITH broker_commissions AS (
                SELECT COALESCE(SUM({BROKER_COMMISSION_SQL}), 0) AS total
                FROM suscripciones s
                JOIN broker_sellers bs ON bs.id = s.broker_seller_id
                JOIN brokers b ON b.id = bs.broker_id
                WHERE s.estado = ANY(:states)
            ),
            direct_commissions AS (
                SELECT COALESCE(SUM({DIRECT_COMMISSION_SQL}), 0) AS total
                FROM suscripciones s
                JOIN direct_sellers ds ON ds.id = s.direct_seller_id
                WHERE s.estado = ANY(:states)
            ),
            liquidated AS (
                SELECT destinatario_tipo, COALESCE(SUM(monto), 0) AS total
                FROM commission_liquidations
                GROUP BY destinatario_tipo
            )
            SELECT
                (SELECT COUNT(*) FROM brokers) AS total_brokers,
                (SELECT COUNT(*) FROM brokers WHERE estado = 'activo') AS brokers_activos,
                (SELECT COUNT(*) FROM broker_sellers) AS total_broker_sellers,
                (SELECT COUNT(*) FROM broker_sellers WHERE estado = 'activo') AS broker_sellers_activos,
                (SELECT COUNT(*) FROM direct_sellers) AS total_direct_sellers,
                (SELECT COUNT(*) FROM direct_sellers WHERE estado = 'activo') AS direct_sellers_activos,
                (SELECT COUNT(*) FROM suscripciones WHERE referral_code IS NOT NULL) AS ventas_referidas,
                (SELECT COALESCE(SUM(precio_pagado), 0) FROM suscripciones WHERE referral_code IS NOT NULL AND estado = ANY(:states)) AS revenue_referido,
                COALESCE((SELECT total FROM broker_commissions), 0) - COALESCE((SELECT total FROM liquidated WHERE destinatario_tipo = 'broker'), 0) AS pendiente_brokers,
                COALESCE((SELECT total FROM direct_commissions), 0) - COALESCE((SELECT total FROM liquidated WHERE destinatario_tipo = 'direct_seller'), 0) AS pendiente_directos
        """), {"states": list(COMMISSIONABLE_STATES)}).fetchone()

        return {
            "total_brokers": row.total_brokers,
            "brokers_activos": row.brokers_activos,
            "total_broker_sellers": row.total_broker_sellers,
            "broker_sellers_activos": row.broker_sellers_activos,
            "total_direct_sellers": row.total_direct_sellers,
            "direct_sellers_activos": row.direct_sellers_activos,
            "ventas_referidas": row.ventas_referidas,
            "revenue_referido": float(row.revenue_referido or 0),
            "comision_pendiente_brokers": float(row.pendiente_brokers or 0),
            "comision_pendiente_directos": float(row.pendiente_directos or 0),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en resumen_comercial: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar el resumen comercial")


def listar_usuarios_comerciales(
    db: Session,
    buscar: str | None,
):
    try:
        ensure_commercial_schema(db)
        params: dict = {}
        filtro = ""

        if buscar:
            filtro = """
                AND (
                    u.nombre ILIKE :buscar OR
                    u.apellido ILIKE :buscar OR
                    u.email ILIKE :buscar
                )
            """
            params["buscar"] = f"%{buscar}%"

        rows = db.execute(text(f"""
            SELECT
                u.id,
                u.nombre,
                u.apellido,
                u.email,
                u.rol,
                u.activo
            FROM usuarios u
            WHERE u.activo = true
              AND COALESCE(u.rol, 'cliente') <> 'admin'
            {filtro}
            ORDER BY u.nombre ASC, u.apellido ASC, u.email ASC
            LIMIT 100
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "nombre": row.nombre,
                "apellido": row.apellido,
                "email": row.email,
                "rol": row.rol,
                "activo": row.activo,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_usuarios_comerciales: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar usuarios disponibles")


def listar_brokers(db: Session, estado: str | None, buscar: str | None):
    try:
        ensure_commercial_schema(db)
        condiciones = ["1=1"]
        params: dict = {"states": list(COMMISSIONABLE_STATES)}

        if estado:
            condiciones.append("b.estado = :estado")
            params["estado"] = estado
        if buscar:
            condiciones.append("(b.nombre ILIKE :buscar OR COALESCE(b.contacto, '') ILIKE :buscar)")
            params["buscar"] = f"%{buscar}%"

        where = " AND ".join(condiciones)
        rows = db.execute(text(f"""
            SELECT
                b.id,
                b.nombre,
                b.contacto,
                b.comision_tipo,
                b.comision_valor,
                b.estado,
                b.fecha_alta,
                b.usuario_id,
                u.nombre AS usuario_nombre,
                u.apellido AS usuario_apellido,
                u.email AS usuario_email,
                COALESCE(sellers.total_sellers, 0) AS total_sellers,
                COALESCE(sellers.active_sellers, 0) AS active_sellers,
                COALESCE(sales.ventas_asociadas, 0) AS ventas_asociadas,
                COALESCE(sales.revenue_generado, 0) AS revenue_generado,
                COALESCE(sales.comision_acumulada, 0) AS comision_acumulada,
                COALESCE(liq.total_liquidado, 0) AS total_liquidado
            FROM brokers b
            LEFT JOIN usuarios u ON u.id = b.usuario_id
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS total_sellers,
                    COUNT(*) FILTER (WHERE estado = 'activo') AS active_sellers
                FROM broker_sellers bs
                WHERE bs.broker_id = b.id
            ) sellers ON true
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS ventas_asociadas,
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
            WHERE {where}
            ORDER BY b.fecha_alta DESC, b.id DESC
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "nombre": row.nombre,
                "contacto": row.contacto,
                "comision_tipo": row.comision_tipo,
                "comision_valor": float(row.comision_valor or 0),
                "estado": row.estado,
                "fecha_alta": row.fecha_alta.isoformat() if row.fecha_alta else None,
                "usuario_id": row.usuario_id,
                "usuario_nombre": _full_name(row.usuario_nombre, row.usuario_apellido),
                "usuario_email": row.usuario_email,
                "total_sellers": row.total_sellers,
                "active_sellers": row.active_sellers,
                "ventas_asociadas": row.ventas_asociadas,
                "revenue_generado": float(row.revenue_generado or 0),
                "comision_acumulada": float(row.comision_acumulada or 0),
                "total_liquidado": float(row.total_liquidado or 0),
                "comision_pendiente": float((row.comision_acumulada or 0) - (row.total_liquidado or 0)),
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_brokers: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar brokers")


def crear_broker(db: Session, datos: BrokerCrear):
    try:
        ensure_commercial_schema(db)
        usuario_id = _resolve_admin_access_for_create(
            db,
            target_role="broker",
            full_name=datos.nombre,
            usuario_id=datos.usuario_id,
            access_email=datos.access_email,
            access_password=datos.access_password,
        )
        row = db.execute(text("""
            INSERT INTO brokers (nombre, contacto, comision_tipo, comision_valor, estado, fecha_alta, usuario_id)
            VALUES (:nombre, :contacto, :comision_tipo, :comision_valor, :estado, NOW(), :usuario_id)
            RETURNING id
        """), {
            "nombre": datos.nombre,
            "contacto": datos.contacto,
            "comision_tipo": datos.comision_tipo,
            "comision_valor": datos.comision_valor,
            "estado": datos.estado,
            "usuario_id": usuario_id,
        }).fetchone()
        if usuario_id is not None:
            _set_usuario_role(db, usuario_id, "broker")
        db.commit()
        return obtener_broker(db, row.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_broker: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos crear el broker")


def actualizar_broker(db: Session, broker_id: int, datos: BrokerActualizar):
    try:
        ensure_commercial_schema(db)
        actual = db.execute(text("SELECT id, usuario_id FROM brokers WHERE id = :id"), {"id": broker_id}).fetchone()
        if not actual:
            raise HTTPException(status_code=404, detail="Broker no encontrado")

        incoming = datos.model_dump(exclude_unset=True)
        payload = dict(incoming)
        previous_usuario_id = actual.usuario_id
        next_usuario_id = _resolve_admin_access_for_update(
            db,
            target_role="broker",
            full_name=payload.get("nombre") or obtener_broker(db, broker_id)["nombre"],
            current_usuario_id=actual.usuario_id,
            usuario_id=payload.pop("usuario_id", None) if "usuario_id" in payload else None,
            access_email=payload.pop("access_email", None) if "access_email" in payload else None,
            access_password=payload.pop("access_password", None) if "access_password" in payload else None,
            current_table="brokers",
            current_id=broker_id,
        )
        touched_access = any(field in incoming for field in ("usuario_id", "access_email", "access_password"))
        if "usuario_id" in incoming or next_usuario_id != actual.usuario_id:
            payload["usuario_id"] = next_usuario_id
        if payload or touched_access:
            if payload:
                set_clause = ", ".join(f"{field} = :{field}" for field in payload)
                db.execute(
                    text(f"UPDATE brokers SET {set_clause} WHERE id = :id"),
                    {"id": broker_id, **payload},
                )
            if "usuario_id" in payload:
                if payload["usuario_id"] is not None:
                    _set_usuario_role(db, payload["usuario_id"], "broker")
                if previous_usuario_id and previous_usuario_id != payload["usuario_id"]:
                    _clear_usuario_role_if_unlinked(db, previous_usuario_id, "broker")
            db.commit()
        return obtener_broker(db, broker_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_broker: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos actualizar el broker")


def listar_broker_sellers(db: Session, broker_id: int | None, estado: str | None, buscar: str | None):
    try:
        ensure_commercial_schema(db)
        condiciones = ["1=1"]
        params: dict = {"states": list(COMMISSIONABLE_STATES)}

        if broker_id is not None:
            condiciones.append("bs.broker_id = :broker_id")
            params["broker_id"] = broker_id
        if estado:
            condiciones.append("bs.estado = :estado")
            params["estado"] = estado
        if buscar:
            condiciones.append("(bs.nombre ILIKE :buscar OR bs.email ILIKE :buscar OR bs.referral_code ILIKE :buscar)")
            params["buscar"] = f"%{buscar}%"

        where = " AND ".join(condiciones)
        rows = db.execute(text(f"""
            SELECT
                bs.id,
                bs.broker_id,
                b.nombre AS broker_nombre,
                bs.nombre,
                bs.email,
                bs.referral_code,
                bs.estado,
                bs.fecha_alta,
                bs.usuario_id,
                u.nombre AS usuario_nombre,
                u.apellido AS usuario_apellido,
                u.email AS usuario_email,
                COALESCE(COUNT(s.id), 0) AS ventas_asociadas,
                COALESCE(SUM(s.precio_pagado), 0) AS revenue_generado
            FROM broker_sellers bs
            JOIN brokers b ON b.id = bs.broker_id
            LEFT JOIN usuarios u ON u.id = bs.usuario_id
            LEFT JOIN suscripciones s
                ON s.broker_seller_id = bs.id
               AND s.estado = ANY(:states)
            WHERE {where}
            GROUP BY bs.id, b.nombre, u.nombre, u.apellido, u.email
            ORDER BY bs.fecha_alta DESC, bs.id DESC
        """), params).fetchall()

        return [_serialize_broker_seller(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_broker_sellers: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar vendedores de broker")


def crear_broker_seller(db: Session, datos: BrokerSellerCrear):
    try:
        ensure_commercial_schema(db)
        _ensure_broker_exists(db, datos.broker_id)
        if datos.usuario_id is not None:
            _ensure_usuario_assignable(db, datos.usuario_id, "broker_seller")
        referral_code = datos.referral_code or generate_referral_code(db, datos.nombre)
        if referral_code_exists(db, referral_code):
            raise HTTPException(status_code=400, detail="El referral code ya esta en uso")

        params = datos.model_dump()
        params["referral_code"] = referral_code

        row = db.execute(text("""
            INSERT INTO broker_sellers (broker_id, nombre, email, referral_code, estado, fecha_alta, usuario_id)
            VALUES (:broker_id, :nombre, :email, :referral_code, :estado, NOW(), :usuario_id)
            RETURNING id
        """), params).fetchone()
        if datos.usuario_id is not None:
            _set_usuario_role(db, datos.usuario_id, "broker_seller")
        db.commit()
        return obtener_broker_seller(db, row.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_broker_seller: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos crear el vendedor del broker")


def actualizar_broker_seller(db: Session, seller_id: int, datos: BrokerSellerActualizar):
    try:
        ensure_commercial_schema(db)
        actual = db.execute(text("""
            SELECT id, referral_code, usuario_id
            FROM broker_sellers
            WHERE id = :id
        """), {"id": seller_id}).fetchone()
        if not actual:
            raise HTTPException(status_code=404, detail="Vendedor de broker no encontrado")

        payload = datos.model_dump(exclude_unset=True)
        previous_usuario_id = actual.usuario_id
        if "broker_id" in payload and payload["broker_id"] is not None:
            _ensure_broker_exists(db, payload["broker_id"])
        if "usuario_id" in payload and payload["usuario_id"] is not None:
            _ensure_usuario_assignable(db, payload["usuario_id"], "broker_seller", "broker_sellers", seller_id)
        if "referral_code" in payload:
            referral_code = payload["referral_code"] or generate_referral_code(db, payload.get("nombre") or actual.referral_code)
            if referral_code_exists(db, referral_code, exclude_table="broker_sellers", exclude_id=seller_id):
                raise HTTPException(status_code=400, detail="El referral code ya esta en uso")
            payload["referral_code"] = referral_code

        if payload:
            set_clause = ", ".join(f"{field} = :{field}" for field in payload)
            db.execute(
                text(f"UPDATE broker_sellers SET {set_clause} WHERE id = :id"),
                {"id": seller_id, **payload},
            )
            if "usuario_id" in payload:
                if payload["usuario_id"] is not None:
                    _set_usuario_role(db, payload["usuario_id"], "broker_seller")
                if previous_usuario_id and previous_usuario_id != payload["usuario_id"]:
                    _clear_usuario_role_if_unlinked(db, previous_usuario_id, "broker_seller")
            db.commit()
        return obtener_broker_seller(db, seller_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_broker_seller: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos actualizar el vendedor de broker")


def listar_direct_sellers(db: Session, estado: str | None, buscar: str | None):
    try:
        ensure_commercial_schema(db)
        condiciones = ["1=1"]
        params: dict = {"states": list(COMMISSIONABLE_STATES)}

        if estado:
            condiciones.append("ds.estado = :estado")
            params["estado"] = estado
        if buscar:
            condiciones.append("(ds.nombre ILIKE :buscar OR ds.email ILIKE :buscar OR ds.referral_code ILIKE :buscar)")
            params["buscar"] = f"%{buscar}%"

        where = " AND ".join(condiciones)
        rows = db.execute(text(f"""
            SELECT
                ds.id,
                ds.nombre,
                ds.email,
                ds.referral_code,
                ds.comision_tipo,
                ds.comision_valor,
                ds.estado,
                ds.fecha_alta,
                ds.usuario_id,
                u.nombre AS usuario_nombre,
                u.apellido AS usuario_apellido,
                u.email AS usuario_email,
                COALESCE(COUNT(s.id), 0) AS ventas_asociadas,
                COALESCE(SUM(s.precio_pagado), 0) AS revenue_generado,
                COALESCE(SUM({DIRECT_COMMISSION_SQL}), 0) AS comision_acumulada,
                COALESCE(liq.total_liquidado, 0) AS total_liquidado
            FROM direct_sellers ds
            LEFT JOIN usuarios u ON u.id = ds.usuario_id
            LEFT JOIN suscripciones s
                ON s.direct_seller_id = ds.id
               AND s.estado = ANY(:states)
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(monto), 0) AS total_liquidado
                FROM commission_liquidations cl
                WHERE cl.destinatario_tipo = 'direct_seller'
                  AND cl.destinatario_id = ds.id
            ) liq ON true
            WHERE {where}
            GROUP BY ds.id, liq.total_liquidado, u.nombre, u.apellido, u.email
            ORDER BY ds.fecha_alta DESC, ds.id DESC
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "nombre": row.nombre,
                "email": row.email,
                "referral_code": row.referral_code,
                "comision_tipo": row.comision_tipo,
                "comision_valor": float(row.comision_valor or 0),
                "estado": row.estado,
                "fecha_alta": row.fecha_alta.isoformat() if row.fecha_alta else None,
                "usuario_id": row.usuario_id,
                "usuario_nombre": _full_name(row.usuario_nombre, row.usuario_apellido),
                "usuario_email": row.usuario_email,
                "ventas_asociadas": row.ventas_asociadas,
                "revenue_generado": float(row.revenue_generado or 0),
                "comision_acumulada": float(row.comision_acumulada or 0),
                "total_liquidado": float(row.total_liquidado or 0),
                "comision_pendiente": float((row.comision_acumulada or 0) - (row.total_liquidado or 0)),
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_direct_sellers: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar vendedores directos")


def crear_direct_seller(db: Session, datos: DirectSellerCrear):
    try:
        ensure_commercial_schema(db)
        usuario_id = _resolve_admin_access_for_create(
            db,
            target_role="direct_seller",
            full_name=datos.nombre,
            usuario_id=datos.usuario_id,
            access_email=datos.access_email,
            access_password=datos.access_password,
        )
        referral_code = datos.referral_code or generate_referral_code(db, datos.nombre)
        if referral_code_exists(db, referral_code):
            raise HTTPException(status_code=400, detail="El referral code ya esta en uso")

        params = {
            "nombre": datos.nombre,
            "email": datos.email,
            "referral_code": referral_code,
            "comision_tipo": datos.comision_tipo,
            "comision_valor": datos.comision_valor,
            "estado": datos.estado,
            "usuario_id": usuario_id,
        }
        row = db.execute(text("""
            INSERT INTO direct_sellers
                (nombre, email, referral_code, comision_tipo, comision_valor, estado, fecha_alta, usuario_id)
            VALUES
                (:nombre, :email, :referral_code, :comision_tipo, :comision_valor, :estado, NOW(), :usuario_id)
            RETURNING id
        """), params).fetchone()
        if usuario_id is not None:
            _set_usuario_role(db, usuario_id, "direct_seller")
        db.commit()
        return obtener_direct_seller(db, row.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_direct_seller: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos crear el vendedor directo")


def actualizar_direct_seller(db: Session, seller_id: int, datos: DirectSellerActualizar):
    try:
        ensure_commercial_schema(db)
        actual = db.execute(text("""
            SELECT id, referral_code, usuario_id
            FROM direct_sellers
            WHERE id = :id
        """), {"id": seller_id}).fetchone()
        if not actual:
            raise HTTPException(status_code=404, detail="Vendedor directo no encontrado")

        payload = datos.model_dump(exclude_unset=True)
        previous_usuario_id = actual.usuario_id
        next_usuario_id = _resolve_admin_access_for_update(
            db,
            target_role="direct_seller",
            full_name=payload.get("nombre") or obtener_direct_seller(db, seller_id)["nombre"],
            current_usuario_id=actual.usuario_id,
            usuario_id=payload.pop("usuario_id", None) if "usuario_id" in payload else None,
            access_email=payload.pop("access_email", None) if "access_email" in payload else None,
            access_password=payload.pop("access_password", None) if "access_password" in payload else None,
            current_table="direct_sellers",
            current_id=seller_id,
        )
        touched_access = any(field in payload or field in datos.model_dump(exclude_unset=True) for field in ("usuario_id", "access_email", "access_password"))
        if "usuario_id" in datos.model_dump(exclude_unset=True) or next_usuario_id != actual.usuario_id:
            payload["usuario_id"] = next_usuario_id
        if "referral_code" in payload:
            referral_code = payload["referral_code"] or generate_referral_code(db, payload.get("nombre") or actual.referral_code)
            if referral_code_exists(db, referral_code, exclude_table="direct_sellers", exclude_id=seller_id):
                raise HTTPException(status_code=400, detail="El referral code ya esta en uso")
            payload["referral_code"] = referral_code

        if payload or touched_access:
            set_clause = ", ".join(f"{field} = :{field}" for field in payload)
            if payload:
                db.execute(
                    text(f"UPDATE direct_sellers SET {set_clause} WHERE id = :id"),
                    {"id": seller_id, **payload},
                )
            if "usuario_id" in payload:
                if payload["usuario_id"] is not None:
                    _set_usuario_role(db, payload["usuario_id"], "direct_seller")
                if previous_usuario_id and previous_usuario_id != payload["usuario_id"]:
                    _clear_usuario_role_if_unlinked(db, previous_usuario_id, "direct_seller")
            db.commit()

        return obtener_direct_seller(db, seller_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en actualizar_direct_seller: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos actualizar el vendedor directo")


def listar_ventas_referidas(
    db: Session,
    canal: str | None,
    estado: str | None,
    buscar: str | None,
):
    try:
        ensure_commercial_schema(db)
        condiciones = ["s.referral_code IS NOT NULL"]
        params: dict = {}

        if canal == "directo":
            condiciones.append("s.direct_seller_id IS NOT NULL")
        elif canal == "broker":
            condiciones.append("s.broker_seller_id IS NOT NULL")
        if estado:
            condiciones.append("s.estado = :estado")
            params["estado"] = estado
        if buscar:
            condiciones.append("""
                (
                    u.nombre ILIKE :buscar OR
                    u.apellido ILIKE :buscar OR
                    u.email ILIKE :buscar OR
                    COALESCE(ds.nombre, '') ILIKE :buscar OR
                    COALESCE(bs.nombre, '') ILIKE :buscar OR
                    COALESCE(b.nombre, '') ILIKE :buscar OR
                    s.referral_code ILIKE :buscar
                )
            """)
            params["buscar"] = f"%{buscar}%"

        where = " AND ".join(condiciones)
        rows = db.execute(text(f"""
            SELECT
                s.id,
                s.referral_code,
                s.estado,
                s.precio_pagado,
                s.created_at,
                u.nombre || ' ' || u.apellido AS cliente_nombre,
                u.email AS cliente_email,
                p.nombre AS plan_nombre,
                CASE
                    WHEN s.direct_seller_id IS NOT NULL THEN 'directo'
                    ELSE 'broker'
                END AS canal,
                ds.id AS direct_seller_id,
                ds.nombre AS direct_seller_nombre,
                bs.id AS broker_seller_id,
                bs.nombre AS broker_seller_nombre,
                b.id AS broker_id,
                b.nombre AS broker_nombre,
                CASE
                    WHEN s.direct_seller_id IS NOT NULL THEN {DIRECT_COMMISSION_SQL}
                    ELSE {BROKER_COMMISSION_SQL}
                END AS comision_generada
            FROM suscripciones s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN planes p ON p.id = s.plan_id
            LEFT JOIN direct_sellers ds ON ds.id = s.direct_seller_id
            LEFT JOIN broker_sellers bs ON bs.id = s.broker_seller_id
            LEFT JOIN brokers b ON b.id = bs.broker_id
            WHERE {where}
            ORDER BY s.created_at DESC, s.id DESC
        """), params).fetchall()

        return [
            {
                "id": row.id,
                "referral_code": row.referral_code,
                "estado": row.estado,
                "precio_pagado": float(row.precio_pagado or 0),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "cliente_nombre": row.cliente_nombre,
                "cliente_email": row.cliente_email,
                "plan_nombre": row.plan_nombre,
                "canal": row.canal,
                "direct_seller_id": row.direct_seller_id,
                "direct_seller_nombre": row.direct_seller_nombre,
                "broker_seller_id": row.broker_seller_id,
                "broker_seller_nombre": row.broker_seller_nombre,
                "broker_id": row.broker_id,
                "broker_nombre": row.broker_nombre,
                "comision_generada": float(row.comision_generada or 0),
                "es_comisionable": row.estado in COMMISSIONABLE_STATES,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_ventas_referidas: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar ventas referidas")


def listar_liquidaciones(db: Session):
    try:
        ensure_commercial_schema(db)
        rows = db.execute(text("""
            SELECT
                cl.id,
                cl.destinatario_tipo,
                cl.destinatario_id,
                cl.monto,
                cl.periodo_desde,
                cl.periodo_hasta,
                cl.estado,
                cl.notas,
                cl.paid_at,
                cl.created_at,
                COALESCE(b.nombre, ds.nombre) AS destinatario_nombre
            FROM commission_liquidations cl
            LEFT JOIN brokers b
                ON cl.destinatario_tipo = 'broker'
               AND b.id = cl.destinatario_id
            LEFT JOIN direct_sellers ds
                ON cl.destinatario_tipo = 'direct_seller'
               AND ds.id = cl.destinatario_id
            ORDER BY COALESCE(cl.paid_at, cl.created_at) DESC, cl.id DESC
        """)).fetchall()

        return [
            {
                "id": row.id,
                "destinatario_tipo": row.destinatario_tipo,
                "destinatario_id": row.destinatario_id,
                "destinatario_nombre": row.destinatario_nombre,
                "monto": float(row.monto or 0),
                "periodo_desde": row.periodo_desde.isoformat() if row.periodo_desde else None,
                "periodo_hasta": row.periodo_hasta.isoformat() if row.periodo_hasta else None,
                "estado": row.estado,
                "notas": row.notas,
                "paid_at": row.paid_at.isoformat() if row.paid_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en listar_liquidaciones: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos cargar liquidaciones")


def crear_liquidacion(db: Session, datos: LiquidacionCrear, admin_id: int):
    try:
        ensure_commercial_schema(db)
        _ensure_destinatario_exists(db, datos.destinatario_tipo, datos.destinatario_id)
        row = db.execute(text("""
            INSERT INTO commission_liquidations
                (destinatario_tipo, destinatario_id, monto, periodo_desde, periodo_hasta, estado, notas, paid_at, created_at, admin_id)
            VALUES
                (:destinatario_tipo, :destinatario_id, :monto, :periodo_desde, :periodo_hasta, 'pagada', :notas, NOW(), NOW(), :admin_id)
            RETURNING id
        """), {
            **datos.model_dump(),
            "admin_id": admin_id,
        }).fetchone()
        db.commit()
        return obtener_liquidacion(db, row.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error en crear_liquidacion: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="No pudimos registrar la liquidacion")


def obtener_broker(db: Session, broker_id: int):
    brokers = listar_brokers(db, estado=None, buscar=None)
    for broker in brokers:
        if broker["id"] == broker_id:
            return broker
    raise HTTPException(status_code=404, detail="Broker no encontrado")


def obtener_broker_seller(db: Session, seller_id: int):
    rows = listar_broker_sellers(db, broker_id=None, estado=None, buscar=None)
    for row in rows:
        if row["id"] == seller_id:
            return row
    raise HTTPException(status_code=404, detail="Vendedor de broker no encontrado")


def obtener_direct_seller(db: Session, seller_id: int):
    rows = listar_direct_sellers(db, estado=None, buscar=None)
    for row in rows:
        if row["id"] == seller_id:
            return row
    raise HTTPException(status_code=404, detail="Vendedor directo no encontrado")


def obtener_liquidacion(db: Session, liquidation_id: int):
    rows = listar_liquidaciones(db)
    for row in rows:
        if row["id"] == liquidation_id:
            return row
    raise HTTPException(status_code=404, detail="Liquidacion no encontrada")


def _ensure_broker_exists(db: Session, broker_id: int):
    row = db.execute(text("SELECT id FROM brokers WHERE id = :id"), {"id": broker_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Broker no encontrado")


def _ensure_destinatario_exists(db: Session, destinatario_tipo: str, destinatario_id: int):
    table = "brokers" if destinatario_tipo == "broker" else "direct_sellers"
    row = db.execute(text(f"SELECT id FROM {table} WHERE id = :id"), {"id": destinatario_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Destinatario no encontrado")


def _resolve_admin_access_for_create(
    db: Session,
    *,
    target_role: str,
    full_name: str,
    usuario_id: int | None,
    access_email: str | None,
    access_password: str | None,
) -> int | None:
    if usuario_id is not None:
        _ensure_usuario_assignable(db, usuario_id, target_role)
        return usuario_id

    if access_email and access_password:
        return create_commercial_user(
            db,
            full_name=full_name,
            email=access_email,
            password=access_password,
            role=target_role,
        )

    if access_email or access_password:
        raise HTTPException(
            status_code=400,
            detail="Para crear un acceso comercial nuevo necesitamos email y contrasena inicial",
        )

    return None


def _resolve_admin_access_for_update(
    db: Session,
    *,
    target_role: str,
    full_name: str,
    current_usuario_id: int | None,
    usuario_id: int | None,
    access_email: str | None,
    access_password: str | None,
    current_table: str,
    current_id: int,
) -> int | None:
    if usuario_id is not None:
        _ensure_usuario_assignable(db, usuario_id, target_role, current_table, current_id)
        return usuario_id

    if access_email or access_password:
        if current_usuario_id:
            current_email = _get_usuario_email(db, current_usuario_id)
            update_commercial_user(
                db,
                usuario_id=current_usuario_id,
                full_name=full_name,
                email=access_email or current_email,
                password=access_password,
                role=target_role,
            )
            return current_usuario_id

        if access_email and access_password:
            return create_commercial_user(
                db,
                full_name=full_name,
                email=access_email,
                password=access_password,
                role=target_role,
            )

        raise HTTPException(
            status_code=400,
            detail="Para crear un nuevo acceso comercial necesitamos email y contrasena inicial",
        )

    return current_usuario_id


def _ensure_usuario_assignable(
    db: Session,
    usuario_id: int,
    target_role: str,
    current_table: str | None = None,
    current_id: int | None = None,
):
    usuario = db.execute(text("""
        SELECT id, rol, activo
        FROM usuarios
        WHERE id = :id
    """), {"id": usuario_id}).fetchone()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not usuario.activo:
        raise HTTPException(status_code=400, detail="No podes vincular un usuario inactivo")

    for table in ("brokers", "broker_sellers", "direct_sellers"):
        params: dict = {"usuario_id": usuario_id}
        sql = f"SELECT id FROM {table} WHERE usuario_id = :usuario_id"
        if current_table == table and current_id is not None:
            sql += " AND id <> :current_id"
            params["current_id"] = current_id
        row = db.execute(text(sql), params).fetchone()
        if row:
            raise HTTPException(
                status_code=400,
                detail="Este usuario ya esta vinculado a otro perfil comercial",
            )

    if usuario.rol == "admin":
        raise HTTPException(status_code=400, detail="No podes vincular un usuario admin al canal comercial")

    if usuario.rol not in (None, "", "cliente", target_role):
        raise HTTPException(
            status_code=400,
            detail=f"El usuario ya tiene un rol incompatible: {usuario.rol}",
        )


def _set_usuario_role(db: Session, usuario_id: int, role: str):
    db.execute(
        text("UPDATE usuarios SET rol = :role WHERE id = :id"),
        {"role": role, "id": usuario_id},
    )


def _clear_usuario_role_if_unlinked(db: Session, usuario_id: int, expected_role: str):
    linked = db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM brokers WHERE usuario_id = :usuario_id
            UNION ALL
            SELECT 1 FROM broker_sellers WHERE usuario_id = :usuario_id
            UNION ALL
            SELECT 1 FROM direct_sellers WHERE usuario_id = :usuario_id
        ) AS is_linked
    """), {"usuario_id": usuario_id}).fetchone()

    if linked and linked.is_linked:
        return

    db.execute(text("""
        UPDATE usuarios
        SET rol = 'cliente'
        WHERE id = :usuario_id
          AND rol = :expected_role
    """), {"usuario_id": usuario_id, "expected_role": expected_role})


def _get_usuario_email(db: Session, usuario_id: int) -> str:
    row = db.execute(
        text("SELECT email FROM usuarios WHERE id = :id"),
        {"id": usuario_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario comercial no encontrado")
    return row.email


def _serialize_broker_seller(row) -> dict:
    return {
        "id": row.id,
        "broker_id": row.broker_id,
        "broker_nombre": row.broker_nombre,
        "nombre": row.nombre,
        "email": row.email,
        "referral_code": row.referral_code,
        "estado": row.estado,
        "fecha_alta": row.fecha_alta.isoformat() if row.fecha_alta else None,
        "usuario_id": row.usuario_id,
        "usuario_nombre": _full_name(row.usuario_nombre, row.usuario_apellido),
        "usuario_email": row.usuario_email,
        "ventas_asociadas": row.ventas_asociadas,
        "revenue_generado": float(row.revenue_generado or 0),
    }


def _full_name(nombre: str | None, apellido: str | None) -> str | None:
    parts = [part for part in (nombre, apellido) if part]
    return " ".join(parts) if parts else None
