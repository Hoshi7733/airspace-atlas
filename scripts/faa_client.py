"""Production NMS OAuth client based on supplied v1.0.18 specification.
Two requests maximum; no retries, redirects, persistent tokens or raw response logs.
"""
import base64
import json
import gzip
import io
import zipfile
import re
import sys
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from faa_credentials import load_credentials
from update_airspace import risk, polygon_geometry

HOST = 'https://api-nms.aim.faa.gov'
LIMIT = 20 * 1024 * 1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class SafeFailure(Exception):
    pass

def request_json(path, headers, data=None, limit=LIMIT):
    if not re.fullmatch(r'/[A-Za-z0-9_/?=&%.:+\-]+',path) or path.startswith('//') or '..' in path:raise SafeFailure('unsafe_path')
    request = Request(HOST + path, headers=headers, data=data)
    try:
        with build_opener(NoRedirect()).open(request, timeout=45) as response:
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise SafeFailure('response_size_limit')
            if raw[:2]==b'\x1f\x8b':
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:raw=stream.read(limit+1)
            elif raw[:2]==b'PK':
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    members=[m for m in archive.infolist() if not m.is_dir()]
                    if len(members)!=1 or members[0].file_size>limit:raise SafeFailure('archive_size_or_members')
                    with archive.open(members[0]) as stream:raw=stream.read(limit+1)
            if len(raw)>limit:raise SafeFailure('response_size_limit')
            result = json.loads(raw)
            if isinstance(result,list):result={'status':'Success','data':{'geojson':result}}
            elif isinstance(result,dict) and result.get('type')=='FeatureCollection':result={'status':'Success','data':{'geojson':result['features']}}
            if not isinstance(result, dict):
                raise SafeFailure('unexpected_json')
            return result
    except HTTPError as error:
        code = error.code
        error.close()
        raise SafeFailure('http_' + str(code)) from None
    except SafeFailure:
        raise
    except Exception:
        raise SafeFailure('network_or_json_error') from None

def authenticate():
    credentials = load_credentials()
    basic = base64.b64encode((credentials.client_id + ':' + credentials.client_secret).encode()).decode()
    data = request_json('/v1/auth/token', {'Authorization': 'Basic ' + basic,
                        'Content-Type': 'application/x-www-form-urlencoded'},
                        b'grant_type=client_credentials', limit=65536)
    token = data.get('access_token')
    if not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise SafeFailure('missing_or_invalid_access_token')
    return token

