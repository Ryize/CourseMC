# API проверки решений уроков из бота

API позволяет доверенному боту:

- получать новые и повторно отправленные решения со сведениями об ученике;
- скачивать приложенные файлы;
- показывать преподавателю предварительную рекомендацию ИИ по последней отправке;
- менять статус решения от имени преподавателя;
- сохранять комментарий преподавателя.

Базовый адрес в продакшене:

```text
https://coursemc.ru/api/v1
```

## Авторизация

Во всех запросах передавайте секрет в HTTP-заголовке:

```text
X-CourseMC-Bot-Token: <COURSEMC_BOT_API_TOKEN>
```

Секрет должен совпадать со значением `COURSEMC_BOT_API_TOKEN` на сайте. Не
передавайте его в URL, не записывайте в логи и не добавляйте в Git.

При неверном или отсутствующем токене API отвечает `403 Forbidden`.

Краткое машиночитаемое описание доступно по адресу:

```text
GET /api/v1/bot/lesson-solutions/docs/
```

## 1. Получить новые решения

```text
GET /api/v1/bot/lesson-solutions/?after=0&limit=50
```

Параметры:

- `after` — идентификатор последней обработанной отправки. При первом запросе
  передайте `0`;
- `limit` — от 1 до 100, по умолчанию 50;
- `teacher_username` — необязательный логин преподавателя. Для обычного
  преподавателя API вернёт только его группы. Суперпользователь видит все
  группы.

Пример ответа:

```json
{
  "count": 1,
  "next_cursor": 127,
  "results": [
    {
      "id": 42,
      "submission_id": 127,
      "attempt_number": 2,
      "student": {
        "id": 18,
        "username": "student_login",
        "display_name": "Иван Иванов"
      },
      "group": {
        "id": 7,
        "title": "Питонисты"
      },
      "lesson": {
        "id": 55,
        "number": 44,
        "title": "Функции. Практика",
        "direction": "Backend 2024"
      },
      "status": "pending",
      "status_display": "На проверке",
      "teacher_comment": "",
      "submitted_at": "2026-08-24T12:30:00+03:00",
      "files": [
        {
          "id": 91,
          "original_name": "solution.py",
          "size": 1842,
          "uploaded_at": "2026-08-24T12:30:00+03:00",
          "download_url": "https://coursemc.ru/api/v1/bot/lesson-solutions/files/91/"
        }
      ],
      "ai_review": {
        "status": "ready",
        "status_display": "Рекомендация готова",
        "feedback": "1. Не выведен результат, который требуется по условию.",
        "issue_count": 1,
        "source_summary": "Проверены: solution.py.",
        "error": null,
        "reviewed_at": "2026-08-24T12:31:00+03:00"
      }
    }
  ]
}
```

`id` — идентификатор решения, он нужен для изменения статуса.
`submission_id` — идентификатор конкретной попытки, он используется как
курсор и ключ идемпотентности уведомления.

`ai_review` относится именно к этому `submission_id`, а не к прежней попытке.
Это черновик для преподавателя, не итоговая оценка и не комментарий ученику.
`feedback` — готовый текст рекомендации или `null`, пока её нет;
`issue_count` — число существенных замечаний. При отсутствии проблем ИИ
возвращает текст «явных ошибок не найдено», но окончательное решение всё равно
принимает преподаватель. Возможные `status`: `not_requested`, `pending`,
`ready`, `partial`, `unsupported`, `failed`. При `partial` проверена лишь часть
файлов — смотрите `source_summary`; при `failed` причина указана в `error`.
Бот должен показывать `feedback` только преподавателю и не менять статус
решения автоматически.

Рекомендуемый цикл работы:

1. Получить очередь с последним сохранённым `after`.
2. Отправить преподавателям уведомления, файлы и доступную рекомендацию ИИ.
3. Для защиты от дублей запомнить обработанные `submission_id`.
4. Только после успешной отправки всей страницы сохранить `next_cursor`.
5. Повторить запрос с новым `after`.

Если бот завершится до сохранения курсора, он может повторить уведомление, но
не потеряет решение. Повторная отправка учеником имеет новый `submission_id`,
даже если `id` решения остался прежним.

