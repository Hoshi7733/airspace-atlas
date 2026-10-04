"""Bounded, staging-only NMS connection test based on supplied v1.0.18 spec.
Two requests maximum; no retries, redirects, persistent tokens or raw response logs.
"""
import base64
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from faa_credentials import load_credentials
from update_airspace import risk, polygon_geometry

HOST = 'https://api-staging.cgifederal-aim.com'
LIMIT = 20 * 1024 * 1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class SafeFailure(Exception):
    pass

def request_json(path, headers, data=None, limit=LIMIT):
    request = Request(HOST + path, headers=headers, data=data)
    try:
        with build_opener(NoRedirect()).open(request, timeout=45) as response:
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise SafeFailure('response_size_limit')
            result = json.loads(raw)
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

def summarize(payload):
    if payload.get('status', '').lower() != 'success' or payload.get('errors'):
        raise SafeFailure('notam_response_failure')
    features = payload.get('data', {}).get('geojson')
    if not isinstance(features, list):
        raise SafeFailure('unexpected_geojson_schema')
    result = dict(notams=len(features),risk_candidates=0,valid_polygon_parts=0,
                  geometry_collections=0,point_parts=0,unsupported_or_invalid_parts=0)
    for feature in features:
        if not isinstance(feature, dict):
            raise SafeFailure('invalid_feature')
        notam = feature.get('properties', {}).get('coreNOTAMData', {}).get('notam', {})
        if not isinstance(notam, dict):
            raise SafeFailure('invalid_notam')
        kind, _, _ = risk({'qcode':notam.get('selectionCode'), 'text':notam.get('text')}, ['WMR','WMW','WXX'])
        if kind:
            result['risk_candidates'] += 1
        geometry = feature.get('geometry') or {}
        if geometry.get('type') == 'GeometryCollection':
            result['geometry_collections'] += 1
            parts = geometry.get('geometries', [])
        else:
            parts = [geometry]
        for part in parts:
            if part.get('type') == 'Point':
                result['point_parts'] += 1
            else:
                try:
                    polygon_geometry(part)
                    result['valid_polygon_parts'] += 1
                except (ValueError, KeyError, TypeError):
                    result['unsupported_or_invalid_parts'] += 1
    return result

def main():
    phase = 'authentication'
    try:
        token = authenticate()
        print('FAA_STAGING_AUTH=success')
        phase = 'notams'
        payload = request_json('/nmsapi/v1/notams?feature=AIRSPACE',
            {'Authorization': 'Bearer ' + token, 'nmsResponseFormat': 'GEOJSON', 'Accept':'application/json'})
        del token
        counts = summarize(payload)
        print('FAA_STAGING_NOTAMS=success')
        print('FAA_STAGING_COUNTS=' + json.dumps(counts, sort_keys=True))
        print('TEST ENVIRONMENT ONLY; no raw data or credentials published.')
        return 0
    except SafeFailure as error:
        print('FAA_STAGING_FAILURE=' + phase + ':' + str(error))
    except Exception:
        print('FAA_STAGING_FAILURE=' + phase + ':configuration_or_schema_error')
    return 1

if __name__ == '__main__':
    sys.exit(main())
