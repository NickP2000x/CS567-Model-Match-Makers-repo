from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import MockAgent, ModelAgent
from .config import Settings, get_settings
from .errors import install_error_handlers
from .models import build_clients
from .router import MockRouter, RouteLLMRouter, load_routellm_scorer
from .routes import router
from .store import Store, system_clock


def create_app(settings: Settings | None = None, clock: Callable[[], int] = system_clock,
               agent: MockAgent | ModelAgent | None = None,
               checkpoint_router: MockRouter | RouteLLMRouter | None = None) -> FastAPI:
    settings = settings or get_settings()
    if checkpoint_router is None:
        checkpoint_router = MockRouter() if settings.router_mode == "mock" else RouteLLMRouter(
            settings.routellm_router, settings.router_threshold,
            load_routellm_scorer(settings.routellm_router,
                                 settings.openai_api_key.get_secret_value() if settings.openai_api_key else None))
    if agent is None:
        agent = (ModelAgent(build_clients(settings), settings.agent_max_steps)
                 if settings.model_mode == "real" else MockAgent())
    # Keep every route, including generated docs, under /api for a single frontend proxy prefix.
    app = FastAPI(
        title="Model Matchmakers backend", version="0.0.0",
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    # The database is created and seeded on first use, not at import time.
    app.state.agent = agent
    app.state.router = checkpoint_router
    app.state.store = Store(settings.resolved_database_path, clock, simulated=agent.simulated,
                            router_simulated=isinstance(checkpoint_router, MockRouter))
    install_error_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                       allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type"])

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.model_mode, "router": settings.router_mode}

    app.include_router(router)
    return app


app = create_app()
