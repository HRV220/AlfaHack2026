#!/usr/bin/env bash
# Создаёт .env из .env.example со случайными паролями и JWT-секретом (E02-06.6).
# Шаг необязательный: без .env стенд поднимается на учебных значениях по умолчанию (NFR-01).
# Запускайте до первого `make up`: пароли PostgreSQL и MinIO запоминаются в томах при первом старте.
# Использование: scripts/bootstrap.sh [--force] [--output ФАЙЛ]
set -euo pipefail

cd "$(dirname "$0")/.."
OUT=.env
FORCE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --force) FORCE=1 ;;
    --output) OUT=${2:?нужен путь к файлу}; shift ;;
    *) echo "Использование: $0 [--force] [--output ФАЙЛ]" >&2; exit 2 ;;
  esac
  shift
done

if [ -e "$OUT" ] && [ "$FORCE" -eq 0 ]; then
  echo "$OUT уже существует — оставляю без изменений (--force перезапишет)."
  exit 0
fi

random_hex() { head -c "$1" /dev/urandom | od -An -vtx1 | tr -d ' \n'; }

cp .env.example "$OUT"
set_var() {
  grep -q "^$1=" "$OUT" || { echo "В .env.example нет переменной $1" >&2; rm -f "$OUT"; exit 1; }
  sed "s|^$1=.*|$1=$2|" "$OUT" > "$OUT.tmp" && mv "$OUT.tmp" "$OUT"
}
for name in POSTGRES_PASSWORD DB_CORE_PASSWORD DB_KB_PASSWORD DB_BANK_PASSWORD DB_ML_PASSWORD \
  DB_DOCS_PASSWORD MINIO_ROOT_PASSWORD; do
  set_var "$name" "$(random_hex 16)"
done
set_var JWT_SECRET "$(random_hex 32)"
echo "Создан $OUT со случайными паролями и JWT-секретом."

if command -v docker >/dev/null 2>&1 \
  && docker volume ls -q 2>/dev/null | grep -qE '^cabinet_(postgres|minio)-data$'; then
  echo "ВНИМАНИЕ: тома стенда уже существуют, а пароли PostgreSQL и MinIO в них заданы при первом" >&2
  echo "старте. Чтобы новые пароли заработали, выполните: make down && docker volume rm" >&2
  echo "cabinet_postgres-data cabinet_minio-data (данные будут удалены)." >&2
fi
