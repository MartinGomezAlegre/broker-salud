from __future__ import annotations

import re


PHONE_PATTERN = re.compile(r"^\+?[0-9 ()-]{8,20}$")


def _optional_clean(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None


def normalize_dni(value: str | None) -> str | None:
    clean = _optional_clean(value)
    if clean is None:
        return None

    digits = re.sub(r"\D", "", clean)
    if not re.fullmatch(r"\d{7,8}", digits):
        raise ValueError("Ingresa un DNI valido")
    return digits


def normalize_cuit(value: str | None) -> str | None:
    clean = _optional_clean(value)
    if clean is None:
        return None

    digits = re.sub(r"\D", "", clean)
    if not re.fullmatch(r"\d{11}", digits):
        raise ValueError("Ingresa un CUIT o CUIL valido")
    return digits


def normalize_phone(value: str | None) -> str | None:
    clean = _optional_clean(value)
    if clean is None:
        return None

    if not PHONE_PATTERN.fullmatch(clean):
        raise ValueError("Ingresa un telefono valido")
    return clean
