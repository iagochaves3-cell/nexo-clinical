"""Live retrieval, with provenance. A retrieved paper is not clinical approval."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
REVIEW_URL = "https://api.openai.com/v1/responses"
MAX_RESPONSE = 2_000_000


class ProviderUnavailable(Exception):
    """Safe error code only; never retain upstream bodies or credentials."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url: str, *, payload: dict | None = None,
                 token: str | None = None, timeout: int = 20) -> dict:
    # Fixed upstreams: callers cannot cause SSRF or forward a key to another host.
    if not (url.startswith(SEARCH_URL + "?") or url == REVIEW_URL):
        raise ProviderUnavailable("unsupported_upstream")
    if token is not None and url != REVIEW_URL:
        raise ProviderUnavailable("credential_destination_mismatch")
    headers = {"Accept": "application/json", "User-Agent": "NexoClinical/3.1 evidence-pilot"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        headers["Content-Type"] = "application/json"
    try:
        with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers), timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ProviderUnavailable("upstream_response_too_large")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ProviderUnavailable("upstream_invalid_schema")
            return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderUnavailable("upstream_request_failed") from None


def reject_identifiers(value: str) -> str:
    # Defense in depth, not anonymization. The caller must supply deidentified data.
    if re.search(r"https?://|\bwww\.|@|\b(?:cpf|cns|prontu[aá]rio|patient.?id|"
                 r"nome|name|email|telefone|address|endere[cç]o|nascimento|birth)\s*[:=]|"
                 r"\b\d{8,}\b|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", value, re.I):
        raise ValueError("Remova identificadores pessoais e URLs do texto clínico.")
    return value.strip()


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=3, max_length=300)
    deidentified: Literal[True]
    limit: int = Field(default=5, ge=1, le=10, strict=True)

    @field_validator("query")
    @classmethod
    def safe_query(cls, value: str) -> str:
        value = reject_identifiers(value)
        # Biomedical terms only. Do not accept provider query syntax or patient data.
        if not re.fullmatch(r"[^\W\d_][\w\s\-'/().,]*", value, re.UNICODE) or any(c.isdigit() for c in value):
            raise ValueError("Use somente termos biomédicos, sem números ou sintaxe de consulta.")
        return value


def plain_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


@dataclass(frozen=True)
class RetrievedSource:
    source_id: str
    pmid: str
    doi: str | None
    title: str
    publication_date: str | None
    publication_types: list[str]
    url: str
    retrieved_at: str
    content_sha256: str
    abstract: str
    retrieval_scope: str = "bibliographic_record_and_abstract"

    def public(self) -> dict:
        record = asdict(self)
        record["abstract_available"] = bool(record.pop("abstract"))
        record["clinical_applicability_verified"] = False
        return record


def search_evidence(request: SearchRequest) -> dict:
    # Separate input terms from the provider's query language; never include context.
    words = re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", request.query, re.UNICODE)
    query = " AND ".join('"' + word + '"' for word in words) + " AND SRC:MED"
    url = SEARCH_URL + "?" + urlencode({
        "query": query, "format": "json", "resultType": "core", "pageSize": request.limit,
    })
    data = request_json(url)
    try:
        count = data["hitCount"]
        records = data["resultList"]["result"]
        if not isinstance(count, int) or count < 0 or not isinstance(records, list):
            raise ValueError()
        retrieved_at = datetime.now(timezone.utc).isoformat()
        sources = []
        seen = set()
        for record in records:
            pmid = record.get("pmid", "")
            if record.get("source") != "MED" or not re.fullmatch(r"\d+", pmid):
                continue
            if pmid in seen:
                continue
            seen.add(pmid)
            pubtypes = record.get("pubTypeList", {}).get("pubType", [])
            if not isinstance(pubtypes, list) or not all(isinstance(x, str) for x in pubtypes):
                raise ValueError()
            # Exclude withdrawn/retracted records rather than silently citing them.
            if any("retract" in x.casefold() or "withdraw" in x.casefold() for x in pubtypes):
                continue
            title = plain_text(record["title"])
            abstract = plain_text(record.get("abstractText", ""))[:24000]
            doi = record.get("doi")
            if doi is not None and (not isinstance(doi, str) or not re.fullmatch(r"10\.\d{4,9}/\S+", doi)):
                doi = None
            content_hash = hashlib.sha256((title + "\n" + abstract).encode()).hexdigest()
            sources.append(RetrievedSource(
                source_id="pubmed:" + pmid, pmid=pmid, doi=doi, title=title,
                publication_date=record.get("firstPublicationDate"), publication_types=pubtypes,
                url="https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/",
                retrieved_at=retrieved_at, content_sha256=content_hash, abstract=abstract,
            ))
        return {"provider": "Europe PMC / PubMed records", "query": request.query,
                "executed_query": query, "retrieved_at": retrieved_at, "hit_count": count,
                "sources": sources[:request.limit]}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ProviderUnavailable("upstream_invalid_schema") from None


def public_search(result: dict) -> dict:
    return {**result, "sources": [source.public() for source in result["sources"]],
            "clinical_validated": False,
            "limitations": ["Busca bibliográfica, não revisão sistemática ou aprovação clínica.",
                            "Registros e resumos não confirmam doses nem apresentações brasileiras.",
                            "Cobertura de protocolos locais e bulas ANVISA ainda não implementada."]}
