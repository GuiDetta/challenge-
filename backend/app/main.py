import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.router import api_router
from app.core.config import CORS_ORIGINS
from app.core.errors import register_error_handlers


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    application = FastAPI(title="GoodWe EV Plan API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    register_error_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
