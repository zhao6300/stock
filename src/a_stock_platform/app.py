from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
import math

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from a_stock_platform.auth import (
    create_access_token,
    hash_password,
    read_access_token,
    verify_password,
)
from a_stock_platform.data import get_market_history, import_daily_prices, validate_symbol
from a_stock_platform.indicators import compute_metrics
from a_stock_platform.importer import parse_csv_rows
from a_stock_platform.models import Watchlist
from a_stock_platform.config import settings
from a_stock_platform.models import (
    SavedFilter,
    User,
    get_db,
    get_user_by_username,
    init_database,
)


templates = Jinja2Templates(directory=Path("templates"))
app = FastAPI(
    title="China A-Share Analysis Platform",
)


def _dashboard_response(
    request: Request,
    user: User,
    database: Session,
    error: str | None = None,
    error_status: int = 200,
) -> Response:
    entries = database.execute(
        select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.symbol)
    ).scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "自选", "user": user, "entries": entries, "error": error},
        status_code=error_status if error else 200,
    )


def _sparkline(candles: list[dict[str, object]], width: int = 240, height: int = 60) -> str:
    closes = [float(row["close"]) for row in candles]
    if len(closes) < 2:
        return ""
    low, high = min(closes), max(closes)
    denominator = high - low or 1
    points = []
    for index, close in enumerate(closes):
        x = (index / (len(closes) - 1)) * width
        y = height - ((close - low) / denominator) * height
        points.append(f"{x:.1f},{y:.1f}")
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="价格走势"><polyline fill="none" stroke="#2563eb" stroke-width="2" points="{" ".join(points)}" /></svg>'


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
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    entries = database.execute(
        select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.symbol)
    ).scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "自选", "user": user, "entries": entries},
    )


