from __future__ import annotations

import re

COMMON_PASSWORDS = {
    "12345678",
    "123456789",
    "1234567890",
    "admin123",
    "admin1234",
    "qwerty123",
    "abc123456",  # pragma: allowlist secret
    "contrasena",
    "contrasenia",
    "password",
    "password1",
    "password123",
    "welcome123",
    "letmein123",
    "celdoctor",
    "celdoctor123",
    "martin123",
    "argentina123",
    "changeme123",
    "qwertyuiop",
}

LETTER_PATTERN = re.compile(r"[A-Za-z]")
NUMBER_PATTERN = re.compile(r"\d")


def validate_password_strength(password: str) -> str:
    clean = (password or "").strip()

    if len(clean) < 10:
        raise ValueError("La contrasena debe tener al menos 10 caracteres")

    if not LETTER_PATTERN.search(clean):
        raise ValueError("La contrasena debe incluir al menos una letra")

    if not NUMBER_PATTERN.search(clean):
        raise ValueError("La contrasena debe incluir al menos un numero")

    if clean.lower() in COMMON_PASSWORDS:
        raise ValueError("Elegi una contrasena menos comun")

    return clean
