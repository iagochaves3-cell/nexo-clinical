from __future__ import annotations
from .prompts import ORCHESTRATOR_PROMPT, SPECIALIST_PROMPT, REVIEWER_PROMPT
from .specialists import SPECIALISTS

def build_agents(model:str|None=None):
    try:
        from agents import Agent
    except ImportError as exc:
        raise RuntimeError("Instale openai-agents para executar agentes") from exc
    kwargs={"model":model} if model else {}
    specialists={k:Agent(name=v,instructions=SPECIALIST_PROMPT,**kwargs) for k,v in SPECIALISTS.items() if k not in {"safety"}}
    reviewer=Agent(name="Revisor clínico independente",instructions=REVIEWER_PROMPT,**kwargs)
    manager=Agent(name="Nexo Clinical Orchestrator",instructions=ORCHESTRATOR_PROMPT,**kwargs)
    return manager,specialists,reviewer
