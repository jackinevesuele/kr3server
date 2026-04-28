# Контрольная работа №3

Выполнил: Босарев Евгений, ЭФБО-11-24.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Для Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Переменные окружения

Создайте файл `.env` по примеру `.env.example`:

```env
MODE=DEV
DOCS_USER=admin
DOCS_PASSWORD=admin
JWT_SECRET_KEY=change_me
```

## Создание базы данных

```bash
python scripts/create_db.py
```

## Запуск

```bash
uvicorn app.main:app --reload
```

## Проверка curl

### Basic Auth

```bash
curl -u admin:admin http://localhost:8000/login
```

### Регистрация

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"qwerty123","role":"user"}'
```

### JWT-логин

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"qwerty123"}'
```

### Защищенный ресурс

```bash
curl http://localhost:8000/protected_resource \
  -H "Authorization: Bearer TOKEN"
```

### CRUD Todo

```bash
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy groceries","description":"Milk, eggs, bread"}'

curl http://localhost:8000/todos/1

curl -X PUT http://localhost:8000/todos/1 \
  -H "Content-Type: application/json" \
  -d '{"title":"Buy groceries","description":"Milk, eggs, bread","completed":true}'

curl -X DELETE http://localhost:8000/todos/1
```

## Документация

В режиме `DEV` документация доступна по адресу:

```text
http://localhost:8000/docs
```

В режиме `PROD` документация отключена.
