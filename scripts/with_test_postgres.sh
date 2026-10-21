#!/usr/bin/env bash
# Поднимает одноразовый PostgreSQL+pgvector (образ из compose), выполняет команду, удаляет контейнер.
# Параметры для тестов: TEST_PG_HOST|PORT|USER|PASSWORD (по умолчанию localhost:55432, postgres).
set -euo pipefail

NAME=cabinet-migtest
IMAGE=$(grep -oE 'pgvector/pgvector:[^[:space:]]+' deploy/compose/compose.yaml | head -1)
PORT=${TEST_PG_PORT:-55432}

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=pg_admin_test -p "$PORT:5432" "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -U postgres -h 127.0.0.1 >/dev/null 2>&1 && break
  sleep 1
done
# pg_isready отвечает уже во время init-перезапуска: ждём устойчивого подключения.
sleep 2
docker exec "$NAME" pg_isready -U postgres -h 127.0.0.1 >/dev/null

"$@"
