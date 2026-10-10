"""Build a UI-only gate from GitHub Secret. Does not secure public data URLs."""
import hashlib,json,os,secrets
from pathlib import Path
from update_airspace import ROOT
p=os.environ.get('ALTA_VIEW_PASSWORD','')
salt='60bc3a9a3c7048d99afd8df6de9c4977';iterations=210000 # Stable per-site salt: refresh does not invalidate this tab's login.
config={'enabled':bool(p),'iterations':iterations,'salt':salt,'hash':hashlib.pbkdf2_hmac('sha256',p.encode(),salt.encode(),iterations).hex() if p else ''}
(ROOT/'web/access-config.json').write_text(json.dumps(config))
print('UI gate enabled' if p else 'UI gate pending: set ALTA_VIEW_PASSWORD repository Secret')
