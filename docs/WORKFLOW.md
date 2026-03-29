# Воркфлоу проекта

Этот документ — операционный мануал для агентов. Здесь описано как взаимодействовать с трекером задач, менять статусы, работать с кодом в данном конкретном проекте.

---

## Трекер задач

**Сервис:** GitLab
**Инстанс:** `https://git.binet.pro`
**Проект:** `kabinet/lms` (project_id: `1`)

### Чтение конфигурации

Все параметры — в `.mcp.json` в корне проекта:

```bash
TOKEN=$(cat .mcp.json | python3 -c "import json,sys; d=json.load(sys.stdin)['env']; print(d['GITLAB_TOKEN'])")
GITLAB_URL=$(cat .mcp.json | python3 -c "import json,sys; d=json.load(sys.stdin)['env']; print(d['GITLAB_URL'])")
PROJECT_ID=$(cat .mcp.json | python3 -c "import json,sys; d=json.load(sys.stdin)['env']; print(d['GITLAB_PROJECT_ID'])")
BOT_USERNAME=$(cat .mcp.json | python3 -c "import json,sys; d=json.load(sys.stdin)['env']; print(d['GITLAB_BOT_USERNAME'])")
BOT_USER_ID=$(cat .mcp.json | python3 -c "import json,sys; d=json.load(sys.stdin)['env']; print(d['GITLAB_BOT_USER_ID'])")
```

### Учётная запись агента

- Логин: `GITLAB_BOT_USERNAME` из `.mcp.json`
- ID: `GITLAB_BOT_USER_ID` из `.mcp.json`
- Твои задачи: issues, назначенные на `$BOT_USERNAME`

---

## Жизненный цикл задачи

```
новая (без лейбла) → discussion → ready → [человек вручную] → working → review → closed
```

### Статусы задачи

| Статус | Лейбл в GitLab | Кто переводит |
|--------|----------------|---------------|
| Новая | *(нет лейбла)* | создаётся без лейбла |
| В обсуждении | `discussion` | агент-обсуждения |
| Готова к разработке | `ready` | агент-обсуждения |
| В разработке | `working` | человек вручную |
| На ревью | `review` | агент-разработчик |
| Готово | `done` + issue закрыт | агент-ревьюер |

---

## Операции с задачами

### Проверить репозиторий

Перед началом работы убедись что находишься в правильном репозитории:

```bash
git remote -v
```

Remote должен указывать на `git.binet.pro`. Если хост другой — останови работу и сообщи об этом.

### Получить список своих задач

```bash
curl -s "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/issues?state=opened&assignee_username=${BOT_USERNAME}&per_page=50" \
  -H "PRIVATE-TOKEN: $TOKEN"
```

### Получить задачу по IID

Через MCP: `mcp__gitlab__get_issue` с параметром `project_id: kabinet/lms`.

Через API:
```bash
curl -s "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/issues/{IID}" \
  -H "PRIVATE-TOKEN: $TOKEN"
```

### Изменить статус задачи

```bash
curl -s -X PUT "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/issues/{IID}" \
  -H "PRIVATE-TOKEN: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"labels": "<LABEL_NAME>"}'
```

Подставь нужный лейбл из таблицы статусов выше.

### Закрыть задачу

```bash
curl -s -X PUT "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/issues/{IID}" \
  -H "PRIVATE-TOKEN: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"state_event": "close", "labels": "done"}'
```

### Читать комментарии к задаче

Через MCP: `mcp__gitlab__get_workitem_notes` с `project_id: kabinet/lms`.

### Написать комментарий к задаче

Через MCP: `mcp__gitlab__create_workitem_note` с `project_id: kabinet/lms`.

---

## Работа с кодом

### Проверка репозитория

Remote должен указывать на `git.binet.pro` (см. выше).

### Ветки

- Создавать от: `prod`
- Формат имени: `feature/issue-{IID}-{short-slug}`
- Целевая ветка для код-ревью: `prod`

### Создание код-ревью (MR)

Через MCP: `mcp__gitlab__create_merge_request`:
- `id`: `kabinet/lms`
- `source_branch`: `feature/issue-{IID}-{short-slug}`
- `target_branch`: `prod`
- `title`: заголовок из задачи
- `description`: краткое summary + `Closes #{IID}` + ссылка из описания задачи если есть

### Поиск код-ревью по задаче

1. По ветке `feature/issue-{IID}-*`:
```bash
curl -s "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/merge_requests?state=opened&source_branch=feature/issue-{IID}" \
  -H "PRIVATE-TOKEN: $TOKEN"
```
2. Или через `mcp__gitlab__search` (scope: `merge_requests`, поиск по `Closes #{IID}`)

### Читать код-ревью

- Данные MR: `mcp__gitlab__get_merge_request`
- Диффы: `mcp__gitlab__get_merge_request_diffs`
- Комментарии к MR:
```bash
curl -s "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/merge_requests/{MR_IID}/notes" \
  -H "PRIVATE-TOKEN: $TOKEN"
```

### Формат коммита

```
feat: <описание изменений>

Closes #<IID>
Ref: <ссылка из описания задачи если есть>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

