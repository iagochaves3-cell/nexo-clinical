"""Shared focused tests copied alongside each satellite server."""
import http.client
import hashlib
import json
import os
import threading
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

import nexo_client as adapter
import server

TOKEN = "test-only-service-" + "s" * 40
UPSTREAM_TOKEN = "test-only-upstream-" + "u" * 40
ENV = {"NEXO_API_URL": adapter.ORIGIN, "NEXO_INTEGRATION_TOKEN": UPSTREAM_TOKEN}
SEARCH = {"query": "pediatric fluid therapy", "deidentified": True}
PAYLOAD = {"research": SEARCH, "claims": [{"claim_id": "a", "statement": "Synthetic claim."}],
           "patient_context": {"age_months": 48, "weight_kg": 16}}
DRAFT = {"status": "review_draft", "clinical_validated": False,
         "prescribing_authorization": False, "requires_human_review": True}


class AdapterTests(unittest.TestCase):
    def test_original_files_match_manifest(self):
        manifest = json.loads((server.ROOT / "original-sha256.json").read_text())
        for name, expected in manifest.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((server.ROOT / name).read_bytes()).hexdigest(), expected)

    @classmethod
    def setUpClass(cls):
        cls.service = server.make_server("127.0.0.1", 0, TOKEN)
        cls.thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.service.server_close()
        cls.thread.join()

    def request(self, path, payload=PAYLOAD, auth=True, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.service.server_port, timeout=5)
        sent_headers = {"Content-Type": "application/json"}
        if auth:
            sent_headers["Authorization"] = "Bearer " + TOKEN
        sent_headers.update(headers or {})
        connection.request("POST", path, json.dumps(payload), sent_headers)
        response = connection.getresponse()
        status, body = response.status, json.loads(response.read())
        connection.close()
        return status, body

    def test_new_routes_require_auth(self):
        for path in adapter.PATHS:
            self.assertEqual(self.request(path, auth=False)[0], 401)

    def test_unconfigured_returns_explicit_503(self):
        with patch.dict(os.environ, {}, clear=True):
            status, body = self.request("/v1/clinical/review")
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "nexo_not_configured")
        self.assertFalse(body["clinical_validated"])

    def test_oversized_payload_and_wrong_content_type(self):
        self.assertEqual(self.request("/v1/clinical/review", {"data": "x" * 65537})[0], 413)
        self.assertEqual(self.request("/v1/clinical/review", headers={"Content-Type": "text/plain"})[0], 415)

    def test_duplicate_authorization_rejected(self):
        c = http.client.HTTPConnection("127.0.0.1", self.service.server_port)
        c.putrequest("GET", "/v1/capabilities")
        c.putheader("Authorization", "Bearer " + TOKEN)
        c.putheader("Authorization", "Bearer " + TOKEN)
        c.endheaders()
        r = c.getresponse()
        self.assertEqual(r.status, 401)
        r.read()
        c.close()

    def test_forward_uses_only_fixed_origin_and_service_domain(self):
        class Opener:
            def open(inner, request, timeout):
                self.assertEqual(request.full_url, adapter.ORIGIN + "/v1/clinical/review")
                self.assertEqual(request.get_header("Authorization"), "Bearer " + UPSTREAM_TOKEN)
                self.assertEqual(json.loads(request.data)["domain"], server.DOMAIN)
                return BytesIO(json.dumps(DRAFT).encode())
        with patch.dict(os.environ, ENV), patch.object(adapter, "build_opener", return_value=Opener()):
            status, body = self.request("/v1/clinical/review", {**PAYLOAD, "domain": "other"})
        self.assertEqual(status, 200)
        self.assertFalse(body["clinical_validated"])
        self.assertNotIn(UPSTREAM_TOKEN, json.dumps(body))

    def test_identifiers_unknown_fields_and_missing_attestation_rejected(self):
        with patch.dict(os.environ, ENV):
            for payload in [{**PAYLOAD, "name": "Patient"}, {**PAYLOAD, "patient_context": {"name": "Patient"}},
                            {**PAYLOAD, "research": {"query": "pediatrics"}}, [], None]:
                self.assertEqual(self.request("/v1/clinical/review", payload)[0], 422)

    def test_provider_error_does_not_leak_upstream_body(self):
        class Opener:
            def open(inner, *args, **kwargs):
                raise HTTPError(adapter.ORIGIN, 401, "secret-body", {}, BytesIO(UPSTREAM_TOKEN.encode()))
        with patch.dict(os.environ, ENV), patch.object(adapter, "build_opener", return_value=Opener()):
            status, body = self.request("/v1/clinical/review")
        self.assertEqual(status, 503)
        self.assertNotIn(UPSTREAM_TOKEN, json.dumps(body))

    def test_invalid_success_and_approval_are_rejected(self):
        class Opener:
            def open(inner, *args, **kwargs):
                return BytesIO(json.dumps({**DRAFT, "clinical_validated": True}).encode())
        with patch.dict(os.environ, ENV), patch.object(adapter, "build_opener", return_value=Opener()):
            self.assertEqual(self.request("/v1/clinical/review")[0], 502)

    def test_arbitrary_origin_rejected(self):
        with patch.dict(os.environ, {**ENV, "NEXO_API_URL": "http://127.0.0.1/"}):
            self.assertEqual(self.request("/v1/clinical/review")[0], 503)


if __name__ == "__main__":
    unittest.main()
