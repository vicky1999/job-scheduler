import logging

from fastapi import FastAPI
from app.api import api_router
from app.core.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Outputs to a file
        logging.StreamHandler()           # Outputs to the console
    ]
)


app = FastAPI()
app.include_router(api_router)

register_exception_handlers(app=app)

@app.get("/health")
def read_root():
    return "OK"