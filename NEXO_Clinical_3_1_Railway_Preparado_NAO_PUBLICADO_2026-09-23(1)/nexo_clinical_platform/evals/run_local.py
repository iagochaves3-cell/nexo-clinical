from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from nexo_clinical.models import ClinicalQuery
from nexo_clinical.orchestrator import ClinicalOrchestrator
orch=ClinicalOrchestrator(); failures=[]; results=[]
for line in (ROOT/'evals/cases.jsonl').read_text().splitlines():
    c=json.loads(line)
    if 'input' in c:
        got=orch.prepare(ClinicalQuery(text=c['input']))
        ok=all(x in got['specialists'] for x in c['expect_specialists'])
    else:
        f=orch.safety.evaluate(c['text'],c.get('context',{}),[]); got={'blocked':orch.safety.blocked(f),'findings':[x.__dict__ for x in f]}; ok=got['blocked']==c['expect_blocked']
    results.append({'id':c['id'],'ok':ok,'got':got})
    if not ok: failures.append(c['id'])
out=ROOT/'evals/results'; out.mkdir(exist_ok=True); (out/'latest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(json.dumps({'passed':len(results)-len(failures),'failed':failures},ensure_ascii=False)); raise SystemExit(bool(failures))
