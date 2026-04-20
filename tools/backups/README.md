# Backups de PostgreSQL

Este directorio agrega una segunda capa de respaldo para CELDOCTOR ademas del sistema nativo de backups de Railway.

## Estrategia recomendada

1. **Backups nativos de Railway**
   - activar schedule diario, semanal y mensual sobre el volumen del Postgres
   - crear un backup manual antes de cada migracion importante
   - bloquear snapshots relevantes para no borrarlos por error

2. **Backups logicos propios**
   - correr `backup_postgres.py` con `pg_dump`
   - guardar el dump fuera de Railway si queres una capa extra
   - cada backup genera:
     - `.dump`
     - `.sha256`
     - `.json` con metadata

## Crear un backup

```bash
python tools/backups/backup_postgres.py --label pre_migracion
```

Tambien podes usar:

```bash
set DATABASE_URL=postgresql://...
python tools/backups/backup_postgres.py --output-dir backups
```

## Restaurar un backup

```bash
python tools/backups/restore_postgres.py backups/celdoctor_pre_migracion_20260419_120000.dump --yes
```

## Importante

- `pg_dump` y `pg_restore` deben estar instalados en la maquina o runner que ejecute estos scripts.
- El restore es una operacion destructiva sobre la base destino.
- Proba siempre primero en staging cuando sea posible.
