from nexo_clinical.registry import SourceRegistry

def test_registry_loads():
    r=SourceRegistry(); assert r.registry_version=="1.0.0"; assert r.get("WHO_SMART_GUIDELINES").status=="active"
def test_search(): assert SourceRegistry().search("FHIR")
