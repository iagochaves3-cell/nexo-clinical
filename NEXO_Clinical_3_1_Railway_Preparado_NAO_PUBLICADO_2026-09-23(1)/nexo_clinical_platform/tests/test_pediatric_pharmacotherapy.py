from nexo_clinical.pediatric_pharmacotherapy import ALLOWED_ADJUNCT_TARGETS,RegimenEligibility,ResolutionState,diagnosis_linked_adjuncts
def test_dx_link():
 r=RegimenEligibility("r","m",("dx",),"adjunct","documented_symptom",("s",),True,"COMPLETE","PASSED","drug")
 assert diagnosis_linked_adjuncts([r],"dx")==[r]
 assert diagnosis_linked_adjuncts([r],"other")==[]
def test_adjunct_requires_allowed_target():
 allowed=RegimenEligibility("allowed","m",("dx",),"adjunct","documented_symptom",("s",),True,"COMPLETE","PASSED","drug")
 blocked=RegimenEligibility("blocked","m",("dx",),"adjunct","unsupported_target",("s",),True,"COMPLETE","PASSED","drug")
 assert diagnosis_linked_adjuncts([allowed,blocked],"dx")==[allowed]
 assert "documented_symptom" in ALLOWED_ADJUNCT_TARGETS
def test_resolution_states_include_clinical_contraindication():
 assert ResolutionState.CONTRAINDICATED_CLINICAL=="CONTRAINDICATED_CLINICAL"
