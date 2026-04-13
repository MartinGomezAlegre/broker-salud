# Capacity Testing Kit

Este kit sirve para medir tres cosas sin depender de herramientas externas:

- latencia y throughput HTTP de la web y de los endpoints criticos
- salud basica de la base de datos
- capacidad de insercion en una tabla temporal, sin ensuciar produccion

## 1. Benchmark HTTP

Ejemplo:

```bash
python tools/capacity/http_benchmark.py \
  --base-url https://celdoctor-waitlist.vercel.app \
  --scenarios tools/capacity/scenarios.example.json \
  --json-out tools/capacity/http-results.json \
  --markdown-out tools/capacity/http-results.md
```

Notas:

- Los headers del JSON aceptan variables de entorno con formato `${ADMIN_BEARER_TOKEN}`.
- Si queres probar endpoints autenticados, exporta el token antes de correr el script.
- Los escenarios se pueden duplicar y ajustar para simular distintos niveles de concurrencia.

## 2. Probe de base de datos

Read-only:

```bash
python tools/capacity/db_probe.py \
  --json-out tools/capacity/db-results.json \
  --markdown-out tools/capacity/db-results.md
```

Con benchmark de escritura temporal:

```bash
python tools/capacity/db_probe.py \
  --run-write-benchmark \
  --write-rows 5000 \
  --batch-size 250 \
  --json-out tools/capacity/db-results.json \
  --markdown-out tools/capacity/db-results.md
```

Notas:

- Usa `DATABASE_URL` desde el entorno o desde `.env`.
- El benchmark de escritura usa una `TEMP TABLE`, por lo que no deja basura persistente.
- Igual conviene correrlo primero en horario de baja carga.

## 3. Evidencia para entregar

Lo ideal es entregar:

1. `http-results.md`
2. `db-results.md`
3. un resumen corto con:
   - concurrencia testeada
   - p95 de endpoints criticos
   - tasas de error
   - filas actuales por tabla principal
   - throughput de insercion temporal

## 4. Escalon recomendado de pruebas

### Web publica

- 10 concurrentes / 100 requests
- 25 concurrentes / 250 requests
- 50 concurrentes / 500 requests

### Endpoints admin

- 5 concurrentes / 50 requests
- 10 concurrentes / 100 requests
- 20 concurrentes / 200 requests

### Base de datos

- snapshot read-only
- temp write benchmark con 1.000 filas
- temp write benchmark con 5.000 filas
- temp write benchmark con 10.000 filas

## 5. Regla practica para tu entrega

No conviene vender un numero solo de "usuarios soportados". Lo serio es informar algo asi:

- `La plataforma mantuvo 0% de errores y p95 menor a X ms con Y requests y Z concurrencia en endpoints publicos.`
- `Los endpoints admin criticos mantuvieron p95 menor a X ms con Y concurrencia.`
- `La base de datos respondio conteos criticos en X ms promedio y proceso N inserts temporales por segundo.`

Ese formato es mucho mas defendible frente a una auditoria tecnica.
