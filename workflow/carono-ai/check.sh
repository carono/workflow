#!/usr/bin/env bash
set -euo pipefail

# Переходим в корень проекта (на 2 уровня выше папки бота: workflow/{bot-name}/ -> ../.. -> корень)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# ─── Блок 0: Режим отладки ─────────────────────────────────────────────────────

VERBOSE=false
for arg in "$@"; do
    if [ "$arg" = "--verbose" ]; then
        VERBOSE=true
        break
    fi
done

export VERBOSE

verbose_log() {
    if [ "$VERBOSE" = true ]; then
        echo "[VERBOSE] $*" >&2
    fi
}

verbose_log "=== check.sh запущен в режиме verbose ==="
verbose_log "Аргументы: $*"
verbose_log "Рабочая директория: $(pwd)"

# ─── Блок 1: Получение задач ───────────────────────────────────────────────────

# Читаем конфигурацию бота
# SCRIPT_DIR уже указывает на workflow/{bot-name}/, извлекаем имя
BOT_NAME=$(basename "$SCRIPT_DIR")

verbose_log "BOT_NAME: $BOT_NAME"

if [ -z "$BOT_NAME" ]; then
    echo "Ошибка: нет папок в workflow/. Запусти агента configure." >&2
    exit 1
fi

# Параметры YouGile из .env файла бота
ENV_FILE="workflow/${BOT_NAME}/.env"
verbose_log "Попытка прочитать .env из: $ENV_FILE"

if [ -f "$ENV_FILE" ]; then
    verbose_log "Файл .env найден, читаем YOUGILE_API_KEY"
    set -a
    . "$ENV_FILE"
    set +a
    verbose_log "YOUGILE_API_KEY загружен (длина: ${#YOUGILE_API_KEY})"
else
    verbose_log "Файл .env не найден, пробуем переменную окружения"
fi

if [ -z "${YOUGILE_API_KEY:-}" ]; then
    echo "Ошибка: YOUGILE_API_KEY не задан и не найден в $ENV_FILE" >&2
    exit 1
fi

export YOUGILE_API_KEY

verbose_log "Получаем список проектов из YouGile API..."
verbose_log "GET https://yougile.com/api-v2/projects"

