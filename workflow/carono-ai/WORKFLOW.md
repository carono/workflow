# Воркфлоу проекта

Этот документ — операционный мануал для агентов. Здесь описано как взаимодействовать с трекером задач, менять статусы, работать с кодом в данном конкретном проекте.

---

## Трекер задач

**Сервис:** YouGile
**Инстанс:** https://ru.yougile.com
**Проект:** WORKFLOW
**Доска:** разработка

### Чтение конфигурации

API-ключ YouGile хранится в переменной окружения `YOUGILE_API_KEY` в файле `.env` рядом с этим документом (`workflow/carono-ai/.env`). Файл `.env` добавлен в `.gitignore`.

Все запросы к API — прямые HTTP-вызовы (curl или любой HTTP-клиент). MCP не используется.

### Базовый URL

```
https://yougile.com/api-v2
```

### Авторизация

Каждый запрос должен содержать заголовок:

```
Authorization: Bearer <YOUGILE_API_KEY>
Content-Type: application/json
Accept: application/json
```

---

## Жизненный цикл задачи

Задачи проходят через колонки доски в порядке:

```
Задачи → Обсуждение → Разработка → На проверке → Готово
```

Бот discussion **не перемещает** задачи между колонками. Его роль — только читать задачи из колонки «Обсуждение», задавать уточняющие вопросы и отвечать на них. Решение о готовности к разработке и перенос в колонку «Разработка» принимает человек.

### Статусы задачи

| Статус | Значение в трекере | Кто переводит |
|--------|--------------------|---------------|
| Новая | Колонка «Задачи» | Человек (создаёт) |
| В обсуждении | Колонка «Обсуждение» | Человек или бот (переносит для уточнения) |
| В разработке | Колонка «Разработка» | Человек (после завершения обсуждения) |
| На проверке | Колонка «На проверке» | Бот worker (после создания MR) |
| Готово | Колонка «Готово» | Человек (после проверки и мёржа MR) |

---

## Операции с задачами

Все операции выполняются прямыми HTTP-запросами к YouGile REST API v2.

### Найти задачи в нужной колонке

```
GET https://yougile.com/api-v2/task-list?columnId=<column_id>&limit=20&offset=0
```

- `columnId` — ID колонки (предварительно узнать через GET /columns?boardId=<board_id>&title=<название колонки>)
- `limit` — макс. число результатов (1–1000)
- `offset` — смещение для пагинации
- `includeDeleted=true` — включить удалённые задачи
- `reversed_order=true` — можно использовать GET /tasks?columnId=... для обратного порядка

Ответ содержит `{paging: {offset, limit, next}, content: [...]}` — массив задач.

### Прочитать задачу

```
GET https://yougile.com/api-v2/tasks/<task_id>
```

Возвращает полную информацию: title, description, columnId, assigned, stickers, checklists, archived, completed, deleted и т.д.

### Создать задачу

```
POST https://yougile.com/api-v2/tasks
```

Тело запроса (обязателен только `title`):

```json
{
  "title": "Название задачи",
  "columnId": "<id колонки>",
  "description": "Описание в markdown",
  "assigned": ["<user_id>", "..."]
}
```

Дополнительные поля: `color`, `deadline`, `stickers`, `checklists`, `subtasks`, `completed`, `archived`.

### Обновить задачу / сменить статус

```
PUT https://yougile.com/api-v2/tasks/<task_id>
```

Тело — только изменяемые поля:

```json
{
  "columnId": "<новый id колонки>",
  "assigned": ["<user_id>"],
  "title": "Новое название",
  "deleted": true
}
```

- `columnId` — перемещает задачу в другую колонку (смена статуса)
- `assigned` — полный список назначенных пользователей (заменяет предыдущий)
- `deleted: true` — удаляет задачу, `deleted: false` — восстанавливает
- `completed` / `archived` — отметка статуса

**Важно:** при переносе задачи в колонку «Разработка», если на задаче ещё нет ответственного — бот обязан назначить на неё себя (Carono AI).

### Прочитать переписку задачи (комментарии)

```
GET https://yougile.com/api-v2/chats/<task_id>/messages?limit=20&offset=0
```

Возвращает историю сообщений в чате задачи. `chat_id` = `task_id`.

### Написать сообщение к задаче

```
POST https://yougile.com/api-v2/chats/<task_id>/messages
```

Тело запроса:

```json
{
  "text": "Текст комментария"
}
```

### Удалить задачу

```
PUT https://yougile.com/api-v2/tasks/<task_id>
```

Тело: `{"deleted": true}`

---

## Вспомогательные эндпоинты

### Получить список колонок

```
GET https://yougile.com/api-v2/columns?boardId=<board_id>&title=<название>
```

### Получить список досок

```
GET https://yougile.com/api-v2/boards?projectId=<project_id>&title=<название>
```

### Получить список проектов

```
GET https://yougile.com/api-v2/projects?title=WORKFLOW
```

### Получить список пользователей

```
GET https://yougile.com/api-v2/users?limit=20&offset=0
```

---

## Работа с кодом

### Ветки

- Создавать от: `master`
- Формат имени: `task/<номер>-<краткое-описание>`, где:
  - номер — локальный WF-номер (например WF-18 → 18)
  - описание — на английском, kebab-case
  - Пример: `task/18-fix-worker-worktrees`
- Целевая ветка для код-ревью: `master`

### Создание код-ревью

Платформа: GitHub (репозиторий `carono/workflow`). MR открывается в ветку `master`. В описании MR обязательно указывать полную ссылку на задачу в YouGile.

После создания MR бот worker **обязан** перевести задачу в колонку «На проверке» (ID: `a82fc016-5ad0-43a0-ad94-40740c04ce0e`).

### Поиск и чтение код-ревью

Использовать MCP-сервер GitHub для поиска и чтения MR/PR по репозиторию.

### Формат коммита

В сообщении коммита обязательно:
1. **Полная ссылка на задачи** в YouGile
2. Человекопонятное описание того, что было сделано

### Предварительные проверки

Перед началом работы агент worker должен проверить:

1. **gh CLI установлен:** `which gh` — если не установлен, установить согласно инструкции ниже
2. **GitHub токен доступен:** переменная `GITHUB_TOKEN` или `GITHUB_API_TOKEN` должна быть установлена
3. **Авторизация в gh:** `gh auth status` — проверить что есть доступ к репозиторию `carono/workflow`

#### Установка gh CLI (Ubuntu/Debian)

```bash
curl -sL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install -y gh
```

#### Настройка токена

Токен должен быть установлен в переменной окружения `GITHUB_TOKEN` или `GITHUB_API_TOKEN`. Если токена нет — запросить у пользователя.
