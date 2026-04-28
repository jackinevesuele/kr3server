import os
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Callable

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer

from .database import (
    create_todo,
    delete_todo,
    get_todo,
    init_db,
    insert_user_plain,
    update_todo,
)
from .models import LoginRequest, Message, Todo, TodoCreate, TodoUpdate, Token, User, UserCreate, UserInDB
from .rate_limiter import check_rate_limit
from .security import (
    ROLE_PERMISSIONS,
    basic_auth_exception,
    create_access_token,
    decode_access_token,
    find_user_by_username,
    get_password_hash,
    verify_password,
)

load_dotenv()

MODE = os.getenv("MODE", "DEV").upper()
DOCS_USER = os.getenv("DOCS_USER", "valid_user")
DOCS_PASSWORD = os.getenv("DOCS_PASSWORD", "valid_password")

if MODE not in {"DEV", "PROD"}:
    raise RuntimeError("Invalid MODE. Use MODE=DEV or MODE=PROD.")

basic_security = HTTPBasic()
bearer_security = HTTPBearer(auto_error=False)

fake_users_db: dict[str, UserInDB] = {}


def seed_demo_users() -> None:
    """Seed useful users for manual RBAC checks."""
    demo_users = [
        ("admin", "adminpass", "admin"),
        ("user", "userpass", "user"),
        ("guest", "guestpass", "guest"),
        ("bosarev_evgeniy", "EFBO-11-24", "admin"),
    ]
    for username, password, role in demo_users:
        if username not in fake_users_db:
            fake_users_db[username] = UserInDB(
                username=username,
                hashed_password=get_password_hash(password),
                role=role,  # type: ignore[arg-type]
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_users()
    yield


app = FastAPI(
    title="Контрольная работа №3 — FastAPI",
    description="Босарев Евгений, ЭФБО-11-24",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


def docs_auth(credentials: Annotated[HTTPBasicCredentials, Depends(basic_security)]) -> str:
    correct_username = secrets.compare_digest(credentials.username, DOCS_USER)
    correct_password = secrets.compare_digest(credentials.password, DOCS_PASSWORD)
    if not (correct_username and correct_password):
        raise basic_auth_exception()
    return credentials.username


if MODE == "DEV":
    @app.get("/docs", include_in_schema=False, dependencies=[Depends(docs_auth)])
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="KR3 API docs",
        )


    @app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(docs_auth)])
    async def custom_openapi_json():
        return JSONResponse(app.openapi())


def auth_user(credentials: Annotated[HTTPBasicCredentials, Depends(basic_security)]) -> UserInDB:
    user = find_user_by_username(credentials.username, fake_users_db)
    if user is None:
        raise basic_auth_exception()

    username_is_valid = secrets.compare_digest(credentials.username, user.username)
    password_is_valid = verify_password(credentials.password, user.hashed_password)
    if not (username_is_valid and password_is_valid):
        raise basic_auth_exception()

    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_security)]
) -> UserInDB:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    if not isinstance(username, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = find_user_by_username(username, fake_users_db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User from token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable[[UserInDB], UserInDB]:
    def dependency(current_user: Annotated[UserInDB, Depends(get_current_user)]) -> UserInDB:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return dependency


@app.get("/", tags=["meta"])
async def root():
    return {
        "student": "Босарев Евгений",
        "group": "ЭФБО-11-24",
        "mode": MODE,
        "message": "KR3 FastAPI app is running",
    }


@app.post("/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(user: UserCreate, request: Request):
    """Register user in in-memory auth DB and also save username/password to SQLite for task 8.1."""
    if find_user_by_username(user.username, fake_users_db) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    check_rate_limit(request, endpoint_key="register", limit=1, period_seconds=60)

    if user.role not in ROLE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    fake_users_db[user.username] = UserInDB(
        username=user.username,
        hashed_password=get_password_hash(user.password),
        role=user.role,
    )

    # Requirement 8.1: raw SQL, table users(username, password), password may be plain text.
    insert_user_plain(user.username, user.password)

    return {"message": "New user created"}


@app.post("/db/register", response_model=Message, tags=["sqlite"])
async def register_in_sqlite_only(user: User):
    """Additional explicit endpoint for task 8.1 with the exact success message."""
    insert_user_plain(user.username, user.password)
    return {"message": "User registered successfully!"}


@app.get("/login", tags=["basic-auth"])
async def login_basic(current_user: Annotated[UserInDB, Depends(auth_user)]):
    """Task 6.1/6.2: GET /login protected with HTTP Basic."""
    return {
        "message": f"Welcome, {current_user.username}!",
        "secret": "You got my secret, welcome",
    }


@app.post("/login", response_model=Token, tags=["jwt-auth"])
async def login_jwt(credentials: LoginRequest, request: Request, response: Response):
    """Task 6.4/6.5: POST /login with JSON credentials and JWT response."""
    check_rate_limit(request, endpoint_key="login", limit=5, period_seconds=60)

    user = find_user_by_username(credentials.username, fake_users_db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    username_is_valid = secrets.compare_digest(credentials.username, user.username)
    password_is_valid = verify_password(credentials.password, user.hashed_password)
    if not (username_is_valid and password_is_valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization failed",
        )

    token = create_access_token(username=user.username, role=user.role)
    return Token(access_token=token, token_type="bearer")


@app.get("/protected_resource", tags=["jwt-auth"])
async def protected_resource(
    current_user: Annotated[UserInDB, Depends(require_roles("admin", "user"))]
):
    return {
        "message": "Access granted",
        "username": current_user.username,
        "role": current_user.role,
    }


@app.post("/rbac/admin/resource", tags=["rbac"])
async def admin_create_resource(
    current_user: Annotated[UserInDB, Depends(require_roles("admin"))]
):
    return {
        "message": "Admin can create resources",
        "permission": "create",
        "username": current_user.username,
    }


@app.get("/rbac/resource", tags=["rbac"])
async def read_resource(
    current_user: Annotated[UserInDB, Depends(require_roles("admin", "user", "guest"))]
):
    return {
        "message": "Resource read allowed",
        "permission": "read",
        "username": current_user.username,
    }


@app.put("/rbac/resource", tags=["rbac"])
async def update_resource(
    current_user: Annotated[UserInDB, Depends(require_roles("admin", "user"))]
):
    return {
        "message": "Resource update allowed",
        "permission": "update",
        "username": current_user.username,
    }


@app.delete("/rbac/resource", tags=["rbac"])
async def delete_resource(
    current_user: Annotated[UserInDB, Depends(require_roles("admin"))]
):
    return {
        "message": "Resource delete allowed",
        "permission": "delete",
        "username": current_user.username,
    }


@app.post("/todos", response_model=Todo, status_code=status.HTTP_201_CREATED, tags=["todos"])
async def create_todo_endpoint(todo: TodoCreate):
    return create_todo(title=todo.title, description=todo.description)


@app.get("/todos/{todo_id}", response_model=Todo, tags=["todos"])
async def get_todo_endpoint(todo_id: int):
    todo = get_todo(todo_id)
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    return todo


@app.put("/todos/{todo_id}", response_model=Todo, tags=["todos"])
async def update_todo_endpoint(todo_id: int, todo: TodoUpdate):
    updated = update_todo(
        todo_id=todo_id,
        title=todo.title,
        description=todo.description,
        completed=todo.completed,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    return updated


@app.delete("/todos/{todo_id}", tags=["todos"])
async def delete_todo_endpoint(todo_id: int):
    deleted = delete_todo(todo_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    return {"message": "Todo deleted successfully"}
