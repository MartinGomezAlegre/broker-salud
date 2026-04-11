import json

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.catalogo.common import descripcion_historial, logger


def historial_catalogo(
    db: Session,
    limit: int,
):
    try:
        rows = db.execute(text("""
            SELECT accion, tabla_afectada, registro_id, datos_anteriores, datos_nuevos, created_at
            FROM auditoria
            WHERE (tabla_afectada = 'planes' AND accion IN (
                    'crear_plan',
                    'actualizar_plan',
                    'cambio_precio_plan',
                    'cambiar_estado_plan'
               ))
               OR (tabla_afectada = 'cupones' AND accion IN (
                    'crear_cupon',
                    'actualizar_cupon',
                    'cambiar_estado_cupon',
                    'desactivar_cupon_por_usos',
                    'eliminar_cupon'
               ))
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

        payload = []
        for row in rows:
            datos_anteriores = row.datos_anteriores
            datos_nuevos = row.datos_nuevos
            if isinstance(datos_anteriores, str):
                datos_anteriores = json.loads(datos_anteriores)
            if isinstance(datos_nuevos, str):
                datos_nuevos = json.loads(datos_nuevos)

            payload.append({
                "accion": row.accion,
                "tabla": row.tabla_afectada,
                "registro_id": row.registro_id,
                "descripcion": descripcion_historial(
                    row.accion,
                    row.registro_id,
                    datos_anteriores or {},
                    datos_nuevos or {},
                ),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "datos_anteriores": datos_anteriores or {},
                "datos_nuevos": datos_nuevos or {},
            })

        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error interno: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
