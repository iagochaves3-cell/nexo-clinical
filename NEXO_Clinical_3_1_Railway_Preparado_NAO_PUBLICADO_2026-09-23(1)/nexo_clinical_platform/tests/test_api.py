from nexo_clinical import __version__
import os
os.environ["NEXO_CREATE_APP"]="1"
from fastapi.testclient import TestClient
from nexo_clinical.api import create_app

def test_health():
    c=TestClient(create_app()); r=c.get('/health'); assert r.status_code==200; assert r.json()['version']==__version__
def test_route():
    c=TestClient(create_app()); r=c.post('/v1/orchestrate',json={'text':'ECG com taquicardia'}); assert r.status_code==200; assert 'Cardiologia e ECG' in r.json()['specialists']
