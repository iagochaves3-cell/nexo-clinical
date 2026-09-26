from __future__ import annotations
import os
from . import __version__
from .models import ClinicalQuery
from .input_models import ECGInput, LaboratoryInput, SafetyInput
from .orchestrator import ClinicalOrchestrator
from .registry import SourceRegistry
from .multimodal.ecg import assess_ecg_input,qtc_bazett,qtc_fridericia
from .multimodal.laboratory import analyze_laboratory
from .multimodal.imaging import assess_image_input

def create_app():
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.exceptions import RequestValidationError
        from starlette.responses import JSONResponse
    except ImportError as exc: raise RuntimeError("Instale o extra api") from exc
    app=FastAPI(title="Nexo Clinical Knowledge Platform",version=__version__)
    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Do not echo inputs: NaN/Infinity cannot be serialized as JSON and
        # request bodies may contain sensitive text.
        details = [{"type": error["type"], "loc": error["loc"], "msg": error["msg"]}
                   for error in exc.errors()]
        return JSONResponse({"detail": details}, status_code=422)
    reg=SourceRegistry(); orch=ClinicalOrchestrator(reg)
    @app.get("/health")
    def health(): return {"status":"ok","version":__version__,"registry_version":reg.registry_version}
    @app.get("/v1/sources")
    def sources(q:str|None=None): return [x.model_dump() for x in (reg.search(q) if q else reg.list(status=None))]
    @app.post("/v1/orchestrate")
    def orchestrate(query:ClinicalQuery): return orch.prepare(query)
    @app.post("/v1/safety/review")
    def safety(payload:SafetyInput):
        findings=orch.safety.evaluate(payload.text,payload.context.model_dump(exclude_none=True),payload.citations)
        return {"blocked":orch.safety.blocked(findings),"findings":[f.__dict__ for f in findings]}
    @app.post("/v1/multimodal/ecg/assess")
    def ecg(payload:ECGInput): return assess_ecg_input(payload.model_dump(exclude_none=True))
    @app.get("/v1/multimodal/ecg/qtc")
    def qtc(qt_ms:float=Query(gt=0, allow_inf_nan=False),rr_ms:float=Query(gt=0, allow_inf_nan=False)):
        try:
            return {"bazett_ms":qtc_bazett(qt_ms,rr_ms),"fridericia_ms":qtc_fridericia(qt_ms,rr_ms)}
        except (ValueError, ArithmeticError):
            raise HTTPException(422, "Valores fora da capacidade numérica do cálculo.") from None
    @app.post("/v1/multimodal/laboratory/analyze")
    def lab(payload:LaboratoryInput):
        try:
            return analyze_laboratory(payload.model_dump(exclude_none=True))
        except (ValueError, ArithmeticError):
            raise HTTPException(422, "Valores fora da capacidade numérica do cálculo.") from None
    @app.post("/v1/multimodal/imaging/assess")
    def imaging(payload:dict): return assess_image_input(payload)
    from .evidence_api import register_evidence_routes
    register_evidence_routes(app)
    return app

def main():
    from deploy.server import main as protected_main
    protected_main()

# ASGI público: use deploy.server:create_app com --factory.
# create_app neste módulo é uma fábrica interna sem autenticação.
