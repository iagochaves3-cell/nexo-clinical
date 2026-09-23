from __future__ import annotations
import json
from pathlib import Path
from .models import Recommendation, DrugRecord
from .registry import SourceRegistry, RegistryError

class KnowledgeError(ValueError): pass

class KnowledgePlatform:
    def __init__(self, registry: SourceRegistry | None = None):
        self.registry = registry or SourceRegistry()
        self.recommendations: dict[str, Recommendation] = {}
        self.drugs: dict[str, DrugRecord] = {}

    def add_recommendation(self, item: Recommendation) -> None:
        missing=self.registry.validate_references(item.source_ids)
        if missing: raise KnowledgeError(f"Fontes ausentes: {', '.join(missing)}")
        old=self.recommendations.get(item.recommendation_id)
        if old and old.version == item.version: raise KnowledgeError("Versão duplicada")
        self.recommendations[item.recommendation_id]=item

    def add_drug(self, item: DrugRecord) -> None:
        missing=self.registry.validate_references(item.source_ids)
        if missing: raise KnowledgeError(f"Fontes ausentes: {', '.join(missing)}")
        self.drugs[item.drug_id]=item

    def find_recommendations(self, domain: str, query: str = "") -> list[Recommendation]:
        q=query.casefold()
        return [r for r in self.recommendations.values() if r.status=="validated" and r.domain==domain and (not q or q in (r.title+" "+r.recommendation).casefold())]

    def find_drug(self, name: str) -> DrugRecord | None:
        q=name.casefold()
        for d in self.drugs.values():
            if q == d.generic_name.casefold() or q in {x.casefold() for x in d.aliases}: return d
        return None

    def export_snapshot(self, path: str | Path) -> Path:
        out=Path(path)
        payload={"registry_version": self.registry.registry_version,
                 "recommendations": [x.model_dump(mode="json") for x in self.recommendations.values()],
                 "drugs": [x.model_dump(mode="json") for x in self.drugs.values()]}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