Если в очереди `ai_review.status` ещё равен `pending`, не задерживайте
уведомление и сохранение курсора. Позже запросите решение по `id` через
детальный endpoint и обновите сообщение бота, когда рекомендация будет готова.
Сверяйте `submission_id`: если ученик успел отправить новую версию, старую
рекомендацию не показывайте как оценку новой работы.

## 2. Обновить решение и рекомендацию ИИ

```text
GET /api/v1/bot/lesson-solutions/42/
```

Передайте тот же токен. Ответ имеет формат одного объекта из `results`
очереди, включая файлы и актуальный `ai_review`. Запрос не зависит от `after`:
его можно использовать для обновления уже отправленного уведомления. Если
проверка завершилась с `failed` или `unsupported`, сообщите преподавателю, что
нужна ручная проверка, а не считайте работу ошибочной.

## 3. Скачать файл решения

```text
GET /api/v1/bot/lesson-solutions/files/91/
```

Передайте тот же заголовок `X-CourseMC-Bot-Token`. Ответ содержит файл как
вложение. Ссылки не являются публичными и без токена не работают.

Пример:

```bash
curl \
  -H "X-CourseMC-Bot-Token: $COURSEMC_BOT_API_TOKEN" \
  -OJ \
  "https://coursemc.ru/api/v1/bot/lesson-solutions/files/91/"
```

## 4. Проверить решение

```text
PATCH /api/v1/bot/lesson-solutions/42/review/
Content-Type: application/json
```

Принять работу:

```json
{
  "reviewer_username": "teacher_login",
  "status": "accepted",
  "teacher_comment": "Хорошая работа."
}
```

Вернуть на доработку:

```json
{
  "reviewer_username": "teacher_login",
  "status": "needs_revision",
  "teacher_comment": "Добавьте обработку пустого списка."
}
```

Вернуть в очередь проверки:

```json
{
  "reviewer_username": "teacher_login",
  "status": "pending",
  "teacher_comment": ""
}
```

Доступные статусы:

- `pending` — «На проверке»;
- `accepted` — «Принято»;
- `needs_revision` — «Нужна доработка».

Для `needs_revision` комментарий обязателен. Логин должен принадлежать
активному пользователю с доступом в админку. Обычный преподаватель может
проверять только учеников своей группы, суперпользователь — всех учеников.

После перехода из статуса `pending` уведомление преподавателя на сайте
автоматически считается просмотренным.

Пример ответа:

```json
{
  "id": 42,
  "status": "needs_revision",
  "status_display": "Нужна доработка",
  "teacher_comment": "Добавьте обработку пустого списка.",
  "reviewer_username": "teacher_login",
  "reviewed_at": "2026-08-24T13:15:00+03:00"
}
```

## Пример на Python

```python
import os

import requests


BASE_URL = "https://coursemc.ru/api/v1/bot/lesson-solutions"
HEADERS = {
    "X-CourseMC-Bot-Token": os.environ["COURSEMC_BOT_API_TOKEN"],
}


def get_new_solutions(cursor: int, teacher_username: str | None = None):
    params = {"after": cursor, "limit": 50}
    if teacher_username:
        params["teacher_username"] = teacher_username
    response = requests.get(
        f"{BASE_URL}/",
        headers=HEADERS,
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def download_file(download_url: str) -> bytes:
    response = requests.get(download_url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.content


def get_solution(solution_id: int):
    response = requests.get(
        f"{BASE_URL}/{solution_id}/",
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def review_solution(
    solution_id: int,
    reviewer_username: str,
    status: str,
    comment: str = "",
):
    response = requests.patch(
        f"{BASE_URL}/{solution_id}/review/",
        headers=HEADERS,
        json={
            "reviewer_username": reviewer_username,
            "status": status,
            "teacher_comment": comment,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
```

## Ошибки

- `400 Bad Request` — неверные параметры, статус или отсутствует обязательный
  комментарий;
- `403 Forbidden` — неверный токен либо преподаватель не ведёт группу;
- `404 Not Found` — решение, файл или преподаватель не найден;
- `405 Method Not Allowed` — использован неподдерживаемый HTTP-метод.
