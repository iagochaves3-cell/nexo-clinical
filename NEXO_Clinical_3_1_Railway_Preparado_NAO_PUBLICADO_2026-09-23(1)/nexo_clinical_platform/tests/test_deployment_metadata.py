import tomllib
import pytest
from fastapi.testclient import TestClient
from nexo_clinical import __version__
from deploy.server import create_app

TOKEN = "test-only-" + "m" * 48

@pytest.mark.parametrize("path,key", [("/health", "version"), ("/", "backend_version"), ("/openapi.json", "info")])
def test_runtime_and_package_versions_match(monkeypatch, path, key):
    monkeypatch.setenv("NEXO_API_TOKEN", TOKEN)
    expected = tomllib.loads(open("pyproject.toml", encoding="utf-8").read())["project"]["version"]
    assert __version__ == expected == "3.1.0"
    r = TestClient(create_app()).get(path, headers={"Authorization": "Bearer " + TOKEN})
    assert r.status_code == 200
    actual = r.json()[key]
    if key == "info": actual = actual["version"]
    assert actual == expected
