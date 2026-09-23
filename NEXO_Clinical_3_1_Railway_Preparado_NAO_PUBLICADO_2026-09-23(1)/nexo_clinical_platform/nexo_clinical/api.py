from __future__ import annotations
import os
from . import __version__
from .models import ClinicalQuery
from .orchestrator import ClinicalOrchestrator
from .registry import SourceRegistry
from .multimodal.ecg import assess_ecg_input,qtc_bazett,qtc_fridericia
from .multimodal.laboratory import analyze_laboratory
from .multimodal.imaging import assess_image_input

def create_app():
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc: raise RuntimeError("Instale o extra api") from exc
    app=FastAPI(title="Nexo Clinical Knowledge Platform",version=__version__)
    reg=SourceRegistry(); orch=ClinicalOrchestrator(reg)
    @app.get("/health")
    def health(): return {"status":"ok","version":__version__,"registry_version":reg.registry_version}
    @app.get("/v1/sources")
    def sources(q:str|None=None): return [x.model_dump() for x in (reg.search(q) if q else reg.list(status=None))]
    @app.post("/v1/orchestrate")
    def orchestrate(query:ClinicalQuery): return orch.prepare(query)
    @app.post("/v1/safety/review")
    def safety(payload:dict):
        findings=orch.safety.evaluate(payload.get("text",""),payload.get("context",{}),payload.get("citations",[]))
        return {"blocked":orch.safety.blocked(findings),"findings":[f.__dict__ for f in findings]}
    @app.post("/v1/multimodal/ecg/assess")
    def ecg(payload:dict): return assess_ecg_input(payload)
    @app.get("/v1/multimodal/ecg/qtc")
    def qtc(qt_ms:float,rr_ms:float): return {"bazett_ms":qtc_bazett(qt_ms,rr_ms),"fridericia_ms":qtc_fridericia(qt_ms,rr_ms)}
    @app.post("/v1/multimodal/laboratory/analyze")
    def lab(payload:dict): return analyze_laboratory(payload)
    @app.post("/v1/multimodal/imaging/assess")
    def imaging(payload:dict): return assess_image_input(payload)
    return app

def main():
    import uvicorn
    uvicorn.run(create_app(),host="0.0.0.0",port=int(os.getenv("PORT","8000")))

app = create_app() if os.getenv("NEXO_CREATE_APP","1")=="1" else None
