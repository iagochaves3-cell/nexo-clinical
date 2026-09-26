from __future__ import annotations
import argparse, json
from . import __version__
from .registry import SourceRegistry
from .orchestrator import ClinicalOrchestrator
from .models import ClinicalQuery

def main():
    p=argparse.ArgumentParser(prog="nexo-clinical")
    sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("health")
    s=sub.add_parser("sources"); s.add_argument("--query")
    r=sub.add_parser("route"); r.add_argument("text"); r.add_argument("--domain")
    args=p.parse_args(); reg=SourceRegistry()
    if args.cmd=="health": out={"status":"ok","version":__version__,"registry_version":reg.registry_version}
    elif args.cmd=="sources": out=[x.model_dump() for x in (reg.search(args.query) if args.query else reg.list(status=None))]
    else: out=ClinicalOrchestrator(reg).prepare(ClinicalQuery(text=args.text,domain_hint=args.domain))
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
