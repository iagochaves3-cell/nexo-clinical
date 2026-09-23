from nexo_clinical.pediatric_pharmacotherapy import RegimenEligibility,diagnosis_linked_adjuncts
def test_dx_link():
 r=RegimenEligibility("r","m",("dx",),"adjunct","documented_symptom",("s",),True,"COMPLETE","PASSED","drug")
 assert diagnosis_linked_adjuncts([r],"dx")==[r]
 assert diagnosis_linked_adjuncts([r],"other")==[]
