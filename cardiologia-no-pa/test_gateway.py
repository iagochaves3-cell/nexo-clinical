import unittest
from gateway import validate_payload
class Contract(unittest.TestCase):
 def test_requires_explicit_deidentification(self):
  self.assertEqual(validate_payload({'query':'acute chest pain'}), 'deidentification_required')
 def test_rejects_identifiers(self):
  self.assertEqual(validate_payload({'query':'CPF: 123.456.789-00','deidentified':True}), 'possible_identifier')
 def test_accepts_bounded_generic_query(self):
  self.assertIsNone(validate_payload({'query':'acute chest pain systematic review','deidentified':True,'limit':2}))
if __name__=='__main__': unittest.main()

import http.client, json, threading
from gateway import make_server
class HTTPContract(unittest.TestCase):
 def setUp(self):
  self.calls=[]
  def upstream(path, token, payload):
   self.calls.append((path, payload))
   return 200, {'sources':[{'title':'synthetic fixture'}], 'clinical_validated':True}
  self.token='synthetic_'+('x'*40)
  self.server=make_server('127.0.0.1',0,self.token,'synthetic-upstream',upstream)
  self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.worker.join()
 def request(self,path,token=None,payload=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
  headers={} if token is None else {'Authorization':'Bearer '+token}
  c.request('GET' if payload is None else 'POST',path,body=None if payload is None else json.dumps(payload),headers=headers)
  r=c.getresponse();result=(r.status,json.loads(r.read()));c.close();return result
 def test_health_is_public(self):
  status,data=self.request('/health');self.assertEqual(status,200);self.assertFalse(data['clinical_engine'])
 def test_authentication_missing_invalid_valid(self):
  for token,expected in [(None,401),('bad',401),(self.token,200)]:
   self.assertEqual(self.request('/v1/capabilities',token)[0],expected)
 def test_valid_evidence_requests_preserve_safety(self):
  status,data=self.request('/v1/evidence/search',self.token,{'query':'chest pain evidence','deidentified':True})
  self.assertEqual(status,200);self.assertFalse(data['clinical_validated']);self.assertFalse(data['prescribing_authorization']);self.assertEqual(len(self.calls),1)
 def test_invalid_input_never_reaches_upstream(self):
  self.assertEqual(self.request('/v1/evidence/search',self.token,{'query':'nome: test','deidentified':True})[0],422);self.assertEqual(self.calls,[])
 def test_unknown_path_not_clinical_engine(self):
  self.assertEqual(self.request('/v1/prescribe',self.token,{'dose':5})[0],404)
 def test_bad_service_token_fails_closed(self):
  with self.assertRaises(ValueError):make_server('127.0.0.1',0,'short','')
