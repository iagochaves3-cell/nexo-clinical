from __future__ import annotations
import hashlib, json
from importlib.resources import files
from pathlib import Path
from typing import Iterable
from .models import SourceRecord

class RegistryError(ValueError): pass

class SourceRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(str(files("nexo_clinical.data").joinpath("source_registry.json")))
        self._records: dict[str, SourceRecord] = {}
        self.registry_version = "unknown"
        self.load()

    def load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.registry_version = raw.get("registry_version", "unknown")
        self._records = {r["source_id"]: SourceRecord.model_validate(r) for r in raw.get("sources", [])}

    def get(self, source_id: str) -> SourceRecord:
        try: return self._records[source_id]
        except KeyError as e: raise RegistryError(f"Fonte não registrada: {source_id}") from e

    def list(self, *, status: str | None = "active", scope: str | None = None) -> list[SourceRecord]:
        out = list(self._records.values())
        if status is not None: out = [r for r in out if r.status == status]
        if scope: out = [r for r in out if scope.lower() in {s.lower() for s in r.scope}]
        return sorted(out, key=lambda r: (r.organization, r.title))

    def search(self, query: str) -> list[SourceRecord]:
        q=query.casefold()
        return [r for r in self.list(status=None) if q in " ".join([r.title,r.organization,r.evidence_role,*r.scope]).casefold()]

    def validate_references(self, source_ids: Iterable[str]) -> list[str]:
        return [sid for sid in source_ids if sid not in self._records]

    def provenance(self, source_ids: Iterable[str]) -> list[dict]:
        return [self.get(s).model_dump() for s in source_ids]
