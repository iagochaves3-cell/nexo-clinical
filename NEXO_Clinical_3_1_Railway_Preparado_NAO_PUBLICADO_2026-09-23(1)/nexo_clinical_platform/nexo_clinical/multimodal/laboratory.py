from __future__ import annotations
from typing import Any
from math import isfinite
from ..input_models import LaboratoryInput

def anion_gap(na:float, cl:float, hco3:float, k:float|None=None)->float:
    return round((na+(k or 0))-cl-hco3,2)
def corrected_sodium(na:float, glucose_mg_dl:float, factor:float=1.6)->float:
    return round(na + factor*((glucose_mg_dl-100)/100),2) if glucose_mg_dl>100 else round(na,2)
def estimated_osmolality(na:float, glucose_mg_dl:float, bun_mg_dl:float)->float:
    return round(2*na + glucose_mg_dl/18 + bun_mg_dl/2.8,2)
def winter_expected_pco2(hco3:float)->dict[str,float]:
    center=1.5*hco3+8
    return {"min":round(center-2,1),"expected":round(center,1),"max":round(center+2,1)}
def analyze_laboratory(data:dict[str,Any])->dict[str,Any]:
    data = LaboratoryInput.model_validate(data).model_dump(exclude_none=True)
    out={"derived":{},"warnings":[]}
    if all(k in data for k in ("na","cl","hco3")): out["derived"]["anion_gap"]=anion_gap(data["na"],data["cl"],data["hco3"],data.get("k"))
    if all(k in data for k in ("na","glucose_mg_dl")): out["derived"]["corrected_sodium"]=corrected_sodium(data["na"],data["glucose_mg_dl"])
    if all(k in data for k in ("na","glucose_mg_dl","bun_mg_dl")): out["derived"]["estimated_osmolality"]=estimated_osmolality(data["na"],data["glucose_mg_dl"],data["bun_mg_dl"])
    if "hco3" in data: out["derived"]["winter_expected_pco2"]=winter_expected_pco2(data["hco3"])
    for result in out["derived"].values():
        values = result.values() if isinstance(result, dict) else [result]
        if not all(isfinite(value) for value in values):
            raise ValueError("Resultado não finito")
    return out
