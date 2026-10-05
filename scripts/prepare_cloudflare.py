"""Ensure the requested Direct Upload project exists. Never print credentials."""
import json
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def prepare():
    account=os.environ.get('CLOUDFLARE_ACCOUNT_ID','').strip()
    token=os.environ.get('CLOUDFLARE_API_TOKEN','').strip()
    project='alta-system'
    if not re.fullmatch(r'[a-fA-F0-9]{32}',account) or not token:
        raise ValueError('Cloudflare Secrets are missing or invalid')
    base='https://api.cloudflare.com/client/v4/accounts/'+account+'/pages/projects'
    client=build_opener(NoRedirect())
    def request(url,data=None):
        req=Request(url,data=json.dumps(data).encode() if data is not None else None,
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with client.open(req,timeout=30) as response:
            result=json.load(response)
        if not result.get('success'):raise ValueError('Cloudflare API reported failure')
        return result['result']
    try:
        result=request(base+'/'+project)
    except HTTPError as exc:
        if exc.code!=404:raise
        result=request(base,{'name':project,'production_branch':'main'})
    if result.get('production_branch')!='main':
        raise ValueError('Existing project production branch is not main')
    print('Cloudflare Pages project ready: '+project)

if __name__=='__main__':
    try:prepare()
    except HTTPError as exc:raise SystemExit('Cloudflare project setup failed: HTTP '+str(exc.code)) from None
    except Exception:raise SystemExit('Cloudflare project setup failed; check account, Pages Edit permission and project settings') from None
