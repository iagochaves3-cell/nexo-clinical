"""Cardiologia no PA: authenticated evidence gateway, not a clinical engine."""
import hmac
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

NEXO = 'https://nexo-clinical-api-production.up.railway.app'
MAX_BODY = 16384

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def validate_payload(payload):
    if not isinstance(payload, dict) or payload.get('deidentified') is not True:
        return 'deidentification_required'
    if set(payload) - {'query', 'deidentified', 'limit'}:
        return 'unsupported_fields'
    query = payload.get('query')
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 1000:
        return 'invalid_query'
    if re.search(r'\b(cpf|cns|prontu[aá]rio|nome|patient_name)\s*:|@|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', query, re.I):
        return 'possible_identifier'
    limit = payload.get('limit', 3)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
        return 'invalid_limit'
    return None

def remote(path, token, payload=None):
    request = Request(NEXO + path, headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'},
                      data=None if payload is None else json.dumps(payload).encode())
    try:
        with build_opener(NoRedirect()).open(request, timeout=35) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                return 502, {'error':'upstream_response_too_large'}
            return response.status, json.loads(raw)
    except HTTPError as error:
        return error.code, {'error':'upstream_request_rejected'}
    except (URLError, OSError, ValueError):
        return 503, {'error':'upstream_unavailable'}

def make_server(host, port, token, upstream_token, transport=remote):
    if not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', token):
        raise ValueError('SERVICE_API_TOKEN must be configured securely')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            for key, value in [('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]:
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(body)
        def authenticated(self):
            headers = self.headers.get_all('Authorization', [])
            value = headers[0] if len(headers)==1 else ''
            scheme, _, supplied = value.partition(' ')
            return scheme.lower()=='bearer' and hmac.compare_digest(supplied.encode(), token.encode())
        def do_GET(self):
            if self.path=='/health':
                return self.reply(200, {'status':'ok','service':'cardiologia-no-pa','clinical_engine':False})
            if not self.authenticated():
                return self.reply(401, {'error':'unauthorized'})
            if self.path=='/v1/capabilities':
                return self.reply(200, {'service':'cardiologia-no-pa','version':'0.1.0','evidence_gateway':True,'upstream_configured':bool(upstream_token),'clinical_engine':False,'clinical_validated':False,'prescribing_authorization':False})
            self.reply(404, {'error':'not_found'})
        def do_POST(self):
            self.close_connection=True
            if not self.authenticated():
                return self.reply(401, {'error':'unauthorized'})
            if self.path!='/v1/evidence/search':
                return self.reply(404, {'error':'not_found'})
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:
                return self.reply(400, {'error':'invalid_framing'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0 < size <= MAX_BODY:
                    return self.reply(413, {'error':'invalid_body_size'})
                payload=json.loads(self.rfile.read(size))
            except (ValueError, OSError):
                return self.reply(400, {'error':'invalid_json'})
            error=validate_payload(payload)
            if error:
                return self.reply(422, {'error':error})
            if not upstream_token:
                return self.reply(503, {'error':'upstream_not_configured'})
            status, data=transport('/v1/evidence/search', upstream_token, payload)
            if status!=200 or not isinstance(data, dict):
                return self.reply(503, {'error':'evidence_unavailable','upstream_status':status})
            data.update({'gateway':'cardiologia-no-pa','clinical_validated':False,'prescribing_authorization':False})
            self.reply(200,data)
    return ThreadingHTTPServer((host,port),Handler)

def startup_smoke(port, token, upstream_token):
    """Uses only environment secrets and synthetic queries; logs no bodies or credentials."""
    import http.client
    def report(name, ok, **extra):
        print(json.dumps({'event':'cardio_nexo_e2e','check':name,'passed':bool(ok),**extra}), flush=True)
    try:
        for supplied, expected in [(None,401),('synthetic-invalid',401),(token,200)]:
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
            conn.request('GET','/v1/capabilities',headers={} if supplied is None else {'Authorization':'Bearer '+supplied})
            res=conn.getresponse(); status=res.status; res.read(); conn.close()
            report('gateway_auth_'+('valid' if supplied==token else 'invalid' if supplied else 'missing'),status==expected,status=status)
        report('upstream_token_configured',bool(upstream_token))
        if not upstream_token:
            return
        status,data=remote('/v1/capabilities',upstream_token)
        report('nexo_scoped_capabilities',status==200 and isinstance(data,dict) and data.get('live_evidence_search') is True,status=status)
        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=45)
        payload={'query':'acute chest pain emergency systematic review','deidentified':True,'limit':2}
        conn.request('POST','/v1/evidence/search',body=json.dumps(payload),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        res=conn.getresponse(); status=res.status; data=json.loads(res.read());conn.close()
        sources=data.get('sources',[]) if isinstance(data,dict) else []
        report('gateway_nexo_live_evidence',status==200 and bool(sources) and data.get('clinical_validated') is False,status=status,source_count=len(sources))
        status,_=remote('/openapi.json',upstream_token)
        report('scoped_admin_denied',status==401,status=status)
    except Exception:
        report('smoke_execution',False,error='sanitized_execution_failure')

if __name__=='__main__':
    port=int(os.environ.get('PORT','8080'))
    token=os.environ.get('SERVICE_API_TOKEN','')
    upstream=os.environ.get('NEXO_INTEGRATION_TOKEN','')
    server=make_server('0.0.0.0',port,token,upstream)
    threading.Thread(target=startup_smoke,args=(port,token,upstream),daemon=True).start()
    server.serve_forever()
