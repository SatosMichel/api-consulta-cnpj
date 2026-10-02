import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


router = APIRouter()
templates = Jinja2Templates(directory="templates")
SESSION_COOKIE = "comercial_session"
SESSION_DURATION_SECONDS = 12 * 60 * 60


def _auth_settings() -> tuple[str, str, str] | None:
    username = os.getenv("COMERCIAL_USERNAME")
    password = os.getenv("COMERCIAL_PASSWORD")
    session_secret = os.getenv("COMERCIAL_SESSION_SECRET")
    if not username or not password or not session_secret or len(session_secret) < 32:
        return None
    return username, password, session_secret


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign_session(username: str, secret: str) -> str:
    expires_at = int(time.time()) + SESSION_DURATION_SECONDS
    payload = f"{username}\n{expires_at}\n{secrets.token_urlsafe(12)}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def is_comercial_session_valid(token: str | None) -> bool:
    settings = _auth_settings()
    if not settings or not token:
        return False

    configured_username, _, session_secret = settings
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = _decode(encoded_payload)
        supplied_signature = _decode(encoded_signature)
        expected_signature = hmac.new(
            session_secret.encode("utf-8"), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return False

        username, expiration, _ = payload.decode("utf-8").split("\n", 2)
        return (
            hmac.compare_digest(username, configured_username)
            and int(expiration) > int(time.time())
        )
    except (ValueError, UnicodeDecodeError):
        return False


def require_comercial_session(request: Request) -> str:
    if not _auth_settings():
        raise HTTPException(
            status_code=503,
            detail=(
                "Autenticação Comercial não configurada. Defina COMERCIAL_USERNAME, "
                "COMERCIAL_PASSWORD e uma COMERCIAL_SESSION_SECRET com ao menos 32 caracteres."
            ),
        )
    if not is_comercial_session_valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(status_code=401, detail="Autenticação necessária para a área Comercial.")
    return os.environ["COMERCIAL_USERNAME"]


def _render_login(request: Request, error: str | None = None, status_code: int = 200):
    settings_missing = _auth_settings() is None
    return templates.TemplateResponse(
        request=request,
        name="comercial_login.html",
        context={
            "error": error,
            "settings_missing": settings_missing,
        },
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _secure_cookie(request: Request) -> bool:
    return request.url.scheme == "https" or os.getenv("RENDER", "").lower() == "true"


@router.get("/comercial/login", response_class=HTMLResponse)
def comercial_login_page(request: Request):
    if is_comercial_session_valid(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/comercial", status_code=303)
    return _render_login(request)


@router.post("/comercial/login", response_class=HTMLResponse)
def comercial_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    settings = _auth_settings()
    if not settings:
        return _render_login(
            request,
            "O acesso ainda não foi configurado no ambiente do servidor.",
            status_code=503,
        )

    expected_username, expected_password, session_secret = settings
    user_matches = hmac.compare_digest(
        username.encode("utf-8"), expected_username.encode("utf-8")
    )
    password_matches = hmac.compare_digest(
        password.encode("utf-8"), expected_password.encode("utf-8")
    )
    if not (user_matches and password_matches):
        return _render_login(request, "Usuário ou senha inválidos.", status_code=401)

    response = RedirectResponse("/comercial", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _sign_session(expected_username, session_secret),
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        secure=_secure_cookie(request),
        samesite="lax",
        path="/",
    )
    return response


@router.post("/comercial/logout")
def comercial_logout(request: Request):
    response = RedirectResponse("/comercial/login", status_code=303)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=_secure_cookie(request),
        samesite="lax",
    )
    return response