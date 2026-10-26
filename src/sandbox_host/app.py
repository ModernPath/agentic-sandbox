"""Sandbox web host: one database, one interface, many agents."""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Mapping, Optional, Sequence
from urllib.parse import quote

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from .config import HostSettings
from sandbox_blocks.config import Settings as ModelSettings
from sandbox_blocks.errors import ConfigurationError, ProviderError

from .auth import SESSION_COOKIE, LoginThrottle, authenticate, create_session, delete_session, session_user
from .database import database_status
from .errors import AgentInputError, ServiceUnavailable
from .migrations import apply_agent_migrations
from .registry import AgentContext, AgentSpec, validate_registry
from . import chat as common_chat
from .cli_bridge import default_pythonpath
from sandbox_blocks.llm import build_llm

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ATTACHMENT_ID = re.compile(r"^[0-9a-f-]{36}$")

logger = logging.getLogger("sandbox_host")
INDEX_HTML = Path(__file__).parent / "static" / "index.html"
LOGIN_HTML = Path(__file__).parent / "static" / "login.html"
HOST_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
HOST_MIGRATION_NAME = "sandbox-host"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/login"}
PUBLIC_PREFIXES = ("/static/",)
STATIC_DIR = Path(__file__).parent / "static"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    attachment_ids: list[str] = Field(default_factory=list, max_length=5)
    agent: Optional[str] = Field(default=None, max_length=40)


class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=1000)


