"""Additive protected routes; original endpoints keep their contracts."""
from threading import BoundedSemaphore

from fastapi import HTTPException

from .evidence import ProviderUnavailable, SearchRequest, public_search, search_evidence
from .evidence_review import ReviewRequest, review_claims


def register_evidence_routes(app):
    slots = BoundedSemaphore(4)

    def execute(operation):
        if not slots.acquire(blocking=False):
            raise HTTPException(429, "research_capacity_exceeded", headers={"Retry-After": "10"})
        try:
            return operation()
        except ProviderUnavailable as exc:
            raise HTTPException(503, str(exc), headers={"Retry-After": "30"}) from None
        finally:
            slots.release()

    @app.post("/v1/evidence/search")
    def evidence_search(payload: SearchRequest):
        return execute(lambda: public_search(search_evidence(payload)))

    @app.post("/v1/clinical/review")
    def clinical_review(payload: ReviewRequest):
        return execute(lambda: review_claims(payload))
