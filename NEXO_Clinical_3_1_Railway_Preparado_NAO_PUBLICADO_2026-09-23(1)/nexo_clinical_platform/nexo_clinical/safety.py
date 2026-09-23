from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class SafetyFinding:
    code: str
    severity: str
    message: str
    blocking: bool=False

class SafetyPipeline:
    HIGH_ALERT=("adrenalina","noradrenalina","insulina","heparina","vasopressina","midazolam","fentanil","morfina","potássio")
    def evaluate(self, text: str, context: dict[str,Any] | None=None, citations: list | None=None) -> list[SafetyFinding]:
        ctx=context or {}; findings=[]; low=text.casefold()
        if any(d in low for d in self.HIGH_ALERT):
            if not re.search(r"\b(kg|peso)\b", low) and not ctx.get("weight_kg"):
                findings.append(SafetyFinding("MISSING_WEIGHT","critical","Medicamento de alta vigilância sem peso explícito.",True))
            if not citations:
                findings.append(SafetyFinding("MISSING_SOURCE","critical","Recomendação farmacológica de alto risco sem fonte rastreável.",True))
        if re.search(r"\b\d+(?:[.,]\d+)?\s*(mg|mcg|µg|ug|g)\s*/\s*kg", low) and not ctx.get("weight_kg"):
            findings.append(SafetyFinding("WEIGHT_BASED_WITHOUT_WEIGHT","critical","Dose ponderal sem peso informado.",True))
        if "estável por" in low and not citations:
            findings.append(SafetyFinding("UNSOURCED_STABILITY","critical","Estabilidade não pode ser afirmada sem fonte específica.",True))
        if "diagnóstico definitivo" in low and ctx.get("input_quality") in {"poor","insufficient"}:
            findings.append(SafetyFinding("LOW_QUALITY_OVERCLAIM","critical","Conclusão definitiva com dado multimodal insuficiente.",True))
        if re.search(r"\b(?:nome|cpf|telefone|prontuário)\s*[:=]", low):
            findings.append(SafetyFinding("PHI_DETECTED","critical","Possível identificador pessoal detectado; anonimizar antes de pesquisa externa.",True))
        return findings
    def blocked(self, findings: list[SafetyFinding]) -> bool: return any(f.blocking for f in findings)