def create_app(settings: HostSettings, agents: Sequence[AgentSpec] = (), engine: Optional[Engine] = None,
               services: Optional[Mapping[str, object]] = None,
               model_settings: Optional[ModelSettings] = None) -> FastAPI:
    validate_registry(agents)
    if not settings.is_loopback():
        logger.warning("Sandbox host is bound to %s. Serve it over HTTPS (set SANDBOX_COOKIE_SECURE=true) "
                       "or keep it on loopback.", settings.host)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.engine is not None:
            apply_agent_migrations(app.state.engine, HOST_MIGRATION_NAME, HOST_MIGRATIONS_DIR)
            for agent in agents:
                if agent.migrations_dir is not None:
                    apply_agent_migrations(app.state.engine, agent.name, agent.migrations_dir)
        yield

    app = FastAPI(title="Agentic Sandbox", docs_url="/api/docs", openapi_url="/api/openapi.json",
                  lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.services = dict(services or {})
    app.state.model_settings = model_settings or ModelSettings.from_env()
    app.state.agents = list(agents)
    app.state.cookie_secure = os.environ.get("SANDBOX_COOKIE_SECURE", "false").lower() == "true"
    app.state.throttle = LoginThrottle()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if request.method not in SAFE_METHODS and request.headers.get("x-sandbox-request") != "1":
            return JSONResponse(status_code=403, content={"error": "Missing X-Sandbox-Request header"})
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)
        if app.state.engine is None:
            return JSONResponse(status_code=503, content={"error": "Sign-in is not configured. Set DATABASE_URL."})
        user = await run_in_threadpool(session_user, app.state.engine, request.cookies.get(SESSION_COOKIE))
        if user is None:
            if path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"error": "Sign in required"})
            return RedirectResponse(f"/login?next={quote(path)}", status_code=303)
        request.state.user = user
        return await call_next(request)

    @app.get("/login", include_in_schema=False)
    def login_page() -> FileResponse:
        return FileResponse(LOGIN_HTML, media_type="text/html")

    @app.post("/api/auth/login")
    def login(payload: LoginRequest) -> JSONResponse:
        engine = app.state.engine
        if engine is None:
            raise ServiceUnavailable("Sign-in is not configured. Set DATABASE_URL.")
        name = payload.username.strip().lower()
        if app.state.throttle.blocked(name):
            return JSONResponse(status_code=429, content={"error": "Too many attempts. Try again in 15 minutes."})
        user = authenticate(engine, payload.username, payload.password)
        if user is None:
            app.state.throttle.record_failure(name)
            return JSONResponse(status_code=401, content={"error": "Invalid username or password"})
        app.state.throttle.clear(name)
        token = create_session(engine, user["id"])
        response = JSONResponse(content={"username": user["username"]})
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE_SECONDS, httponly=True,
                            samesite="strict", secure=app.state.cookie_secure, path="/")
        return response

    @app.post("/api/auth/logout")
    def logout(request: Request) -> JSONResponse:
        delete_session(app.state.engine, request.cookies.get(SESSION_COOKIE))
        response = JSONResponse(content={"ok": True})
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict",
                               secure=app.state.cookie_secure)
        return response

    @app.get("/api/auth/me")
    def me(request: Request) -> dict:
        return {"username": request.state.user["username"]}

    from .governance import router as governance_router
    app.include_router(governance_router, prefix="/api", tags=["governance"])
    from .crm_api import router as crm_router
    app.include_router(crm_router, prefix="/api", tags=["crm"])

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(INDEX_HTML, media_type="text/html")

    def chat_model():
        injected = app.state.services.get("chat", {})
        if injected.get("llm") is not None:
            return injected["llm"]
        try:
            return build_llm(app.state.model_settings)
        except ConfigurationError:
            raise ServiceUnavailable("No model is configured. Set SANDBOX_LLM_PROVIDER and its key.") from None

    def cli_environ() -> dict:
        environ = dict(os.environ)
        environ.setdefault("PYTHONPATH", default_pythonpath())
        environ["DATABASE_URL"] = app.state.engine.url.render_as_string(hide_password=False)
        return environ

    @app.post("/api/chat")
    def chat_turn(payload: ChatRequest, request: Request) -> dict:
        if app.state.engine is None:
            raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
        if any(not ATTACHMENT_ID.match(item) for item in payload.attachment_ids):
            raise AgentInputError(422, "Attachment ids must be file ids returned by the upload.")
        llm = chat_model()
        specs = app.state.agents
        if payload.agent:
            specs = [spec for spec in specs if spec.name == payload.agent]
            if not specs:
                raise AgentInputError(422, "That agent is not registered.")
        tools = common_chat.collect_tools(specs, app.state.engine, app.state.services,
                                          app.state.model_settings, llm)
        tools.append(common_chat.make_cli_tool(specs, app.state.engine, cli_environ()))
        if not payload.agent:
            from .crm_api import build_tools as crm_tools

            tools.extend(crm_tools(app.state.engine, request.state.user["username"]))
        return common_chat.reply(llm, tools, payload.message, [turn.model_dump() for turn in payload.history],
                                 payload.attachment_ids, common_chat.system_prompt(specs))

    @app.post("/api/chat/attachments", status_code=201)
    async def upload_attachment(file: UploadFile = File(...)) -> dict:
        if app.state.engine is None:
            raise ServiceUnavailable("Storage is not configured. Set DATABASE_URL.")
        spec = next((agent for agent in app.state.agents if agent.attach is not None), None)
        if spec is None:
            raise AgentInputError(404, "No agent accepts attachments.")
        data = await file.read(MAX_ATTACHMENT_BYTES + 1)
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise AgentInputError(413, "Files must be 10 MB or smaller.")
        context = AgentContext(spec.name, app.state.engine, app.state.services.get(spec.name),
                               app.state.model_settings)
        return spec.attach(context, file.filename or "upload", data)

    @app.exception_handler(ServiceUnavailable)
    def _unavailable(request, error: ServiceUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": str(error)})

    @app.exception_handler(AgentInputError)
    def _input(request, error: AgentInputError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"error": error.message})

    @app.exception_handler(ConfigurationError)
    def _configuration(request, error: ConfigurationError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": str(error)})

    @app.exception_handler(ProviderError)
    def _provider(request, error: ProviderError) -> JSONResponse:
        # Provider messages can echo upstream text; return a fixed message and keep details in logs.
        logger.warning("Provider call failed: %s", error)
        return JSONResponse(status_code=502, content={
            "error": "The model or search provider failed. Check the sandbox logs and provider configuration."})

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "database": database_status(app.state.engine)}

    @app.get("/api/agents")
    def list_agents() -> dict:
        return {"agents": [_describe(agent) for agent in agents]}

    for agent in agents:
        app.include_router(agent.router, prefix=f"/api/agents/{agent.name}", tags=[agent.name])
        if agent.ui_dir is not None:
            app.mount(f"/agents/{agent.name}", StaticFiles(directory=agent.ui_dir, html=True),
                      name=f"ui-{agent.name}")
    return app


def _describe(agent: AgentSpec) -> dict:
    return {
        "name": agent.name,
        "title": agent.title,
        "description": agent.description,
        "api_base": f"/api/agents/{agent.name}",
        "ui_path": f"/agents/{agent.name}/" if agent.ui_dir is not None else None,
        "has_panel": agent.has_panel,
    }
