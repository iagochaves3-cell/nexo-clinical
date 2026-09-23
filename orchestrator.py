from __future__ import annotations
from .models import ClinicalQuery, ClinicalAnswer, EvidenceCitation
from .registry import SourceRegistry
from .specialists import route_specialists, SPECIALISTS
from .safety import SafetyPipeline

class ClinicalOrchestrator:
    def __init__(self, registry:SourceRegistry|None=None):
        self.registry=registry or SourceRegistry(); self.safety=SafetyPipeline()
    def prepare(self, query:ClinicalQuery)->dict:
        routed=route_specialists(query.text,query.domain_hint)
        domain=routed[0]
        return {"domain":domain,"specialists":[SPECIALISTS[x] for x in routed],"source_registry_version":self.registry.registry_version,
                "privacy_gate":"do_not_externalize_identifiers"}
    def finalize(self, query:ClinicalQuery, answer_text:str, source_ids:list[str], calculations:list[dict]|None=None)->ClinicalAnswer:
        citations=[EvidenceCitation(source_id=s.source_id,title=s.title,organization=s.organization,url=s.canonical_url,last_verified=s.last_verified,version=s.version) for s in [self.registry.get(x) for x in source_ids]]
        findings=self.safety.evaluate(answer_text,query.patient_context,citations)
        prep=self.prepare(query)
        limitations=[]
        if self.safety.blocked(findings): limitations.append("Resposta bloqueada para revisão clínica por achado crítico de segurança.")
        return ClinicalAnswer(answer=answer_text,domain=prep["domain"],specialists=prep["specialists"],citations=citations,
                              calculations=calculations or [],safety_findings=[f.__dict__ for f in findings],limitations=limitations,
                              protocol_versions=[f"source-registry:{self.registry.registry_version}"])
