from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Mapping, Any
class ResolutionState(StrEnum):
 READY="READY"; CONTRAINDICATED_AGE="CONTRAINDICATED_AGE"; CONTRAINDICATED_WEIGHT="CONTRAINDICATED_WEIGHT"; NOT_INDICATED_FOR_DIAGNOSIS="NOT_INDICATED_FOR_DIAGNOSIS"; SPECIALIST_ONLY="SPECIALIST_ONLY"; REQUIRES_CRITICAL_INPUT="REQUIRES_CRITICAL_INPUT"; REGULATORY_SUSPENDED="REGULATORY_SUSPENDED"
@dataclass(frozen=True)
class RegimenEligibility:
 regimen_id:str; medication_id:str; diagnosis_ids:tuple[str,...]; role:str; clinical_target:str; source_ids:tuple[str,...]; presentation_verified_brazil:bool; completeness_status:str; triple_audit_status:str; calculation_component:str; active:bool=True
 def executable(self): return bool(self.active and self.source_ids and self.presentation_verified_brazil and self.completeness_status=="COMPLETE" and self.triple_audit_status=="PASSED" and self.calculation_component.strip())
def diagnosis_linked_candidates(regimens:Iterable[RegimenEligibility],diagnosis_id:str,role:str|None=None): return [r for r in regimens if r.active and diagnosis_id in r.diagnosis_ids and (role is None or r.role==role) and r.executable()]
def diagnosis_linked_adjuncts(regimens:Iterable[RegimenEligibility],diagnosis_id:str): return diagnosis_linked_candidates(regimens,diagnosis_id,"adjunct")
