from fastapi import FastAPI

from .config import Settings, get_settings
from .errors import install_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    # Keep every route, including generated docs, under /api for a single frontend proxy prefix.
    app = FastAPI(
        title="Model Matchmakers backend", version="0.0.0",
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    install_error_handlers(app)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.model_mode}

    return app


app = create_app()
