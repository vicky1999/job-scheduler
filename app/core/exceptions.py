import logging
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse

from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)

class APIBaseException(HTTPException):
    """Base exception class for all custom domain errors."""
    def __init__(self, detail: str, status_code: int = 400):
        self.status_code = status_code
        self.detail = detail
        super().__init__(status_code=status_code, detail=detail)


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(HTTPException)
    async def global_http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            detail = exc.detail.get("message", str(exc.detail))
        else:
            detail = str(exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content={ "detail": detail },
            headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(Exception)
    async def universal_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server error on {request.url.path}: {str(exc)}", exc_info=True)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred on the server.",
            }
        )