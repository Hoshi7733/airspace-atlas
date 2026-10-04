"""Read FAA credentials only from process environment; never serialize values."""
import os
from dataclasses import dataclass, field

@dataclass(frozen=True)
class FAACredentials:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)

def load_credentials():
    client_id = os.environ.get("FAA_CLIENT_ID", "")
    client_secret = os.environ.get("FAA_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("FAA_CLIENT_ID and FAA_CLIENT_SECRET must both be configured")
    if any(c in client_id + client_secret for c in ("\r", "\n", "\x00")):
        raise ValueError("FAA credentials contain invalid control characters")
    return FAACredentials(client_id, client_secret)

if __name__ == "__main__":
    try:
        credentials = load_credentials()
    except ValueError:
        print("FAA credentials: missing or invalid. Connection remains pending.")
    else:
        print("FAA credentials: available. API specification verification still required.")
        del credentials
