# PTZ Camera API

## Описание

Проект для управления PTZ-камерами через ONVIF и получения видеопотока по RTSP.  
API реализовано на Flask, запуск через [uv](https://github.com/pgjones/uv).

---

## Быстрый старт

1. **Установите зависимости:**
   ```
   pip install uv
   uv sync
   ```

2. **Настройте переменные окружения:**
   - Пример `.env`:
     ```
     APP_HOST=0.0.0.0
     APP_PORT=8000
     APP_DEBUG=True
     APP_TOKEN=your_token_here
     HEIGHTS=1.0,2.0,3.0
     CAMERA1_HOST=192.168.1.100
     CAMERA1_USER=admin
     CAMERA1_PASS=admin
     CAMERA1_PORT=80
     CAMERA1_RTSP=rtsp://192.168.1.100:554/stream
     CAMERA1_LON=37.6176
     CAMERA1_LAT=55.7558
     CAMERA1_HEIGHT=100.0
     ```

3. **Запустите сервер через uv:**
   ```
   uv run main.py
   ```

---

## API эндпоинты

- `GET /api/cameras` — список всех камер
- `GET /api/stream/<camera_id>/` — MJPEG видеопоток
- `POST /api/ptz/<camera_id>/move/` — перемещение PTZ-камеры  
  **Параметры:**  
  ```json
  {
    "lat": 55.7558,
    "lon": 37.6176,
    "height": 100.0,
    "zoom": 0,
    "radar_id": 1
  }
  ```
- `POST /api/ptz/<camera_id>/continuous_move/` — непрерывное движение PTZ
  **Параметры:**  
  ```json
  {
    "x": 1,
    "y": 1,
    "zoom": 0
  }
  ```
- `POST /api/ptz/<camera_id>/stop/` — остановить PTZ

**Все запросы требуют заголовок:**
```
Authorization: Bearer <APP_TOKEN>
```

---


## Проверка стиля и типов

- Проверка типов:
  ```
  mypy .
  ```
- Проверка стиля:
  ```
  flake8 .
  ```
- Автоформатирование:
  ```
  black .
  isort .
  ```

---

## Conventional Commits

Для истории изменений используйте [Conventional Commits](https://www.conventionalcommits.org/ru/v1.0.0/):

| Тип коммита | Описание                                      |
|-------------|-----------------------------------------------|
| feat        | Добавление новой функциональности             |
| fix         | Исправление ошибки                            |
| docs        | Изменение в документации                      |
| style       | Правки по стилю (форматирование и т. д.)      |
| refactor    | Рефакторинг без исправления ошибок/фич        |
| perf        | Оптимизация производительности                |
| test        | Добавление или обновление тестов              |
| build       | Изменения, касающиеся сборки проекта          |
| ci          | Настройка или изменение CI/CD                 |
| chore       | Прочие задачи (например, изменения в .gitignore) |
| revert      | Откат предыдущего коммита                     |

**Пример:**
```
fix(auth): fix token validation issue
```

### Область изменений (scope, опционально)

Scope помогает уточнить, к какой части проекта относится изменение:

| Scope   | Описание                                           |
|---------|----------------------------------------------------|
| auth    | Авторизация и аутентификация                       |
| ui      | Пользовательский интерфейс                         |
| api     | Серверные или клиентские API                       |
| core    | Основной функционал приложения                     |
| config  | Файлы конфигурации                                 |
| deps    | Обновление зависимостей                            |
| tests   | Модульные, интеграционные или e2e тесты            |
| docs    | Документация                                       |
| db      | Изменения в базе данных                            |
| build   | Скрипты сборки или сборочные файлы                 |

**Пример:**
```
docs(readme): add installation instructions
```

---

### Pre-commit hooks

Для автоматической проверки и автоформатирования кода используйте [pre-commit](https://pre-commit.com/):

1. Установите pre-commit:
   ```
   pip install pre-commit
   ```
2. Создайте файл `.pre-commit-config.yaml` (пример ниже).
3. Активируйте хуки:
   ```
   pre-commit install
   ```
4. Теперь при каждом коммите будут запускаться:
   - автоформатирование black и isort,
   - проверка стиля flake8,
   - проверка типов mypy.

Пример `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-isort
    rev: v5.10.1
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

## Прочее

- Логи пишутся в папку `logs/`.
- Для production рекомендуется запускать через WSGI (например, gunicorn).
- Для автоматической проверки кода используйте pre-commit hooks.

---

## Контакты

Вопросы и баги — Напрямую разработчику (tg: @drxzps).