from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    matched: bool
    action: str | None
    reason: str
    severity: str = "info"

@dataclass
class ClinicalRule:
    rule_id: str
    domain: str
    predicate: Callable[[dict[str, Any]], bool]
    action: str
    reason: str
    severity: str = "info"

class ClinicalRuleEngine:
    def __init__(self): self._rules: list[ClinicalRule]=[]
    def register(self, rule: ClinicalRule) -> None:
        if any(r.rule_id==rule.rule_id for r in self._rules): raise ValueError("rule_id duplicado")
        self._rules.append(rule)
    def evaluate(self, domain: str, context: dict[str, Any]) -> list[RuleResult]:
        out=[]
        for r in self._rules:
            if r.domain not in {domain,"global"}: continue
            try: matched=bool(r.predicate(context))
            except Exception as exc:
                out.append(RuleResult(r.rule_id,False,None,f"Falha segura: {exc}","error")); continue
            if matched: out.append(RuleResult(r.rule_id,True,r.action,r.reason,r.severity))
        return out
