import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from buque.api.admin import router as admin_router
from buque.api.rules import router as rules_router
from buque.api.routes import router
from buque.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title="补雀 BuQue API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(rules_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "buque.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
