#!/usr/bin/env bash
# Приёмочная проверка стенда `core` (E02-06.7): ждёт готовности контейнеров и проверяет сервисы.
# Использование: scripts/smoke.sh [--up]
#   --up              сначала поднять стенд (`up -d --build`) и замерить время холодного старта
# Переменные: SMOKE_SKIP_LLM=1 — не поднимать и не проверять Ollama (машина с памятью < 14 ГБ);
#             SMOKE_TIMEOUT — сколько секунд ждать готовности (по умолчанию 900);
#             SMOKE_PROJECT — отдельное имя проекта Compose: свои контейнеры и тома, существующий
#             стенд и его данные не затрагиваются (порты на хосте должны быть свободны).
set -uo pipefail

export MSYS_NO_PATHCONV=1 # Git Bash на Windows иначе портит пути в аргументах docker exec
cd "$(dirname "$0")/.."
COMPOSE="docker compose ${SMOKE_PROJECT:+-p $SMOKE_PROJECT} --project-directory . -f deploy/compose/compose.yaml --profile core"
SKIP_LLM=${SMOKE_SKIP_LLM:-0}
TIMEOUT=${SMOKE_TIMEOUT:-900}
LLM_MODEL=${LLM_MODEL:-qwen2.5:7b-instruct-q4_K_M}
START=$(date +%s)

if [ "${1:-}" = "--up" ]; then
  services=$($COMPOSE config --services)
  [ "$SKIP_LLM" = 1 ] && services=$(echo "$services" | grep -vx ollama)
  # shellcheck disable=SC2086
  $COMPOSE up -d --build $services || { echo "Не удалось поднять стенд" >&2; exit 1; }
fi

# --- Ожидание: рабочие контейнеры healthy, разовые (init, minio-init…) завершились кодом 0 ---
pending() {
  local line service state health code
  $COMPOSE ps -a --format '{{.Service}}|{{.State}}|{{.Health}}|{{.ExitCode}}' | while IFS='|' read -r service state health code; do
    [ "$SKIP_LLM" = 1 ] && [ "$service" = ollama ] && continue
    case "$state" in
      running) [ -z "$health" ] || [ "$health" = healthy ] || echo "$service: $health" ;;
      exited) [ "$code" = 0 ] || echo "$service: завершился с кодом $code" ;;
      restarting|dead) echo "$service: аварийное состояние $state" ;;
      *) echo "$service: $state" ;;
    esac
  done
}

echo "Жду готовности контейнеров (до ${TIMEOUT} с)..."
while true; do
  waiting=$(pending)
  [ -z "$waiting" ] && break
  if echo "$waiting" | grep -qE "завершился с кодом|аварийное состояние"; then
    echo "Контейнер остановился с ошибкой или перезапускается по кругу:" >&2; echo "$waiting" >&2; exit 1
  fi
  if [ $(( $(date +%s) - START )) -ge "$TIMEOUT" ]; then
    echo "Не дождался за ${TIMEOUT} с:" >&2; echo "$waiting" >&2; exit 1
  fi
  sleep 5
done
READY=$(( $(date +%s) - START ))

# --- Проверки сервисов ---
failed=0
check() {
  local name=$1; shift
  if "$@" >/dev/null 2>&1; then echo "  ok    $name"; else echo "  FAIL  $name"; failed=$((failed + 1)); fi
}
count_at_least() { [ "$(eval "$1")" -ge "$2" ]; }
healthy() { [ "$($COMPOSE ps --format '{{.Health}}' "$1")" = healthy ]; }

echo "Проверки:"
for svc in core-api ml-service bank-sim web; do
  check "/health $svc" $COMPOSE exec -T "$svc" python -m cabinet_common.entrypoint --healthcheck
done
check "Schema Registry: 11 схем" count_at_least \
  "$COMPOSE exec -T redpanda rpk registry subject list | grep -c -- '-value'" 11
check "Redpanda: 22 топика (11 + DLQ)" count_at_least \
  "$COMPOSE exec -T redpanda rpk topic list | grep -cE '^(bank|document|profile|cashflow|application|decision|recommendation)\.'" 22
check "PostgreSQL: seed реестра (>= 3 карточки)" count_at_least \
  "$COMPOSE exec -T postgres sh -c 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"SELECT count(*) FROM core.registry_snapshot\"'" 3
check "MinIO" $COMPOSE exec -T minio curl -fsS http://localhost:9000/minio/health/live
check "MLflow" curl -fsS "http://127.0.0.1:${MLFLOW_PORT:-5000}/health"
check "Edge (HTTPS)" curl -fsSk "https://127.0.0.1:${EDGE_HTTPS_PORT:-8443}/edge/health"
check "ClamAV" healthy clamav
if [ "$SKIP_LLM" = 1 ]; then
  echo "  --    Ollama: пропущена (SMOKE_SKIP_LLM=1)"
else
  check "Ollama: модель $LLM_MODEL" sh -c "$COMPOSE exec -T ollama ollama list | grep -q '$LLM_MODEL'"
fi

echo
if [ "$failed" -eq 0 ]; then
  echo "Стенд готов за ${READY} с$([ "$SKIP_LLM" = 1 ] && echo ' (без LLM)'). Все проверки пройдены."
else
  echo "Провалено проверок: $failed (стенд готов за ${READY} с)." >&2
  exit 1
fi
