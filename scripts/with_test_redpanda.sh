#!/usr/bin/env bash
# Поднимает одноразовый Redpanda (образ из compose) с Kafka API и Schema Registry на хосте,
# выполняет команду, удаляет контейнер.
# Параметры для тестов: TEST_KAFKA_PORT (по умолчанию 55092), TEST_SR_PORT (55081).
set -euo pipefail

NAME=cabinet-eventtest
IMAGE=$(grep -oE 'docker.redpanda.com/redpandadata/redpanda:[^[:space:]]+' deploy/compose/compose.yaml | head -1)
KAFKA_PORT=${TEST_KAFKA_PORT:-55092}
SR_PORT=${TEST_SR_PORT:-55081}

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "$KAFKA_PORT:$KAFKA_PORT" -p "$SR_PORT:$SR_PORT" "$IMAGE" \
  redpanda start --mode=dev-container --smp=1 --memory=768M --reserve-memory=0M --node-id=0 \
  --kafka-addr="0.0.0.0:$KAFKA_PORT" --advertise-kafka-addr="localhost:$KAFKA_PORT" \
  --schema-registry-addr="0.0.0.0:$SR_PORT" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 60); do
  docker exec "$NAME" rpk cluster health 2>/dev/null | grep -qE 'Healthy:.+true' && break
  sleep 1
done
docker exec "$NAME" rpk cluster health | grep -qE 'Healthy:.+true'

export KAFKA_BOOTSTRAP_SERVERS="localhost:$KAFKA_PORT"
export SCHEMA_REGISTRY_URL="http://localhost:$SR_PORT"
"$@"
