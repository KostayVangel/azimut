# API платформы обучения

- **`courses`** — управление курсами, структурой обучения, материалами, папками и файлами;
- **`users`** — профиль пользователя, роли, права доступа и управление сотрудниками.

---

## Содержание

1. [Краткий обзор](#краткий-обзор)
2. [API `courses`](#api-courses)
   - [Назначение](#назначение-courses)
   - [Структура курсов](#структура-курсов)
   - [Базовый URL](#базовый-url-courses)
   - [Авторизация](#авторизация-courses)
   - [Логика навигации](#логика-навигации)
   - [Эндпоинты](#эндпоинты-courses)
   - [Breadcrumbs](#breadcrumbs)
   - [Ошибки валидации](#ошибки-валидации-courses)
   - [Ограничения бизнес-логики](#ограничения-бизнес-логики-courses)
   - [Рекомендуемый сценарий для фронтенда](#рекомендуемый-сценарий-для-фронтенда)
3. [API `users`](#api-users)
   - [Назначение](#назначение-users)
   - [Типы пользователей](#типы-пользователей)
   - [RBAC-структура](#rbac-структура)
   - [Базовый URL](#базовый-url-users)
   - [Авторизация](#авторизация-users)
   - [Эндпоинты](#эндпоинты-users)
   - [Каталог прав](#каталог-прав)
4. [Сводная таблица эндпоинтов](#сводная-таблица-эндпоинтов)

---

## Краткий обзор

Платформа построена вокруг двух основных сущностей:

- **образовательный контент** — курсы, темы, материалы, документы, тесты и файлы;
- **доступ и управление пользователями** — профили, роли, права, сотрудники и разграничение доступа.

Все ответы API возвращаются в формате **JSON**, за исключением загрузки файлов, где используется `multipart/form-data`.

---

# API `courses`

## Назначение `courses`

API приложения `courses` предназначено для:

- получения списка доступных пользователю курсов;
- навигации по структуре курса как по директориям;
- создания курсов и вложенных сущностей через API;
- получения материалов курса;
- получения содержимого папок и файлов внутри материалов.

---

## Структура курсов

Система поддерживает два типа курсов.

### 1. Полноценный курс

```text
Курс
└── Семестр
    └── Предмет
        └── Тема
            └── Материалы
```

### 2. Неполный курс

```text
Курс
└── Тема
    └── Материалы
```

Дополнительно у неполного курса материалы могут быть прикреплены **напрямую к курсу**.

---

## Базовый URL `courses`

```text
/api/courses/
```

---

## Авторизация `courses`

На текущем этапе:

- чтение доступно без ограничений;
- создание доступно авторизованному пользователю.

В дальнейшем ограничения доступа могут зависеть от:

- роли пользователя;
- факта покупки курса.

Логика доступа централизована на backend и может быть расширена позже.

---

## Логика навигации

API построено по принципу **«открытия директорий»**.

Типичный сценарий:

1. клиент получает список курсов;
2. открывает конкретный курс;
3. получает вложенные сущности текущего уровня;
4. открывает следующий уровень;
5. повторяет этот сценарий до нужной вложенности.

Такой подход нужен для:

- оптимизации скорости загрузки;
- уменьшения размера ответа;
- удобной ленивой подгрузки структуры на фронтенде.

---

## Эндпоинты `courses`

### 1. Получить список курсов

**`GET /api/courses/`**

Возвращает список всех доступных пользователю курсов.

#### Пример ответа

```json
[
  {
    "id": 1,
    "title": "Python Backend",
    "slug": "python-backend",
    "description": "Курс по backend-разработке",
    "course_type": "full",
    "course_type_display": "Полноценный",
    "position": 1,
    "is_active": true
  },
  {
    "id": 2,
    "title": "SQL Basics",
    "slug": "sql-basics",
    "description": "Быстрый курс по SQL",
    "course_type": "simple",
    "course_type_display": "Неполный",
    "position": 2,
    "is_active": true
  }
]
```

#### Поля ответа

| Поле | Тип | Описание |
|---|---|---|
| `id` | integer | ID курса |
| `title` | string | Название курса |
| `slug` | string | Уникальный slug |
| `description` | string | Описание |
| `course_type` | string | Тип курса: `full` / `simple` |
| `course_type_display` | string | Человекочитаемое название типа |
| `position` | integer | Порядок сортировки |
| `is_active` | boolean | Активен ли курс |

---

### 2. Создать курс

**`POST /api/courses/`**

Создает новый курс.

#### Тело запроса

```json
{
  "title": "Python Backend",
  "description": "Курс по backend-разработке",
  "course_type": "full",
  "position": 1,
  "is_active": true
}
```

#### Поля запроса

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `title` | string | да | Название курса |
| `slug` | string | нет | Можно не передавать, будет сгенерирован автоматически |
| `description` | string | нет | Описание курса |
| `course_type` | string | да | `full` или `simple` |
| `position` | integer | нет | Порядок отображения |
| `is_active` | boolean | нет | Активен ли курс |

---

### 3. Открыть курс как директорию

**`GET /api/courses/<course_id>/contents/`**

Возвращает содержимое курса.

- для **полноценного курса** — семестры;
- для **неполного курса** — темы и материалы, прикрепленные напрямую к курсу.

#### Пример ответа для полноценного курса

```json
{
  "node_type": "course",
  "current": {
    "id": 1,
    "title": "Python Backend",
    "slug": "python-backend",
    "description": "Курс по backend-разработке",
    "course_type": "full",
    "course_type_display": "Полноценный",
    "position": 1,
    "is_active": true
  },
  "breadcrumbs": [
    { "type": "root", "id": null, "title": "Все курсы" },
    { "type": "course", "id": 1, "title": "Python Backend" }
  ],
  "children": {
    "semesters": [
      {
        "id": 1,
        "course": 1,
        "title": "1 семестр",
        "position": 1
      }
    ],
    "subjects": [],
    "topics": [],
    "materials": []
  }
}
```

#### Пример ответа для неполного курса

```json
{
  "node_type": "course",
  "current": {
    "id": 2,
    "title": "SQL Basics",
    "slug": "sql-basics",
    "description": "Быстрый курс по SQL",
    "course_type": "simple",
    "course_type_display": "Неполный",
    "position": 2,
    "is_active": true
  },
  "breadcrumbs": [
    { "type": "root", "id": null, "title": "Все курсы" },
    { "type": "course", "id": 2, "title": "SQL Basics" }
  ],
  "children": {
    "semesters": [],
    "subjects": [],
    "topics": [
      {
        "id": 10,
        "course": 2,
        "subject": null,
        "title": "SELECT",
        "description": "",
        "position": 1
      }
    ],
    "materials": [
      {
        "id": 5,
        "course": 2,
        "subject": null,
        "topic": null,
        "title": "Вводная лекция",
        "material_type": "lecture",
        "material_type_display": "Лекция",
        "description": "",
        "position": 1,
        "is_published": true,
        "free_preview": true
      }
    ]
  }
}
```

---

### 4. Создать семестр

**`POST /api/courses/semesters/`**

Создает семестр внутри полноценного курса.

```json
{
  "course": 1,
  "title": "1 семестр",
  "position": 1
}
```

> Семестр можно создать **только** для курса типа `full`.

---

### 5. Открыть семестр

**`GET /api/courses/semesters/<semester_id>/contents/`**

Возвращает содержимое семестра: предметы.

---

### 6. Создать предмет

**`POST /api/courses/subjects/`**

Создает предмет внутри семестра.

```json
{
  "semester": 1,
  "title": "Django",
  "description": "Основы Django",
  "position": 1
}
```

---

### 7. Открыть предмет

**`GET /api/courses/subjects/<subject_id>/contents/`**

Возвращает:

- темы предмета;
- материалы, прикрепленные к предмету.

---

### 8. Создать тему

**`POST /api/courses/topics/`**

Создает тему:

- либо внутри `subject` — для полноценного курса;
- либо внутри `course` — для неполного курса.

#### Для неполного курса

```json
{
  "course": 2,
  "title": "SELECT",
  "description": "Основы выборки",
  "position": 1
}
```

#### Для полноценного курса

```json
{
  "subject": 3,
  "title": "Модели",
  "description": "Работа с моделями Django",
  "position": 1
}
```

> Нельзя передавать одновременно и `course`, и `subject`.

---

### 9. Открыть тему

**`GET /api/courses/topics/<topic_id>/contents/`**

Возвращает материалы темы.

---

### 10. Создать материал

**`POST /api/courses/materials/`**

Создает материал и его специализированные данные.

Материал может принадлежать:

- `course` — только для неполного курса;
- `subject` — только для полноценного курса;
- `topic` — для обоих типов.

#### Типы материалов

| Значение | Описание |
|---|---|
| `lecture` | Лекция |
| `presentation` | Презентация |
| `document` | Документ |
| `test` | Тест |
| `other` | Другое |

#### Базовая структура запроса

```json
{
  "course": null,
  "subject": null,
  "topic": 20,
  "title": "Лекция по моделям",
  "material_type": "lecture",
  "description": "Введение в модели Django",
  "position": 1,
  "is_published": true,
  "free_preview": false
}
```

Нужно передать **ровно одного родителя**:

- `course`
- `subject`
- `topic`

#### Примеры специализированных данных

**Лекция**

```json
{
  "topic": 20,
  "title": "Лекция по моделям",
  "material_type": "lecture",
  "description": "Введение в модели Django",
  "position": 1,
  "is_published": true,
  "free_preview": false,
  "lecture_data": {
    "content": "Текст лекции...",
    "duration_minutes": 45
  }
}
```

**Презентация**

```json
{
  "subject": 3,
  "title": "Презентация по ORM",
  "material_type": "presentation",
  "description": "Слайды по Django ORM",
  "position": 2,
  "is_published": true,
  "free_preview": false,
  "presentation_data": {
    "speaker_notes": "Комментарии спикера",
    "slides_count": 24
  }
}
```

**Документ**

```json
{
  "topic": 20,
  "title": "Методичка",
  "material_type": "document",
  "description": "PDF файл с методичкой",
  "position": 3,
  "is_published": true,
  "free_preview": true,
  "document_data": {
    "document_format": "pdf",
    "extracted_text": "Текст документа..."
  }
}
```

**Тест**

```json
{
  "topic": 20,
  "title": "Тест по моделям",
  "material_type": "test",
  "description": "Проверка знаний",
  "position": 4,
  "is_published": true,
  "free_preview": false,
  "test_data": {
    "time_limit_minutes": 20,
    "attempts_limit": 3,
    "passing_percentage": 70,
    "shuffle_questions": true,
    "show_correct_answers_after_submit": false,
    "questions": [
      {
        "text": "Что делает models.ForeignKey?",
        "question_type": "single",
        "explanation": "",
        "points": 1,
        "position": 1,
        "correct_text_answers": [],
        "case_sensitive": false,
        "options": [
          {
            "text": "Создает связь многие-к-одному",
            "is_correct": true,
            "position": 1
          },
          {
            "text": "Создает связь многие-ко-многим",
            "is_correct": false,
            "position": 2
          }
        ]
      }
    ]
  }
}
```

---

### 11. Открыть материал

**`GET /api/courses/materials/<material_id>/contents/`**

Возвращает:

- базовую информацию о материале;
- детальную структуру по типу материала;
- вложенные папки;
- вложенные файлы.

> Для тестов в этом ответе **не возвращаются правильные ответы**.

---

### 12. Создать папку внутри материала

**`POST /api/courses/folders/`**

```json
{
  "material": 200,
  "parent": null,
  "title": "Дополнительные материалы",
  "position": 1
}
```

---

### 13. Открыть папку

**`GET /api/courses/folders/<folder_id>/contents/`**

Возвращает вложенные папки и файлы.

---

### 14. Загрузить файл

**`POST /api/courses/files/`**

Создает файл внутри материала или папки.

#### Формат запроса

```text
multipart/form-data
```

#### Поля формы

| Поле | Тип | Обязательное | Описание |
|---|---|---|---|
| `material` | integer | да | ID материала |
| `folder` | integer/null | нет | ID папки |
| `title` | string | нет | Название файла |
| `file` | file | да | Сам файл |
| `file_role` | string | нет | Роль файла |
| `position` | integer | нет | Позиция |

#### Допустимые значения `file_role`

| Значение | Описание |
|---|---|
| `main` | Основной файл |
| `attachment` | Вложение |
| `image` | Изображение |
| `other` | Другое |

---

## Breadcrumbs

Во всех эндпоинтах вида `.../contents/` возвращается поле `breadcrumbs`.

Оно нужно для построения навигации на фронтенде.

#### Пример

```json
[
  {"type": "root", "id": null, "title": "Все курсы"},
  {"type": "course", "id": 1, "title": "Python Backend"},
  {"type": "semester", "id": 1, "title": "1 семестр"},
  {"type": "subject", "id": 3, "title": "Django"},
  {"type": "topic", "id": 20, "title": "Модели"}
]
```

---

## Ошибки валидации `courses`

При ошибках валидации API возвращает стандартный ответ DRF.

#### Пример

```json
{
  "course": [
    "Семестры можно создавать только у полноценного курса."
  ]
}
```

или

```json
{
  "non_field_errors": [
    "Материал должен принадлежать только одному родителю: course, subject или topic."
  ]
}
```

---

## Ограничения бизнес-логики `courses`

### Курсы

- `course_type` может быть только `full` или `simple`.

### Семестры

- создаются только у `full` курса.

### Предметы

- создаются только внутри семестра полноценного курса.

### Темы

- либо у `course` для `simple` курса;
- либо у `subject` для `full` курса.

### Материалы

- могут принадлежать только одному родителю:
  - `course`
  - `subject`
  - `topic`

### Публикация

Пользовательские эндпоинты чтения возвращают только материалы с:

```text
is_published = true
```

---

## Рекомендуемый сценарий для фронтенда

```text
GET /api/courses/
GET /api/courses/<id>/contents/
GET /api/courses/semesters/<id>/contents/
GET /api/courses/subjects/<id>/contents/
GET /api/courses/topics/<id>/contents/
GET /api/courses/materials/<id>/contents/
GET /api/courses/folders/<id>/contents/
```

---

# API `users`

## Назначение `users`

API `users` отвечает за:

- профиль текущего пользователя;
- получение доступов текущего пользователя;
- управление ролями;
- управление сотрудниками.

---

## Типы пользователей

- `owner` — главный пользователь
- `employee` — сотрудник
- `student` — учащийся

---

## RBAC-структура

Система прав доступа построена так:

- `PermissionModule` — вкладка;
- `PermissionAction` — действие внутри вкладки;
- `Role` — роль с набором действий;
- `User.role` — назначенная роль сотруднику.

---

## Базовый URL `users`

```text
/api/users/
```

---

## Авторизация `users`

Все эндпоинты приложения требуют авторизацию.

Поддерживаемый формат зависит от схемы аутентификации проекта:

- `SessionAuth`
- `JWT`
- `Token`

---

## Эндпоинты `users`

### 1. Получить профиль текущего пользователя

**`GET /api/users/me/`**

Возвращает данные текущего пользователя, включая роль и тип аккаунта.

---

### 2. Обновить свой профиль

**`PATCH /api/users/me/`**

Разрешено обновлять:

- `first_name`
- `last_name`
- `middle_name`
- `email`
- `phone`
- `avatar`

Для загрузки аватара рекомендуется использовать `multipart/form-data`.

---

### 3. Получить доступы текущего пользователя

**`GET /api/users/me/access/`**

Возвращает:

- профиль пользователя;
- роль;
- все вкладки;
- все действия;
- информацию о том, где доступ разрешен.

#### Как использовать на фронте

- показывать вкладку, если `has_access = true`;
- активировать кнопку или функцию, если `action.granted = true`.

---

### 4. Получить каталог модулей и действий

**`GET /api/users/permission-modules/`**

Используется для построения формы создания роли.

---

### 5. Получить список ролей

**`GET /api/users/roles/`**

Возвращает список ролей с базовой информацией и количеством пользователей.

---

### 6. Создать роль

**`POST /api/users/roles/`**

Создает новую роль и назначает ей набор прав через `permission_codes`.

---

### 7. Получить роль

**`GET /api/users/roles/<id>/`**

Возвращает полную конфигурацию роли.

---

### 8. Обновить роль

**`PATCH /api/users/roles/<id>/`**

Позволяет изменить описание, активность и набор прав роли.

---

### 9. Удалить роль

**`DELETE /api/users/roles/<id>/`**

Логика удаления:

- роль не удаляется физически, а деактивируется;
- системную роль удалить нельзя;
- роль, назначенную сотрудникам, удалить нельзя.

Успешный ответ:

```text
204 No Content
```

---

### 10. Получить список сотрудников

**`GET /api/users/staff/`**

Возвращает список сотрудников с их ролями и статусом активности.

---

### 11. Создать сотрудника

**`POST /api/users/staff/`**

Если `password` не передан, он будет сгенерирован автоматически.

> `temporary_password` возвращается только в ответе создания, если пароль был сгенерирован автоматически.

---

### 12. Получить сотрудника

**`GET /api/users/staff/<id>/`**

Возвращает полные данные сотрудника.

---

### 13. Обновить сотрудника

**`PATCH /api/users/staff/<id>/`**

Можно менять:

- `username`
- `password`
- `first_name`
- `last_name`
- `middle_name`
- `email`
- `phone`
- `avatar`
- `role`
- `is_active`

Если передать новый пароль, пользователю будет выставлено:

```text
must_change_password = true
```

---

## Каталог прав

Ниже приведен единый справочник permission-кодов для frontend и backend.

### Настройка магазина

- `store.cards.create`
- `store.cards.edit`

### Управление банером

- `banner.image.upload`
- `banner.visibility.toggle`

### Курсы

- `courses.folder.create`
- `courses.folder.rename`
- `courses.files.attach`
- `courses.description.create`
- `courses.description.edit`
- `courses.tests.create`
- `courses.tests.edit`

### Сотрудники

- `employees.roles.view`
- `employees.roles.delete`
- `employees.roles.create`
- `employees.roles.configure`
- `employees.staff.view`
- `employees.staff.create`
- `employees.staff.edit`

### Распределение

- `distribution.groups.create`
- `distribution.students.create`
- `distribution.students.credentials.edit`
- `distribution.students.sensitive_data.view`
- `distribution.students.groups.add`
- `distribution.students.groups.remove`

### Учащиеся

- `students.groups.view`
- `students.progress.group.view`
- `students.progress.single.view`
- `students.courses.add`

### Оплата

- `payments.view_all`
- `payments.notifications.send`

### Документы

- `documents.files.upload`
- `documents.files.delete`

### Чаты

- `chats.all.view`
- `chats.assigned.view`

### Принятие заявок

- `applications.all.view`
- `applications.take_in_work`

### Доступ к профилю

- `profile.required_documents.edit`

### Оформление

- `design.access`

---

# Сводная таблица эндпоинтов

## `courses`

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/courses/` | Список курсов |
| `POST` | `/api/courses/` | Создать курс |
| `GET` | `/api/courses/<id>/contents/` | Открыть курс |
| `POST` | `/api/courses/semesters/` | Создать семестр |
| `GET` | `/api/courses/semesters/<id>/contents/` | Открыть семестр |
| `POST` | `/api/courses/subjects/` | Создать предмет |
| `GET` | `/api/courses/subjects/<id>/contents/` | Открыть предмет |
| `POST` | `/api/courses/topics/` | Создать тему |
| `GET` | `/api/courses/topics/<id>/contents/` | Открыть тему |
| `POST` | `/api/courses/materials/` | Создать материал |
| `GET` | `/api/courses/materials/<id>/contents/` | Открыть материал |
| `POST` | `/api/courses/folders/` | Создать папку |
| `GET` | `/api/courses/folders/<id>/contents/` | Открыть папку |
| `POST` | `/api/courses/files/` | Загрузить файл |

## `users`

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/users/me/` | Получить профиль текущего пользователя |
| `PATCH` | `/api/users/me/` | Обновить свой профиль |
| `GET` | `/api/users/me/access/` | Получить доступы текущего пользователя |
| `GET` | `/api/users/permission-modules/` | Получить каталог модулей и действий |
| `GET` | `/api/users/roles/` | Получить список ролей |
| `POST` | `/api/users/roles/` | Создать роль |
| `GET` | `/api/users/roles/<id>/` | Получить роль |
| `PATCH` | `/api/users/roles/<id>/` | Обновить роль |
| `DELETE` | `/api/users/roles/<id>/` | Деактивировать роль |
| `GET` | `/api/users/staff/` | Получить список сотрудников |
| `POST` | `/api/users/staff/` | Создать сотрудника |
| `GET` | `/api/users/staff/<id>/` | Получить сотрудника |
| `PATCH` | `/api/users/staff/<id>/` | Обновить сотрудника |

---