@app.post("/dashboard/watchlist")
def add_watchlist_symbol(
    request: Request,
    symbol: Annotated[str, Form()],
    symbol_type: Annotated[str, Form()],
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    symbol_type = symbol_type.strip().lower()
    try:
        normalized = validate_symbol(symbol, symbol_type)
    except ValueError as error:
        return _dashboard_response(request, user, database, str(error), 422)
    existing = database.execute(
        select(Watchlist).where(
            Watchlist.user_id == user.id,
            Watchlist.symbol == normalized,
            Watchlist.symbol_type == symbol_type,
        )
    ).scalar_one_or_none()
    if existing:
        return RedirectResponse("/dashboard", status_code=303)
    database.add(
        Watchlist(
            user_id=user.id,
            symbol=normalized,
            symbol_type=symbol_type,
        )
    )
    database.commit()
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/dashboard/watchlist/{watchlist_id}/delete")
def delete_watchlist_symbol(
    watchlist_id: int,
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    entry = database.get(Watchlist, watchlist_id)
    if entry and entry.user_id == user.id:
        database.delete(entry)
        database.commit()
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/dashboard/watchlist/{watchlist_id}/import")
async def import_watchlist_csv(
    request: Request,
    watchlist_id: int,
    csv_file: Annotated[UploadFile, File()],
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    entry = database.get(Watchlist, watchlist_id)
    if entry is None or entry.user_id != user.id:
        return _dashboard_response(request, user, database, "自选代码不存在", 404)
    try:
        rows = parse_csv_rows(await csv_file.read())
    except ValueError as error:
        return _dashboard_response(request, user, database, str(error), 422)
    try:
        imported = import_daily_prices(database, entry.symbol, entry.symbol_type, rows, source="csv_upload")
    except ValueError as error:
        return _dashboard_response(request, user, database, str(error), 422)
    if not imported:
        return _dashboard_response(request, user, database, "没有导入任何记录")
    return RedirectResponse("/dashboard", status_code=303)


def _analysis_data(
    symbol: str,
    symbol_type: str,
    database: Session,
    days: int,
) -> dict[str, object]:
    normalized = validate_symbol(symbol, symbol_type)
    candles = get_market_history(database, normalized, symbol_type, min(max(days, 5), 500))
    if not candles:
        raise ValueError("暂无行情数据，请确认接口可用或导入数据")
    metrics = compute_metrics(candles)
    source = str(candles[-1].get("source") or "")
    return {
        "symbol": normalized,
        "symbol_type": symbol_type,
        "candles": candles,
        "metrics": metrics,
        "source": source,
        "sparkline": _sparkline(candles),
    }


def _comparison_payload(
    symbols: str | list[str],
    symbol_type: str,
    database: Session,
    days: int,
    sort_by: str = "annualized_return_pct",
    direction: str = "desc",
    min_annualized_return_pct: float | None = None,
    max_annualized_volatility_pct: float | None = None,
    min_sharpe: float | None = None,
) -> dict[str, object]:
    if symbol_type not in {"stock", "fund"}:
        raise ValueError("symbol_type 只能是 stock 或 fund")
    if direction not in {"asc", "desc"}:
        raise ValueError("direction 只能是 asc 或 desc")
    if not isinstance(symbols, str):
        symbols = ",".join(symbols)
    requested = [item.strip() for item in symbols.replace("，", ",").split(",") if item.strip()]
    if not requested:
        raise ValueError("至少提供一个股票或基金代码")
    if len(requested) > 30:
        raise ValueError("一次最多比较 30 个代码")
    rows = []
    warnings = []
    for symbol in requested:
        try:
            result = _analysis_data(symbol, symbol_type, database, days)
        except ValueError as error:
            warnings.append(f"{symbol}: {error}")
            continue
        rows.append(
            {
                "symbol": result["symbol"],
                "symbol_type": result["symbol_type"],
                "metrics": result["metrics"],
                "source": result["source"],
                "sparkline": result["sparkline"],
            }
        )
    if sort_by != "annualized_return_pct":
        raise ValueError("排序字段无效")
    if min_annualized_return_pct is not None:
        rows = [
            row for row in rows
            if float(row["metrics"].get("annualized_return_pct", 0.0)) >= min_annualized_return_pct
        ]
    if max_annualized_volatility_pct is not None:
        rows = [
            row for row in rows
            if float(row["metrics"].get("annualized_volatility_pct", math.inf)) <= max_annualized_volatility_pct
        ]
    if min_sharpe is not None:
        rows = [row for row in rows if row["metrics"].get("sharpe") is not None and float(row["metrics"]["sharpe"]) >= min_sharpe]
    rows.sort(
        key=lambda item: float(item["metrics"].get(sort_by, 0.0) or 0.0),
        reverse=direction == "desc",
    )
    return {
        "symbol_type": symbol_type,
        "symbols": requested,
        "rows": rows,
        "warnings": warnings,
        "sort_by": sort_by,
        "direction": direction,
    }


@app.get("/analysis/{symbol_type}/{symbol}")
def analysis_page(
    request: Request,
    symbol_type: str,
    symbol: str,
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
    days: Annotated[int, Query(ge=5, le=500)] = 250,
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    try:
        data = _analysis_data(symbol, symbol_type, database, days)
    except ValueError as error:
        return _error_page(request, "analysis.html", str(error), 422)
    return templates.TemplateResponse(
        request=request,
        name="analysis.html",
        context={
            "title": str(data["symbol"]),
            "user": user,
            **data,
            **data["metrics"],
        },
    )


@app.get("/api/analysis/{symbol_type}/{symbol}")
def analysis_json(
    symbol_type: str,
    symbol: str,
    database: Annotated[Session, Depends(get_db)],
    days: Annotated[int, Query(ge=5, le=500)] = 250,
) -> dict[str, object]:
    try:
        return _analysis_data(symbol, symbol_type, database, days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/compare")
def compare_page(
    request: Request,
    symbols: str,
    symbol_type: str,
    database: Annotated[Session, Depends(get_db)],
    user: Annotated[User | None, Depends(get_current_user)] = None,
    days: Annotated[int, Query(ge=5, le=500)] = 250,
    sort_by: str = "annualized_return_pct",
    direction: str = "desc",
    min_annualized_return_pct: Annotated[float | None, Query(ge=0)] = None,
    max_annualized_volatility_pct: Annotated[float | None, Query(ge=0)] = None,
    min_sharpe: float | None = None,
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    try:
        payload = _comparison_payload(
            symbols,
            symbol_type,
            database,
            days,
            sort_by,
            direction,
            min_annualized_return_pct=min_annualized_return_pct,
            max_annualized_volatility_pct=max_annualized_volatility_pct,
            min_sharpe=min_sharpe,
        )
    except ValueError as error:
        return _error_page(request, "compare.html", str(error), 422)
    return templates.TemplateResponse(
        request=request,
        name="compare.html",
        context={"title": "对比", "user": user, **payload},
    )


@app.get("/api/compare")
def compare_json(
    symbols: str,
    symbol_type: str,
    database: Annotated[Session, Depends(get_db)],
    days: Annotated[int, Query(ge=5, le=500)] = 250,
    sort_by: str = "annualized_return_pct",
    direction: str = "desc",
    min_annualized_return_pct: Annotated[float | None, Query(ge=0)] = None,
    max_annualized_volatility_pct: Annotated[float | None, Query(ge=0)] = None,
    min_sharpe: float | None = None,
) -> dict[str, object]:
    try:
        return _comparison_payload(
            symbols,
            symbol_type,
            database,
            days,
            sort_by,
            direction,
            min_annualized_return_pct=min_annualized_return_pct,
            max_annualized_volatility_pct=max_annualized_volatility_pct,
            min_sharpe=min_sharpe,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/filters")
def filters_page(
    request: Request,
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    saved = database.execute(
        select(SavedFilter).where(SavedFilter.user_id == user.id).order_by(SavedFilter.name)
    ).scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="filters.html",
        context={"title": "筛选", "user": user, "saved": saved},
    )


@app.post("/filters")
def create_filter(
    request: Request,
    name: Annotated[str, Form()],
    symbols: Annotated[str, Form()],
    symbol_type: Annotated[str, Form()],
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
    min_annualized_return_pct: Annotated[float | None, Form()] = None,
    max_annualized_volatility_pct: Annotated[float | None, Form()] = None,
    min_sharpe: Annotated[float | None, Form()] = None,
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    name = name.strip()
    if not name or len(name) > 50:
        return _error_page(request, "filters.html", "筛选名称应为 1 到 50 个字符", 422)
    try:
        normalized_type = "stock" if symbol_type == "stock" else "fund"
        validate_symbol(symbols.split(",")[0], normalized_type)
    except ValueError as error:
        return _error_page(request, "filters.html", str(error), 422)
    saved = SavedFilter(
        user_id=user.id,
        name=name,
        symbol_type=normalized_type,
        symbols=symbols.strip(),
        min_annualized_return_pct=min_annualized_return_pct,
        max_annualized_volatility_pct=max_annualized_volatility_pct,
        min_sharpe=min_sharpe,
    )
    database.add(saved)
    database.commit()
    return RedirectResponse("/filters", status_code=303)


@app.post("/filters/{filter_id}/delete")
def delete_filter(
    filter_id: int,
    user: Annotated[User | None, Depends(get_current_user)],
    database: Annotated[Session, Depends(get_db)],
) -> Response:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    saved = database.get(SavedFilter, filter_id)
    if saved and saved.user_id == user.id:
        database.delete(saved)
        database.commit()
    return RedirectResponse("/filters", status_code=303)
