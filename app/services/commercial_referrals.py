import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_referral_schema_checked = False
_referral_schema_available = False


def resolve_referral_tracking(
    db: Session,
    referral_code: str | None,
) -> dict:
    if not referral_code:
        return {}

    if not _ensure_referral_schema(db):
        logger.warning("Referral code recibido pero la base comercial aun no esta migrada")
        return {}

    direct_seller = db.execute(text("""
        SELECT id
        FROM direct_sellers
        WHERE referral_code = :referral_code
          AND estado = 'activo'
        LIMIT 1
    """), {"referral_code": referral_code}).fetchone()
    if direct_seller:
        return {
            "referral_code": referral_code,
            "direct_seller_id": direct_seller.id,
            "broker_seller_id": None,
        }

    broker_seller = db.execute(text("""
        SELECT id
        FROM broker_sellers
        WHERE referral_code = :referral_code
          AND estado = 'activo'
        LIMIT 1
    """), {"referral_code": referral_code}).fetchone()
    if broker_seller:
        return {
            "referral_code": referral_code,
            "direct_seller_id": None,
            "broker_seller_id": broker_seller.id,
        }

    return {}


def build_referral_insert(referral_tracking: dict) -> tuple[str, str, dict]:
    if not referral_tracking:
        return "", "", {}

    columns = ", referral_code, broker_seller_id, direct_seller_id"
    values = ", :referral_code, :broker_seller_id, :direct_seller_id"
    return columns, values, referral_tracking


def build_referral_update(referral_tracking: dict) -> tuple[str, dict]:
    if not referral_tracking:
        return "", {}

    set_clause = """,
            referral_code = :referral_code,
            broker_seller_id = :broker_seller_id,
            direct_seller_id = :direct_seller_id"""
    return set_clause, referral_tracking


def _ensure_referral_schema(db: Session) -> bool:
    global _referral_schema_checked, _referral_schema_available
    if _referral_schema_checked:
        return _referral_schema_available

    columns = db.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'suscripciones'
          AND column_name IN ('referral_code', 'broker_seller_id', 'direct_seller_id')
    """)).fetchall()
    tables = db.execute(text("""
        SELECT to_regclass('public.broker_sellers') AS broker_sellers,
               to_regclass('public.direct_sellers') AS direct_sellers
    """)).fetchone()

    found_columns = {row.column_name for row in columns}
    _referral_schema_available = (
        {"referral_code", "broker_seller_id", "direct_seller_id"}.issubset(found_columns)
        and bool(tables and tables.broker_sellers and tables.direct_sellers)
    )
    _referral_schema_checked = True
    return _referral_schema_available
