from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import logging
from contextlib import suppress
from starlette.concurrency import run_in_threadpool

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.core.web_files import WebFiles
from sqlalchemy.orm import sessionmaker

from ai_engine.catalog import SignCatalog
from backend.app.api.v1.api import api_router
from backend.app.core.security import AuthRateLimiter
from backend.app.core.settings import Settings
from backend.app.db.database import engine, init_db
from backend.app.db.migrations import require_current_database
from backend.app.services.image_store import ImageStore
from ai_engine.detection import YoloDetector
from backend.app.core.upload_limit import UploadLimitMiddleware
from backend.app.services.policy_service import initialize_policy
from backend.app.services.routing_service import RoutingProvider,make_place_provider
from backend.app.services.lifecycle_service import expire_due_records
from backend.app.services.catalog_service import require_database_catalog


def create_app(database_engine=None, settings: Settings | None = None, *, user_app_directory: Path | None = None) -> FastAPI:
    db_engine = database_engine if database_engine is not None else engine
    settings = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(application):
        if settings.auto_migrate:
            init_db(db_engine)
        else:
            require_current_database(db_engine)
        require_database_catalog(application.state.session_factory, application.state.catalog)
        initialize_policy(application.state.session_factory,settings.confirmation_days)
        def expire():
            with application.state.session_factory() as db: return expire_due_records(db)
        async def lifecycle_job():
            while True:
                await asyncio.sleep(settings.lifecycle_interval_seconds)
                try: await run_in_threadpool(expire)
                except Exception: logging.getLogger(__name__).exception('Lifecycle job failed; will retry next interval')
        await run_in_threadpool(expire)
        task=asyncio.create_task(lifecycle_job())
        try: yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError): await task

    application = FastAPI(
        title="SignSight API - Vietnam Traffic Sign Intelligence Platform",
        description="Traffic sign recognition, mapping and record revalidation. Authenticated roles: user, manager, admin.",
        version="1.1.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.catalog = SignCatalog.from_file(settings.catalog_path)
    application.state.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    application.state.auth_limiter = AuthRateLimiter()
    application.state.image_store = ImageStore(settings.storage_root)
    application.state.detector = YoloDetector(settings.yolo_weights, settings.yolo_device,
                                            confidence=settings.yolo_confidence,
                                            catalog=application.state.catalog,mapping_path=settings.yolo_mapping_path)
    application.state.routing_provider=RoutingProvider(settings.routing_base_url,settings.provider_user_agent)
    application.state.place_provider=make_place_provider(settings)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Validation errors must not echo passwords or other submitted values.
        errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_middleware(UploadLimitMiddleware, max_bytes=settings.max_upload_bytes + 64 * 1024)
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/")
    def root():
        return {
            "project": "SignSight",
            "description": "AI-Powered Traffic Sign Mapping and Navigation Platform",
            "docs_url": "/docs",
            "web_url": "/web/index.html",
            "supported_classes_count": len(application.state.catalog.items),
            "supported_classes": [f"{item['qcvn_code']}: {item['name_vi']}" for item in application.state.catalog.items],
        }

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    application.mount("/web", WebFiles(directory=str(frontend), html=True), name="web")
    # Optional same-origin Flutter preview; API authorization is unchanged.
    user_app = user_app_directory if user_app_directory is not None else Path(__file__).resolve().parents[2] / 'mobile' / 'build' / 'web'
    if user_app.is_dir():
        application.mount('/app', StaticFiles(directory=str(user_app), html=True), name='user-app')
    return application


app = create_app()
