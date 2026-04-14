import argparse
import os
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


DDL = [
    """
    ALTER TABLE usuarios
      ADD COLUMN IF NOT EXISTS rol VARCHAR(30) NOT NULL DEFAULT 'cliente',
      ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true,
      ADD COLUMN IF NOT EXISTS dni VARCHAR(20),
      ADD COLUMN IF NOT EXISTS cuit VARCHAR(20),
      ADD COLUMN IF NOT EXISTS direccion VARCHAR(255),
      ADD COLUMN IF NOT EXISTS localidad VARCHAR(100),
      ADD COLUMN IF NOT EXISTS codigo_postal VARCHAR(20),
      ADD COLUMN IF NOT EXISTS provincia VARCHAR(100),
      ADD COLUMN IF NOT EXISTS pais VARCHAR(100);
    """,
    """
    ALTER TABLE suscripciones
      ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE;
    """,
    """
    ALTER TABLE suscripciones
      ALTER COLUMN estado TYPE VARCHAR(40);
    """,
    """
    ALTER TABLE planes
      ADD COLUMN IF NOT EXISTS descripcion TEXT,
      ADD COLUMN IF NOT EXISTS tipo VARCHAR(40) NOT NULL DEFAULT 'familiar',
      ADD COLUMN IF NOT EXISTS max_beneficiarios INT NOT NULL DEFAULT 0,
      ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT true;
    """,
    """
    UPDATE suscripciones
    SET fecha_vencimiento = COALESCE(fecha_vencimiento, fecha_fin, fecha_inicio + INTERVAL '30 days')
    WHERE fecha_vencimiento IS NULL;
    """,
    """
    CREATE TABLE IF NOT EXISTS tickets_soporte (
        id SERIAL PRIMARY KEY,
        usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        asunto VARCHAR(200) NOT NULL,
        descripcion TEXT,
        mensaje TEXT,
        categoria VARCHAR(50),
        estado VARCHAR(20) DEFAULT 'abierto',
        prioridad VARCHAR(20) DEFAULT 'normal',
        respuesta TEXT,
        admin_id INT,
        respondido_en TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS pagos (
        id SERIAL PRIMARY KEY,
        usuario_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
        suscripcion_id INT REFERENCES suscripciones(id) ON DELETE SET NULL,
        estado VARCHAR(30) DEFAULT 'aprobado',
        monto NUMERIC(12,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS beneficiarios (
        id SERIAL PRIMARY KEY,
        suscripcion_id INT NOT NULL REFERENCES suscripciones(id) ON DELETE CASCADE,
        nombre VARCHAR(100) NOT NULL,
        apellido VARCHAR(100) NOT NULL,
        dni VARCHAR(20) NOT NULL,
        fecha_nacimiento DATE NOT NULL,
        relacion VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS empresas (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(160) NOT NULL DEFAULT 'Empresa demo',
        activo BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS empleados_empresa (
        id SERIAL PRIMARY KEY,
        empresa_id INT NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
        nombre VARCHAR(120),
        email VARCHAR(180),
        activo BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS auditoria (
        id SERIAL PRIMARY KEY,
        accion VARCHAR(120) NOT NULL,
        datos_nuevos JSONB,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email ON usuarios(email);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios(rol);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_suscripciones_usuario_id ON suscripciones(usuario_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_suscripciones_estado ON suscripciones(estado);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_suscripciones_fecha_vencimiento ON suscripciones(fecha_vencimiento);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_tickets_usuario_id ON tickets_soporte(usuario_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_tickets_estado ON tickets_soporte(estado);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pagos_usuario_id ON pagos(usuario_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_beneficiarios_suscripcion_id ON beneficiarios(suscripcion_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_empleados_empresa_empresa_id ON empleados_empresa(empresa_id);
    """,
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the local performance database so it matches the current app core schema.")
    parser.add_argument("--database-url", help="Override DATABASE_URL.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv_file(repo_root / ".env")
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL no esta configurada.")

    import psycopg2

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for statement in DDL:
                cursor.execute(statement)
        connection.commit()

    print("Local performance DB prepared.")


if __name__ == "__main__":
    main()
