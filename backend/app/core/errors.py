"""Registro de erros da API.

Cada falha recebe um código curto (`ECT-402`) e uma referência única
(`ECT-402 · 7F3A21`) que o cliente informa ao suporte. O evento fica gravado em
`error_events` para que o atendimento consiga achar a ocorrência depois.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.dependencies import get_database

logger = logging.getLogger("ecotwin")

CODES = {
    400: "ECT-400",
    401: "ECT-401",
    402: "ECT-402",
    403: "ECT-403",
    404: "ECT-404",
    409: "ECT-409",
    415: "ECT-415",
    422: "ECT-422",
    500: "ECT-500",
}


async def owner_of(request: Request) -> str | None:
    """O usuário pode vir no cabeçalho, na query ou no corpo, conforme a rota."""
    from_request = request.headers.get("X-User-Id") or request.query_params.get("owner_id") or request.query_params.get("user_id")
    if from_request:
        return from_request
    if not request.headers.get("content-type", "").startswith("application/json"):
        return None
    try:
        body = await request.json()
    except Exception:
        return None
    if isinstance(body, dict):
        owner = body.get("owner_id") or body.get("user_id")
        return owner if isinstance(owner, str) else None
    return None


def record(request: Request, status_code: int, detail: str, owner_id: str | None) -> dict[str, str]:
    code = CODES.get(status_code, f"ECT-{status_code}")
    reference = uuid4().hex[:6].upper()
    event = {
        "id": str(uuid4()),
        "reference": reference,
        "code": code,
        "status_code": status_code,
        "method": request.method,
        "path": request.url.path,
        "owner_id": owner_id,
        "detail": detail,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.warning("%s %s %s %s -> %s", code, reference, request.method, request.url.path, detail)
    try:
        get_database().save_error_event(event)
    except Exception:  # o registro do erro nunca pode derrubar a resposta
        logger.exception("Falha ao gravar o evento de erro %s", reference)
    return {"code": code, "reference": reference}


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        detail = error.detail if isinstance(error.detail, str) else "Não foi possível concluir a operação."
        if error.status_code < 400:
            return JSONResponse(status_code=error.status_code, content={"detail": detail})
        marks = record(request, error.status_code, detail, await owner_of(request))
        return JSONResponse(status_code=error.status_code, content={"detail": detail, **marks}, headers=getattr(error, "headers", None))

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        problems = [
            f"{'.'.join(str(part) for part in item.get('loc', ())[1:]) or 'corpo'}: {item.get('msg', 'valor inválido')}"
            for item in error.errors()
        ]
        detail = "; ".join(problems) or "Dados inválidos."
        marks = record(request, 422, detail, await owner_of(request))
        return JSONResponse(status_code=422, content={"detail": detail, **marks})

    @application.exception_handler(Exception)
    async def unhandled_error(request: Request, error: Exception) -> JSONResponse:
        marks = record(request, 500, f"{type(error).__name__}: {error}", await owner_of(request))
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro inesperado no servidor. Informe o código ao suporte.", **marks},
        )
