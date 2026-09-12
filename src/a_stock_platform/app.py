from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from a_stock_platform.auth import (
    create_access_token,
    hash_password,
    read_access_token,
    verify_password,
)
from a_stock_platform.config import settings
from a_stock_platform.models import User, get_db, get_user_by_username, init_database


templates = Jinja2Templates(directory=Path("templates"))
app = FastAPI(
    title="China A-Share Analysis Platform",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app.router.lifespan_context = lifespan


def get_current_user(
    request: Request,
    database: Annotated[Session, Depends(get_db)],
) -> User | None:
    token = request.cookies.get("session_token")
    if not token:
        return None
    payload = read_access_token(token, settings.secret_key)
    if payload is None:
        return None
    return get_user_by_username(str(payload["sub"]), database)


class AuthRepository:
    """SQL backed credential storage and form level validation."""

    def __init__(self, database: Session):
        self.database = database

    def register_user(self, username: str, password: str) -> User:
        username = username.strip().lower()
        if not 3 <= len(username) <= 50 or len(password) < 8:
            raise ValueError("用户名需为 3-50 个字符，密码至少 8 个字符")
        if not username.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线或连字符")
        if get_user_by_username(username, self.database):
            raise ValueError("用户名已经被注册")
        user = User(username=username, password_hash=hash_password(password))
        self.database.add(user)
        self.database.commit()
        return user

    def authenticate_user(self, username: str, password: str) -> User | None:
        user = get_user_by_username(username.strip().lower(), self.database)
        if not user or not verify_password(password, user.password_hash):
            return None
        return user


def _error_page(request: Request, template: str, message: str, status_code: int) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={"title": message, "error": message},
        status_code=status_code,
    )


@app.get("/")
def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={"title": "Home"})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/register")
def register_form(
    request: Request,
    current_user_value: Annotated[User | None, Depends(get_current_user)],
) -> HTMLResponse:
    if current_user_value:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="register.html", context={"title": "注册"})


@app.post("/register")
def register_user(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    repository = AuthRepository(database)
    try:
        repository.register_user(username, password)
    except ValueError as error:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"title": "注册", "error": str(error)},
            status_code=422,
        )
    return RedirectResponse("/login", status_code=303)


@app.get("/login")
def login_form(
    request: Request,
    current_user_value: Annotated[User | None, Depends(get_current_user)],
) -> HTMLResponse:
    if current_user_value:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"title": "登录"})


@app.post("/login")
def login_user(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    repository = AuthRepository(database)
    user = repository.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"title": "登录", "error": "用户名或密码错误"},
            status_code=401,
        )
    expires_hours = settings.session_ttl_seconds // 3600
    token = create_access_token(user.username, settings.secret_key, expires_hours)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_token", path="/")
    return response


@app.get("/dashboard")
def dashboard(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "自选", "user": user},
    )
