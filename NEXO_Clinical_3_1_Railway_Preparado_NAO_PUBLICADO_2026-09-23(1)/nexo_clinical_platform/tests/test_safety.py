from nexo_clinical.safety import SafetyPipeline

def test_high_alert_blocks_without_source():
    p=SafetyPipeline(); f=p.evaluate("Noradrenalina 0,1 mcg/kg/min",{"weight_kg":10},[]); assert p.blocked(f)
def test_phi_blocks():
    p=SafetyPipeline(); assert p.blocked(p.evaluate("Nome: João CPF: 123",{},[]))
