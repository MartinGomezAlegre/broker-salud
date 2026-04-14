import argparse
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def chunked(values, size):
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a large local dataset for core capacity tests.")
    parser.add_argument("--database-url", help="Override DATABASE_URL.")
    parser.add_argument("--users", type=int, default=100000, help="How many synthetic users to create.")
    parser.add_argument("--batch-size", type=int, default=2000, help="Batch size for inserts.")
    parser.add_argument("--reset-generated", action="store_true", help="Delete previously generated perf_* users and related rows first.")
    parser.add_argument("--ticket-ratio", type=float, default=0.08, help="Share of users that get support tickets.")
    parser.add_argument("--beneficiary-ratio", type=float, default=0.15, help="Share of active family users that get beneficiaries.")
    parser.add_argument("--payment-ratio", type=float, default=0.85, help="Share of subscriptions that get a payment row.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    load_dotenv_file(repo_root / ".env")
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL no esta configurada.")

    import psycopg2
    from psycopg2.extras import execute_values

    from app.auth import hashear_password

    started = time.perf_counter()
    password_hash = hashear_password("PerfTest123!")
    today = date.today()
    random.seed(42)

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM planes")
            plan_count = cursor.fetchone()[0]
            if plan_count == 0:
                cursor.execute(
                    """
                    INSERT INTO planes (nombre, descripcion, precio_mensual, max_beneficiarios, activo)
                    VALUES
                        ('Individual', 'Plan individual de prueba', 5000, 1, true),
                        ('Familiar', 'Plan familiar de prueba', 12500, 4, true)
                    """
                )

            cursor.execute("SELECT id, max_beneficiarios FROM planes WHERE activo = true ORDER BY id")
            planes = cursor.fetchall()
            if not planes:
                raise SystemExit("No hay planes activos para asociar suscripciones.")

            if args.reset_generated:
                cursor.execute(
                    """
                    DELETE FROM beneficiarios
                    WHERE suscripcion_id IN (
                        SELECT s.id
                        FROM suscripciones s
                        JOIN usuarios u ON u.id = s.usuario_id
                        WHERE u.email LIKE 'perf_user_%@example.com'
                    )
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM pagos
                    WHERE usuario_id IN (
                        SELECT id FROM usuarios WHERE email LIKE 'perf_user_%@example.com'
                    )
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM tickets_soporte
                    WHERE usuario_id IN (
                        SELECT id FROM usuarios WHERE email LIKE 'perf_user_%@example.com'
                    )
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM suscripciones
                    WHERE usuario_id IN (
                        SELECT id FROM usuarios WHERE email LIKE 'perf_user_%@example.com'
                    )
                    """
                )
                cursor.execute("DELETE FROM usuarios WHERE email LIKE 'perf_user_%@example.com'")
                connection.commit()

            cursor.execute(
                """
                INSERT INTO usuarios (nombre, apellido, email, telefono, fecha_nacimiento, password_hash, rol, activo, dni, cuit, direccion, localidad, codigo_postal, provincia, pais)
                VALUES (%s, %s, %s, %s, %s, %s, 'admin', true, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                """,
                (
                    "Perf",
                    "Admin",
                    "perf_admin@example.com",
                    "1100000000",
                    date(1990, 1, 1),
                    password_hash,
                    "30000000001",
                    "30000000001",
                    "Calle Test 1",
                    "CABA",
                    "1000",
                    "Buenos Aires",
                    "Argentina",
                ),
            )
            connection.commit()

            users_to_insert = []
            for index in range(args.users):
                seq = index + 1
                email = f"perf_user_{seq:06d}@example.com"
                birth = date(1980 + (seq % 25), ((seq % 12) + 1), ((seq % 27) + 1))
                users_to_insert.append(
                    (
                        f"Perf{seq}",
                        f"User{seq}",
                        email,
                        f"11{seq:08d}"[-10:],
                        birth,
                        password_hash,
                        "cliente",
                        True,
                        f"{20000000 + seq}",
                        f"{30000000000 + seq}",
                        f"Av Test {seq}",
                        "CABA" if seq % 2 == 0 else "General Rodriguez",
                        f"{1000 + (seq % 9000)}",
                        "Buenos Aires",
                        "Argentina",
                    )
                )

            for batch in chunked(users_to_insert, args.batch_size):
                execute_values(
                    cursor,
                    """
                    INSERT INTO usuarios
                        (nombre, apellido, email, telefono, fecha_nacimiento, password_hash, rol, activo, dni, cuit, direccion, localidad, codigo_postal, provincia, pais)
                    VALUES %s
                    ON CONFLICT (email) DO NOTHING
                    """,
                    batch,
                    page_size=args.batch_size,
                )
                connection.commit()

            cursor.execute("SELECT id, email FROM usuarios WHERE email LIKE 'perf_user_%@example.com' ORDER BY id")
            users = cursor.fetchall()

            subscriptions = []
            beneficiary_candidates = []
            ticket_rows = []
            payment_rows = []

            for user_id, email in users:
                plan_id, max_beneficiarios = random.choice(planes)
                state_roll = random.random()
                if state_roll < 0.72:
                    estado = "activa"
                elif state_roll < 0.84:
                    estado = "cancelacion_programada"
                elif state_roll < 0.94:
                    estado = "pendiente_pago"
                elif state_roll < 0.97:
                    estado = "vencida"
                else:
                    estado = "cancelada"

                fecha_inicio = today - timedelta(days=random.randint(0, 365))
                fecha_vencimiento = fecha_inicio + timedelta(days=30)
                precio = 5000 if max_beneficiarios == 1 else 12500
                subscriptions.append((user_id, plan_id, estado, fecha_inicio, fecha_vencimiento, precio, fecha_inicio))

                if max_beneficiarios and max_beneficiarios > 1 and estado in {"activa", "cancelacion_programada"} and random.random() < args.beneficiary_ratio:
                    beneficiary_candidates.append((user_id, max_beneficiarios))

                if random.random() < args.ticket_ratio:
                    ticket_rows.append(
                        (
                            user_id,
                            "Consulta operativa",
                            "Necesito ayuda con mi cuenta y seguimiento.",
                            "Necesito ayuda con mi cuenta y seguimiento.",
                            "abierto" if random.random() < 0.6 else "respondido",
                            "alta" if random.random() < 0.1 else "normal",
                        )
                    )

            for batch in chunked(subscriptions, args.batch_size):
                execute_values(
                    cursor,
                    """
                    INSERT INTO suscripciones
                        (usuario_id, plan_id, estado, fecha_inicio, fecha_vencimiento, precio_pagado, created_at)
                    VALUES %s
                    """,
                    batch,
                    page_size=args.batch_size,
                )
                connection.commit()

            cursor.execute(
                """
                SELECT s.id, s.usuario_id, p.max_beneficiarios
                FROM suscripciones s
                JOIN planes p ON p.id = s.plan_id
                JOIN usuarios u ON u.id = s.usuario_id
                WHERE u.email LIKE 'perf_user_%@example.com'
                  AND s.estado IN ('activa', 'cancelacion_programada')
                """
            )
            suscripciones_rows = cursor.fetchall()
            subs_by_user = {user_id: (suscripcion_id, max_beneficiarios or 1) for suscripcion_id, user_id, max_beneficiarios in suscripciones_rows}

            beneficiaries = []
            for user_id, max_beneficiarios in beneficiary_candidates:
                sub = subs_by_user.get(user_id)
                if not sub:
                    continue
                suscripcion_id, max_benef = sub
                extras = min(max_benef - 1, random.randint(1, 3))
                for idx in range(extras):
                    seq = user_id * 10 + idx
                    beneficiaries.append(
                        (
                            suscripcion_id,
                            f"Benef{seq}",
                            f"User{seq}",
                            f"{40000000 + seq}",
                            date(2000 + (seq % 20), ((seq % 12) + 1), ((seq % 27) + 1)),
                            "familiar",
                        )
                    )

            for batch in chunked(beneficiaries, args.batch_size):
                execute_values(
                    cursor,
                    """
                    INSERT INTO beneficiarios
                        (suscripcion_id, nombre, apellido, dni, fecha_nacimiento, relacion)
                    VALUES %s
                    """,
                    batch,
                    page_size=args.batch_size,
                )
                connection.commit()

            if ticket_rows:
                for batch in chunked(ticket_rows, args.batch_size):
                    execute_values(
                        cursor,
                        """
                        INSERT INTO tickets_soporte
                            (usuario_id, asunto, descripcion, mensaje, estado, prioridad)
                        VALUES %s
                        """,
                        batch,
                        page_size=args.batch_size,
                    )
                    connection.commit()

            if args.payment_ratio > 0:
                cursor.execute(
                    """
                    SELECT s.id, s.usuario_id, COALESCE(s.precio_pagado, 0)
                    FROM suscripciones s
                    JOIN usuarios u ON u.id = s.usuario_id
                    WHERE u.email LIKE 'perf_user_%@example.com'
                    """
                )
                for suscripcion_id, user_id, precio in cursor.fetchall():
                    if random.random() <= args.payment_ratio:
                        payment_rows.append((user_id, suscripcion_id, "aprobado", precio))

                for batch in chunked(payment_rows, args.batch_size):
                    execute_values(
                        cursor,
                        """
                        INSERT INTO pagos (usuario_id, suscripcion_id, estado, monto)
                        VALUES %s
                        """,
                        batch,
                        page_size=args.batch_size,
                    )
                    connection.commit()

    elapsed = round(time.perf_counter() - started, 2)
    print(
        f"Seed completo: {args.users} usuarios sinteticos, {len(subscriptions)} suscripciones, "
        f"{len(beneficiaries)} beneficiarios, {len(ticket_rows)} tickets y {len(payment_rows)} pagos en {elapsed}s."
    )
    print("Credenciales de prueba:")
    print("  admin: perf_admin@example.com / PerfTest123!")
    print("  usuario: perf_user_000001@example.com / PerfTest123!")


if __name__ == "__main__":
    main()
