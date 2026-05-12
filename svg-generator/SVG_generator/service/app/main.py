import logging

from fastapi import FastAPI

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="SVG Generator",
    description="Сервис генерации учебных SVG-иллюстраций для ЕГЭ",
    version="0.1.0",
)

app.include_router(router)
