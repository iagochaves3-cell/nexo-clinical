"""Entrada ASGI protegida para piloto técnico. Não é validação clínica."""
from __future__ import annotations

import hmac
import os
import re
from collections.abc import Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 1_048_576
PUBLIC_PATHS = frozenset({"/", "/health"})
INTEGRATION_ROUTES = frozenset({("GET", "/v1/capabilities"),
                               ("POST", "/v1/evidence/search"),
                               ("POST", "/v1/clinical/review")})
SECURITY_HEADERS = [
    (b"cache-control", b"no-store"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"strict-transport-security", b"max-age=31536000"),
    (b"x-nexo-deployment-mode", b"technical-pilot"),
    (b"x-nexo-clinical-validation", b"not-implemented"),
]

class ProtectedAPI:
    """Bearer obrigatório, inclusive na documentação; limite real de corpo."""

    def __init__(self, app: ASGIApp, token: str, integration_token: str = "") -> None:
        self.app = app
        self._token = token.encode("ascii")
        self._integration_token = integration_token.encode("ascii")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                overridden = {name for name, _ in SECURITY_HEADERS}
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in overridden]
                message["headers"] = headers + SECURITY_HEADERS
            await send(message)

        async def reject(code: int, detail: str, **kwargs: Any) -> None:
            await JSONResponse({"detail": detail}, status_code=code, **kwargs)(scope, receive, secure_send)

        if scope.get("path") not in PUBLIC_PATHS:
            values = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
            authorized = False
            if len(values) == 1:
                scheme, separator, supplied = values[0].partition(b" ")
                primary = hmac.compare_digest(supplied, self._token)
                integration = hmac.compare_digest(supplied, self._integration_token)
                scoped = bool(self._integration_token and integration and
                              (scope.get("method"), scope.get("path")) in INTEGRATION_ROUTES)
                authorized = bool(separator and scheme.lower() == b"bearer" and (primary or scoped))
            if not authorized:
                await reject(401, "Credencial de API ausente ou inválida.", headers={"WWW-Authenticate": "Bearer"})
                return

        lengths = [value for name, value in scope.get("headers", []) if name.lower() == b"content-length"]
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit():
                await reject(400, "Content-Length inválido.")
                return
            if int(lengths[0]) > MAX_BODY_BYTES:
                await reject(413, "Corpo excede 1 MiB.")
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                await reject(413, "Corpo excede 1 MiB.")
                return
            if not message.get("more_body", False):
                break
        supplied_body = False

        async def buffered_receive() -> Message:
            nonlocal supplied_body
            if not supplied_body:
                supplied_body = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, secure_send)


def create_app() -> ASGIApp:
    token = os.environ.get("NEXO_API_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        raise RuntimeError("Configure NEXO_API_TOKEN com segredo aleatório de 32 a 256 caracteres URL-safe antes de iniciar.")
    integration_token = os.environ.get("NEXO_INTEGRATION_TOKEN", "")
    if integration_token and (not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", integration_token) or integration_token == token):
        raise RuntimeError("NEXO_INTEGRATION_TOKEN deve ser um segredo URL-safe independente de 32 a 256 caracteres.")
    from nexo_clinical import __version__
    from nexo_clinical.api import create_app as original_app
    app = original_app()

    @app.get("/", include_in_schema=False)
    def service_info() -> dict[str, Any]:
        return {
            "service": "NEXO Clinical",
            "backend_version": __version__,
            "deployment_mode": "technical-pilot",
            "clinical_validation": "not_implemented",
            "notice": "Serviço experimental. Não usar como filtro de aprovação clínica.",
        }

    @app.get("/v1/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "source_registry": True,
            "specialist_routing": True,
            "live_evidence_search": True,
            "evidence_revision": "2026-09-23.1",
            "evidence_search_provider": "Europe PMC / PubMed records",
            "clinical_review": "evidence_bound_draft",
            "review_provider_configured": bool(os.getenv("NEXO_REVIEW_API_KEY") and os.getenv("NEXO_REVIEW_MODEL")),
            "clinical_validation": False,
            "sites_integration_verified": False,
            "original_orchestrate_behavior": "prepare_specialist_routing_only",
        }

    return ProtectedAPI(app, token, integration_token)


def main() -> None:
    import uvicorn
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError as exc:
        raise RuntimeError("PORT deve ser um inteiro.") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT fora da faixa de 1 a 65535.")
    uvicorn.run(create_app(), host="0.0.0.0", port=port, access_log=False,
                server_header=False, limit_concurrency=40, timeout_keep_alive=5)


if __name__ == "__main__":
    main()
