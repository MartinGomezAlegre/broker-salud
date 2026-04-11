from datetime import date

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.catalogo import CuponActualizar, CuponCrear, CuponEstado
from app.services.catalogo.common import logger, registrar_auditoria, row_to_dict


def listar_cupones(db: Session):
    try:
        rows = db.execute(text("""
            SELECT c.id, c.codigo, c.descripcion, c.tipo_descuento, c.valor,
                   p.nombre AS plan_nombre,
                   c.max_usos, c.usos_actuales, c.valido_desde, c.valido_hasta,
                   c.solo_nuevos_usuarios, c.activo, c.created_at
            FROM cupones c
            LEFT JOIN planes p ON p.id = c.plan_id
            ORDER BY c.created_at DESC
        """)).fetchall()

        return [
            {
                "id": row.id,
                "codigo": row.codigo,
                "descripcion": row.descripcion,
                "tipo_descuento": row.tipo_descuento,
                "valor": float(row.valor) if row.valor is not None else None,
                "plan_nombre": row.plan_nombre,
                "max_usos": row.max_usos,
                "usos_actuales": row.usos_actuales,
                "valido_desde": row.valido_desde.isoformat() if row.valido_desde else None,
                "valido_hasta": row.valido_hasta.isoformat() if row.valido_hasta else None,
                "solo_nuevos": row.solo_nuevos_usuarios,
                "activo": row.activo,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def crear_cupon(
    db: Session,
    datos: CuponCrear,
):
    try:
        existente = db.execute(
            text("SELECT id FROM cupones WHERE codigo = :codigo"),
            {"codigo": datos.codigo},
        ).fetchone()
        if existente:
            raise HTTPException(status_code=400, detail="El codigo de cupon ya existe")

        result = db.execute(text("""
            INSERT INTO cupones
              (codigo, descripcion, tipo_descuento, valor, plan_id, max_usos,
               usos_actuales, valido_desde, valido_hasta, solo_nuevos_usuarios, activo)
            VALUES
              (:codigo, :descripcion, :tipo_descuento, :valor, :plan_id, :max_usos,
               0, :valido_desde, :valido_hasta, :solo_nuevos_usuarios, true)
            RETURNING id
        """), {
            "codigo": datos.codigo,
            "descripcion": datos.descripcion,
            "tipo_descuento": datos.tipo_descuento,
            "valor": datos.valor,
            "plan_id": datos.plan_id,
            "max_usos": datos.max_usos,
            "valido_desde": datos.valido_desde or date.today(),
            "valido_hasta": datos.valido_hasta,
            "solo_nuevos_usuarios": datos.solo_nuevos_usuarios,
        }).fetchone()

        cupon = db.execute(
            text("SELECT * FROM cupones WHERE id = :id"),
            {"id": result.id},
        ).fetchone()
        registrar_auditoria(db, "crear_cupon", "cupones", result.id, {}, row_to_dict(cupon))
        db.commit()

        return row_to_dict(cupon)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def actualizar_cupon(
    db: Session,
    cupon_id: int,
    datos: CuponActualizar,
):
    try:
        cupon = db.execute(
            text("SELECT * FROM cupones WHERE id = :id"),
            {"id": cupon_id},
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupon no encontrado")

        cambios = datos.model_dump(exclude_none=True)
        if not cambios:
            return row_to_dict(cupon)

        update_fields = [f"{campo} = :{campo}" for campo in cambios]
        db.execute(
            text(f"UPDATE cupones SET {', '.join(update_fields)} WHERE id = :id"),
            {"id": cupon_id, **cambios},
        )

        actualizado = db.execute(
            text("SELECT * FROM cupones WHERE id = :id"),
            {"id": cupon_id},
        ).fetchone()
        registrar_auditoria(
            db,
            "actualizar_cupon",
            "cupones",
            cupon_id,
            row_to_dict(cupon),
            row_to_dict(actualizado),
        )
        db.commit()

        return row_to_dict(actualizado)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def cambiar_estado_cupon(
    db: Session,
    cupon_id: int,
    datos: CuponEstado,
):
    try:
        cupon = db.execute(
            text("SELECT id, codigo, activo FROM cupones WHERE id = :id"),
            {"id": cupon_id},
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupon no encontrado")

        db.execute(
            text("UPDATE cupones SET activo = :activo WHERE id = :id"),
            {"activo": datos.activo, "id": cupon_id},
        )
        registrar_auditoria(
            db,
            "cambiar_estado_cupon",
            "cupones",
            cupon_id,
            {"codigo": cupon.codigo, "activo": cupon.activo},
            {"codigo": cupon.codigo, "activo": datos.activo},
        )
        db.commit()

        return {
            "id": cupon_id,
            "activo": datos.activo,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def eliminar_cupon(
    db: Session,
    cupon_id: int,
):
    try:
        cupon = db.execute(
            text("SELECT * FROM cupones WHERE id = :id"),
            {"id": cupon_id},
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupon no encontrado")

        cupon_payload = row_to_dict(cupon)
        if cupon.usos_actuales and cupon.usos_actuales > 0:
            db.execute(
                text("UPDATE cupones SET activo = false WHERE id = :id"),
                {"id": cupon_id},
            )
            registrar_auditoria(
                db,
                "desactivar_cupon_por_usos",
                "cupones",
                cupon_id,
                cupon_payload,
                {**cupon_payload, "activo": False},
            )
            db.commit()
            return {"mensaje": "El cupon tiene usos registrados, fue desactivado en lugar de eliminado"}

        registrar_auditoria(db, "eliminar_cupon", "cupones", cupon_id, cupon_payload, {})
        db.execute(
            text("DELETE FROM cupones WHERE id = :id"),
            {"id": cupon_id},
        )
        db.commit()

        return {"mensaje": "Cupon eliminado correctamente"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


def usos_cupon(
    db: Session,
    cupon_id: int,
):
    try:
        cupon = db.execute(
            text("SELECT id FROM cupones WHERE id = :id"),
            {"id": cupon_id},
        ).fetchone()
        if not cupon:
            raise HTTPException(status_code=404, detail="Cupon no encontrado")

        rows = db.execute(text("""
            SELECT u.nombre || ' ' || u.apellido AS nombre_usuario,
                   u.email,
                   p.nombre AS plan_contratado,
                   cu.descuento_aplicado,
                   cu.created_at AS fecha_uso
            FROM cupones_uso cu
            JOIN usuarios u ON u.id = cu.usuario_id
            LEFT JOIN suscripciones s ON s.id = cu.suscripcion_id
            LEFT JOIN planes p ON p.id = s.plan_id
            WHERE cu.cupon_id = :cupon_id
            ORDER BY cu.created_at DESC
        """), {"cupon_id": cupon_id}).fetchall()

        return [
            {
                "nombre_usuario": row.nombre_usuario,
                "email": row.email,
                "plan_contratado": row.plan_contratado,
                "descuento_aplicado": float(row.descuento_aplicado) if row.descuento_aplicado else None,
                "fecha_uso": row.fecha_uso.isoformat() if row.fecha_uso else None,
            }
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
