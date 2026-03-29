#!/bin/bash
# Проверяет GitLab на наличие задач для агентов и запускает нужный агент.
# Использует: claude CLI (должен быть в PATH)
# Запуск вручную: bash scripts/gitlab-check.sh
# Запуск через cron: */15 * * * * cd /path/to/project && bash scripts/gitlab-check.sh >> /tmp/gitlab-check.log 2>&1

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_JSON="$PROJECT_DIR/.mcp.json"

# Читаем конфигурацию из .mcp.json
if [ ! -f "$MCP_JSON" ]; then
    echo "[ERROR] Файл .mcp.json не найден: $MCP_JSON"
    exit 1
fi
read_env() {
    python3 -c "import json,sys; print(json.load(open('$MCP_JSON'))['env']['$1'])"
}
TOKEN=$(read_env GITLAB_TOKEN)
GITLAB_URL=$(read_env GITLAB_URL)
PROJECT_ID=$(read_env GITLAB_PROJECT_ID)
ASSIGNEE=$(read_env GITLAB_BOT_USERNAME)

BASE_URL="$GITLAB_URL/api/v4"
DISCUSSION_STATE="$PROJECT_DIR/runtime/discussion-state.json"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Проверяем задачи в GitLab..."

# Получаем все открытые задачи, назначенные на агента
ISSUES=$(curl -s \
    "${BASE_URL}/projects/${PROJECT_ID}/issues?state=opened&assignee_username=${ASSIGNEE}&per_page=50" \
    -H "PRIVATE-TOKEN: $TOKEN")

if [ $? -ne 0 ] || [ -z "$ISSUES" ]; then
    echo "[ERROR] Не удалось получить список issues"
    exit 1
fi

# Считаем задачи по типам.
# Для discussion проверяем стейт: задача нужна только если её updated_at
# изменился с момента последней обработки агентом (новые комментарии).
COUNT_DISCUSSION=$(echo "$ISSUES" | python3 -c "
import json, sys, os
issues = json.load(sys.stdin)
discussion = [i for i in issues if not i['labels'] or 'discussion' in [l.lower() for l in i['labels']]]
if not discussion:
    print(0)
    sys.exit()
state_file = '$DISCUSSION_STATE'
state = {}
if os.path.exists(state_file):
    try:
        state = json.load(open(state_file)).get('issues', {})
    except Exception:
        pass
count = 0
for i in discussion:
    iid = str(i['iid'])
    if iid not in state or state[iid]['updated_at'] < i['updated_at']:
        count += 1
print(count)
")

COUNT_WORKING=$(echo "$ISSUES" | python3 -c "
import json, sys
issues = json.load(sys.stdin)
count = sum(1 for i in issues if 'working' in [l.lower() for l in i['labels']])
print(count)
")

COUNT_REVIEW=$(echo "$ISSUES" | python3 -c "
import json, sys
issues = json.load(sys.stdin)
count = sum(1 for i in issues if 'review' in [l.lower() for l in i['labels']])
print(count)
")

echo "[INFO] discussion/new: $COUNT_DISCUSSION | working: $COUNT_WORKING | review: $COUNT_REVIEW"

# Приоритет: review > working > discussion
if [ "$COUNT_REVIEW" -gt 0 ]; then
    AGENT="reviewer"
    echo "[INFO] Найдено $COUNT_REVIEW задач(и) для review. Запускаю $AGENT..."
elif [ "$COUNT_WORKING" -gt 0 ]; then
    AGENT="worker"
    echo "[INFO] Найдено $COUNT_WORKING задач(и) для working. Запускаю $AGENT..."
elif [ "$COUNT_DISCUSSION" -gt 0 ]; then
    AGENT="discussion"
    echo "[INFO] Найдено $COUNT_DISCUSSION задач(и) для discussion. Запускаю $AGENT..."
else
    echo "[INFO] Нет задач для обработки. Агент не запускается."
    exit 0
fi

# Запускаем агента через claude CLI
cd "$PROJECT_DIR"
echo "[INFO] Запускаю: claude -p \"Запусти агент $AGENT\""
claude -p "Запусти агент $AGENT"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Агент завершил работу."
