"""Errores de aplicación y su traducción a una respuesta uniforme.

Todas las respuestas de error usan ``application/problem+json`` con los mismos
campos. Nunca incluyen trazas, rutas físicas ni secretos.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging.setup import correlation_id_var

PROBLEM_MEDIA_TYPE = "application/problem+json"


class AppError(Exception):
    """Error esperado de negocio o de acceso."""

    status_code = 400
    code = "error"
    title = "Solicitud no válida"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title


class NotFoundError(AppError):
    # También se usa cuando el recurso existe pero el usuario no tiene acceso,
    # para no revelar su existencia (sección 11 de la arquitectura).
    status_code = 404
    code = "no_encontrado"
    title = "Recurso no encontrado"


class AccessHiddenError(NotFoundError):
    """El recurso existe, pero el usuario no tiene ningún acceso a él.

    La respuesta es idéntica a la de un recurso inexistente; la diferencia es
    que el intento queda auditado como acceso denegado.
    """


class PermissionDeniedError(AppError):
    status_code = 403
    code = "sin_permiso"
    title = "Operación no permitida"


class ConflictError(AppError):
    status_code = 409
    code = "conflicto"
    title = "El recurso cambió o ya existe"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validacion"
    title = "Datos no válidos"


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "no_autenticado"
    title = "Inicia sesión para continuar"


class InvalidCredentialsError(AppError):
    # Mismo mensaje para correo inexistente, contraseña errónea, cuenta inactiva
    # o bloqueada: no se revela cuál fue el motivo.
    status_code = 401
    code = "credenciales_invalidas"
    title = "Correo o contraseña incorrectos"


class CsrfError(AppError):
    status_code = 403
    code = "csrf"
    title = "Solicitud no verificada"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "servicio_no_disponible"
    title = "Servicio no disponible"


def build_problem(
    status: int, code: str, title: str, detail: str, **extra: object
) -> dict[str, object]:
    body: dict[str, object] = {
        "type": f"urn:reclutamiento:error:{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "correlation_id": correlation_id_var.get(),
    }
    body.update(extra)
    return body


def internal_error_problem() -> dict[str, object]:
    return build_problem(
        500,
        "error_interno",
        "Error interno",
        "Ocurrió un error inesperado. Usa el identificador de correlación para reportarlo.",
    )


def _response(status: int, code: str, title: str, detail: str, **extra: object) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=build_problem(status, code, title, detail, **extra),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def problem_response(exc: AppError) -> JSONResponse:
    return _response(exc.status_code, exc.code, exc.title, exc.detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de errores esperados.

    Los errores inesperados los atiende ``RequestContextMiddleware``, para que la
    respuesta 500 conserve el identificador de correlación.
    """

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return problem_response(exc)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = "Recurso no encontrado" if exc.status_code == 404 else "Error de solicitud"
        return _response(exc.status_code, f"http_{exc.status_code}", title, title)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"campo": ".".join(str(p) for p in err["loc"]), "mensaje": err["msg"]}
            for err in exc.errors()
        ]
        return _response(
            422, "validacion", "Datos no válidos", "Revisa los campos indicados.", errors=errors
        )