# Получаем все задачи с доски «разработка» проекта WORKFLOW
ISSUES_JSON=$(python3 -c "
import json, os, urllib.request, sys

verbose = os.environ.get('VERBOSE', 'false') == 'true'

def log(msg):
    if verbose:
        print(f'[VERBOSE] {msg}', file=sys.stderr)

api_key = os.environ['YOUGILE_API_KEY']
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def api_get(url):
    log(f'GET {url}')
    req = urllib.request.Request(url)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            log(f'Ответ: {resp.status}, содержимое: {len(json.dumps(data))} символов')
            return data
    except Exception as e:
        log(f'Ошибка запроса: {e}')
        return None

# Находим проект WORKFLOW
log('Ищем проект WORKFLOW...')
projects = api_get('https://yougile.com/api-v2/projects')
if not projects:
    print('[]')
    sys.exit(0)

log(f'Найдено проектов: {projects.get(\"paging\", {}).get(\"count\", 0)}')
workflow_proj = next((p for p in projects['content'] if p['title'] == 'WORKFLOW'), None)
if not workflow_proj:
    log('Проект WORKFLOW не найден')
    print('[]')
    sys.exit(0)
log(f'Проект WORKFLOW найден, id: {workflow_proj[\"id\"]}')

# Находим доску «Разработка»
log('Ищем доску Разработка...')
boards = api_get(f'https://yougile.com/api-v2/boards?projectId={workflow_proj[\"id\"]}')
if not boards:
    print('[]')
    sys.exit(0)
log(f'Найдено досок: {boards.get(\"paging\", {}).get(\"count\", 0)}')
dev_board = next((b for b in boards['content'] if b['title'] == 'Разработка'), None)
if not dev_board:
    log('Доска Разработка не найдена')
    print('[]')
    sys.exit(0)
log(f'Доска Разработка найдена, id: {dev_board[\"id\"]}')

# Находим колонки
log('Получаем колонки...')
columns = api_get(f'https://yougile.com/api-v2/columns?boardId={dev_board[\"id\"]}')
if not columns:
    print('[]')
    sys.exit(0)
col_map = {c['title']: c['id'] for c in columns['content']}
log(f'Найдено колонок: {len(col_map)} -> {list(col_map.keys())}')

# Собираем задачи из всех колонок
all_tasks = []
for col_name, col_id in col_map.items():
    log(f'Получаем задачи из колонки \"{col_name}\" ({col_id})...')
    data = api_get(f'https://yougile.com/api-v2/task-list?columnId={col_id}&limit=1000')
    if data:
        count = len(data.get('content', []))
        log(f'  Задач в колонке: {count}')
        for task in data['content']:
            task['_column'] = col_name
            all_tasks.append(task)
    else:
        log(f'  Ошибка получения задач из колонки \"{col_name}\"')

log(f'Всего задач собрано: {len(all_tasks)}')
print(json.dumps(all_tasks, ensure_ascii=False))
" 2>&1)

# Если verbose, отделим логи от JSON
if [ "$VERBOSE" = true ]; then
    # Последняя строка — это JSON, остальное — логи
    ISSUES_JSON=$(echo "$ISSUES_JSON" | tail -1)
fi

verbose_log "Получено задач (JSON длина): ${#ISSUES_JSON}"

# Сохраняем JSON во временный файл — прямая интерполяция '''$ISSUES_JSON'''
# ломается если в данных есть одинарные кавычки (названия задач и т.п.)
ISSUES_TMP=$(mktemp)
trap "rm -f '$ISSUES_TMP'" EXIT
printf '%s' "$ISSUES_JSON" > "$ISSUES_TMP"
verbose_log "JSON сохранён во временный файл: $ISSUES_TMP"

# ─── Блок 2: Подсчёт задач по каждому агенту ───────────────────────────────────

verbose_log "Определяем ID пользователя Carono AI..."

# ID агента Carono AI
AI_USER_ID=$(python3 -c "
import json, os, urllib.request, sys
api_key = os.environ['YOUGILE_API_KEY']
req = urllib.request.Request('https://yougile.com/api-v2/users')
req.add_header('Authorization', f'Bearer {api_key}')
req.add_header('Content-Type', 'application/json')
with urllib.request.urlopen(req, timeout=30) as resp:
    users = json.loads(resp.read())
ai_user = next((u for u in users['content'] if 'carono' in u.get('email', '').lower() or 'ai' in u.get('realName', '').lower()), None)
if ai_user:
    print(ai_user['id'])
else:
    print('')
" 2>/dev/null || echo "")

verbose_log "AI_USER_ID: $AI_USER_ID"

verbose_log "Подсчёт задач для discussion..."
COUNT_DISCUSSION=$(python3 -c "
import json, sys
issues = json.load(open('$ISSUES_TMP'))
ai_user = '$AI_USER_ID'
verbose = $( [ "$VERBOSE" = true ] && echo "True" || echo "False" )
# Обсуждение: задачи в колонке 'Обсуждение', неназначенные ИЛИ назначенные на AI
count = sum(
    1 for i in issues
    if i.get('_column') == 'Обсуждение' and (
        not i.get('assigned') or
        (ai_user and ai_user in i.get('assigned', []))
    )
)
if verbose:
    matching = [i for i in issues if i.get('_column') == 'Обсуждение' and (not i.get('assigned') or (ai_user and ai_user in i.get('assigned', [])))]
    for t in matching:
        print(f'  [discussion] {t.get(\"idTaskProject\", \"?\")} - {t.get(\"title\", \"\")}', file=sys.stderr)
print(count)
")

verbose_log "COUNT_DISCUSSION: $COUNT_DISCUSSION"

verbose_log "Подсчёт задач для worker..."
COUNT_WORKER=$(python3 -c "
import json, sys
issues = json.load(open('$ISSUES_TMP'))
ai_user = '$AI_USER_ID'
verbose = $( [ "$VERBOSE" = true ] && echo "True" || echo "False" )
# Разработка: задачи в колонке 'Разработка', назначенные на AI
count = sum(
    1 for i in issues
    if i.get('_column') == 'Разработка' and
    ai_user in i.get('assigned', [])
)
if verbose:
    matching = [i for i in issues if i.get('_column') == 'Разработка' and ai_user in i.get('assigned', [])]
    for t in matching:
        print(f'  [worker] {t.get(\"idTaskProject\", \"?\")} - {t.get(\"title\", \"\")}', file=sys.stderr)
print(count)
")

verbose_log "COUNT_WORKER: $COUNT_WORKER"

# Reviewer: колонка «на ревью» может не существовать — проверяем
HAS_REVIEW_COLUMN=$(python3 -c "
import json
issues = json.load(open('$ISSUES_TMP'))
print('yes' if any(i.get('_column') == 'на ревью' for i in issues) else 'no')
")

verbose_log "HAS_REVIEW_COLUMN: $HAS_REVIEW_COLUMN"

if [ "$HAS_REVIEW_COLUMN" = "yes" ]; then
    verbose_log "Подсчёт задач для reviewer..."
    COUNT_REVIEWER=$(python3 -c "
import json, sys
issues = json.load(open('$ISSUES_TMP'))
ai_user = '$AI_USER_ID'
verbose = $( [ "$VERBOSE" = true ] && echo "True" || echo "False" )
count = sum(
    1 for i in issues
    if i.get('_column') == 'на ревью' and
    ai_user in i.get('assigned', [])
)
if verbose:
    matching = [i for i in issues if i.get('_column') == 'на ревью' and ai_user in i.get('assigned', [])]
    for t in matching:
        print(f'  [reviewer] {t.get(\"idTaskProject\", \"?\")} - {t.get(\"title\", \"\")}', file=sys.stderr)
print(count)
")
    verbose_log "COUNT_REVIEWER: $COUNT_REVIEWER"
else
    COUNT_REVIEWER=0
    verbose_log "COUNT_REVIEWER: 0 (колонка 'на ревью' отсутствует)"
fi

# ─── Блок 3: Определение NEEDED ────────────────────────────────────────────────

NEEDED_DISCUSSION="no"
[ "$COUNT_DISCUSSION" -gt 0 ] && NEEDED_DISCUSSION="yes"

NEEDED_WORKER="no"
[ "$COUNT_WORKER" -gt 0 ] && NEEDED_WORKER="yes"

NEEDED_REVIEWER="no"
[ "$COUNT_REVIEWER" -gt 0 ] && NEEDED_REVIEWER="yes"

# ─── Блок 4: Вывод таблицы (режим по умолчанию) ────────────────────────────────

# Отфильтруем --verbose из аргументов для определения режима
CLEAN_ARGS=()
for arg in "$@"; do
    if [ "$arg" != "--verbose" ]; then
        CLEAN_ARGS+=("$arg")
    fi
done
MODE="${CLEAN_ARGS[0]:-status}"

if [ "$MODE" = "status" ]; then
    verbose_log "Режим: вывод таблицы состояния"
    printf "%-15s %-8s %s\n" "AGENT" "TASKS" "NEEDED"
    printf "%-15s %-8s %s\n" "discussion" "$COUNT_DISCUSSION" "$NEEDED_DISCUSSION"
    printf "%-15s %-8s %s\n" "worker" "$COUNT_WORKER" "$NEEDED_WORKER"
    if [ "$HAS_REVIEW_COLUMN" = "yes" ]; then
        printf "%-15s %-8s %s\n" "reviewer" "$COUNT_REVIEWER" "$NEEDED_REVIEWER"
    fi
    verbose_log "Таблица выведена, завершение."
    exit 0
fi

# ─── Блок 5: Запуск агентов ────────────────────────────────────────────────────

if [ "$MODE" = "--run" ]; then
    TARGET="${CLEAN_ARGS[1]:-}"
    if [ -z "$TARGET" ]; then
        echo "Укажи агента: --run <agent|all>" >&2
        exit 1
    fi

    verbose_log "Режим: запуск агентов, цель: $TARGET"

    run_agent() {
        local agent="$1"
        verbose_log "Запуск агента: $agent"
        echo "[start] $agent"
        if claude -p "Выполни свои задачи" --agent "$agent" > "logs/${agent}-$(date +%s).log" 2>&1; then
            echo "[ok]    $agent"
            verbose_log "Агент $agent завершился успешно"
        else
            echo "[fail]  $agent (см. logs/)"
            verbose_log "Агент $agent завершился с ошибкой, лог: logs/${agent}-*.log"
        fi
    }

    mkdir -p logs
    verbose_log "Директория logs создана/проверена"

    if [ "$TARGET" = "all" ]; then
        PIDS=()
        verbose_log "Запуск всех агентов с NEEDED=yes..."
        for agent_needed in \
            "discussion:$NEEDED_DISCUSSION" \
            "worker:$NEEDED_WORKER" \
            "reviewer:$NEEDED_REVIEWER"; do
            agent="${agent_needed%%:*}"
            needed="${agent_needed##*:}"
            verbose_log "  $agent: NEEDED=$needed"
            if [ "$needed" = "yes" ]; then
                verbose_log "  -> Запускаем $agent в фоне"
                run_agent "$agent" &
                PIDS+=($!)
            else
                verbose_log "  -> Пропускаем $agent"
            fi
        done
        verbose_log "Ожидание завершения ${#PIDS[@]} агентов..."
        for pid in "${PIDS[@]}"; do
            wait "$pid"
        done
        verbose_log "Все агенты завершены"
    else
        verbose_log "Запуск конкретного агента: $TARGET"
        run_agent "$TARGET"
    fi

    exit 0
fi

echo "Использование: $0 [--run <agent|all>]" >&2
exit 1
