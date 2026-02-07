from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings.config import get_settings
from settings.logging import setup_logging
from db.supabase import connect_db, close_db
from core.routes.auth import router as auth_router
from core.routes.list import router as list_router
from core.routes.projects import router as projects_router
from core.routes.runs import router as runs_router
from core.routes.issues import router as issues_router
from core.routes.evidence import router as evidence_router
from core.routes.users import router as users_router
from core.routes.categories import router as categories_router
from core.routes.widgets import router as widgets_router


def create_app() -> FastAPI:
    settings = get_settings()

    setup_logging(log_level=settings.LOG_LEVEL)

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        debug=settings.DEBUG,
        docs_url="/docs",          
        redoc_url="/redoc",       
        openapi_url="/openapi.json",
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else ["localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth_router)
    app.include_router(list_router)
    app.include_router(projects_router)
    app.include_router(runs_router)
    app.include_router(issues_router)
    app.include_router(evidence_router)
    app.include_router(users_router)
    app.include_router(categories_router)
    app.include_router(widgets_router)
    

    # Health
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "env": settings.APP_ENV}

    # Lifecycle
    @app.on_event("startup")
    async def on_startup():
        await connect_db()

    @app.on_event("shutdown")
    async def on_shutdown():
        await close_db()

    return app


app = create_app()
