from collections.abc import Callable

from fastapi import FastAPI

from .config import Settings, get_settings
from .errors import install_error_handlers
from .routes import router
from .store import Store, system_clock


def create_app(settings: Settings | None = None, clock: Callable[[], int] = system_clock) -> FastAPI:
    settings = settings or get_settings()
    # Keep every route, including generated docs, under /api for a single frontend proxy prefix.
    app = FastAPI(
        title="Model Matchmakers backend", version="0.0.0",
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    # The database is created and seeded on first use, not at import time.
    app.state.store = Store(settings.resolved_database_path, clock)
    install_error_handlers(app)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.model_mode}

    app.include_router(router)
    return app


app = create_app()
