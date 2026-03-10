"""
EVE Rock – multi-character OAuth2 PKCE authentication.

Each character gets its own token stored keyed by character_id in a single
JSON file on disk.  Characters can be added, refreshed, or removed at runtime.
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# EVE SSO constants
# ---------------------------------------------------------------------------
ESI_BASE       = "https://esi.evetech.net/latest"
SSO_AUTH_URL   = "https://login.eveonline.com/v2/oauth/authorize"
SSO_TOKEN_URL  = "https://login.eveonline.com/v2/oauth/token"
SSO_VERIFY_URL = "https://login.eveonline.com/oauth/verify"

CALLBACK_PORT = 45679                          # different from eve-gas-man (45678)
REDIRECT_URI  = f"http://localhost:{CALLBACK_PORT}/callback"

# Scopes requested at login.
SCOPES = (
    "esi-industry.read_character_mining.v1 "
    "esi-industry.read_corporation_mining.v1 "
    "esi-universe.read_structures.v1"
)

TOKEN_FILE = Path.home() / ".eve_rock_tokens.json"


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _pkce_pair() -> tuple[str, str]:
    verifier  = secrets.token_urlsafe(64)
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# Local callback server
# ---------------------------------------------------------------------------

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        code   = params.get("code",  [None])[0]
        state  = params.get("state", [None])[0]

        if code and state == self.server.expected_state:
            self.server.auth_code = code
            body = (
                b"<html><body><h2>Authentication successful!</h2>"
                b"<p>You may close this tab and return to EVE Rock.</p>"
                b"</body></html>"
            )
            self.send_response(200)
        else:
            self.server.auth_code = None
            body = b"<html><body><h2>Authentication failed.</h2></body></html>"
            self.send_response(400)

        self.send_header("Content-Type",   "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):          # silence access log
        pass


def _wait_for_code(state: str, timeout: int = 120) -> str | None:
    server = http.server.HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
    server.expected_state = state
    server.auth_code      = None
    server.timeout        = 1                  # poll every second

    deadline = time.time() + timeout
    while time.time() < deadline:
        server.handle_request()
        if server.auth_code is not None:
            server.server_close()
            return server.auth_code

    server.server_close()
    return None


# ---------------------------------------------------------------------------
# Token exchange / refresh
# ---------------------------------------------------------------------------

def _exchange_code(client_id: str, code: str, verifier: str) -> dict | None:
    resp = requests.post(
        SSO_TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "client_id":     client_id,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if not resp.ok:
        return None
    data = resp.json()
    data["expires_at"] = time.time() + data.get("expires_in", 1200) - 30
    return data


def _refresh_access_token(client_id: str, refresh_tok: str) -> dict | None:
    resp = requests.post(
        SSO_TOKEN_URL,
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_tok,
            "client_id":     client_id,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if not resp.ok:
        return None
    data = resp.json()
    data["expires_at"] = time.time() + data.get("expires_in", 1200) - 30
    return data


def _fetch_char_identity(access_token: str) -> dict | None:
    """Return character_id, character_name, corporation_id from the token."""
    resp = requests.get(
        SSO_VERIFY_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not resp.ok:
        return None
    v       = resp.json()
    char_id = v.get("CharacterID")
    if not char_id:
        return None

    cr = requests.get(
        f"{ESI_BASE}/characters/{char_id}/",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    corp_id = cr.json().get("corporation_id") if cr.ok else None
    return {
        "character_id":   char_id,
        "character_name": v.get("CharacterName", ""),
        "corporation_id": corp_id,
    }


# ---------------------------------------------------------------------------
# Persistent token store
# ---------------------------------------------------------------------------

def load_all_tokens() -> dict:
    """Return {str(char_id): token_dict} from disk."""
    if not TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_all_tokens(tokens: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)    # restrict permissions on posix systems
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_add_character(client_id: str) -> tuple[int, dict] | None:
    """
    Run PKCE flow for a new (or existing) character.
    Returns (character_id, enriched_token) or None on failure / timeout.
    The returned token dict includes character_id, character_name, corporation_id.
    """
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)

    params = {
        "response_type":         "code",
        "redirect_uri":          REDIRECT_URI,
        "client_id":             client_id,
        "scope":                 SCOPES,
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
    }
    webbrowser.open(SSO_AUTH_URL + "?" + urllib.parse.urlencode(params))

    code = _wait_for_code(state, timeout=120)
    if not code:
        return None

    token = _exchange_code(client_id, code, verifier)
    if not token:
        return None

    info = _fetch_char_identity(token["access_token"])
    if not info:
        return None

    char_id = info["character_id"]
    token["character_id"]   = char_id
    token["character_name"] = info["character_name"]
    token["corporation_id"] = info.get("corporation_id")

    tokens = load_all_tokens()
    tokens[str(char_id)] = token
    _save_all_tokens(tokens)
    return char_id, token


def get_valid_token(client_id: str, char_id: int, token: dict) -> dict | None:
    """
    Return a valid (possibly refreshed) token for the given character.
    Updates the token file on disk if a refresh was needed.
    Returns None if the refresh token is expired or invalid.
    """
    if time.time() < token.get("expires_at", 0):
        return token                               # still valid

    new_token = _refresh_access_token(client_id, token.get("refresh_token", ""))
    if not new_token:
        return None

    # Preserve character identity fields
    for key in ("character_id", "character_name", "corporation_id"):
        new_token[key] = token.get(key)
    new_token["character_id"] = new_token.get("character_id") or char_id

    tokens = load_all_tokens()
    tokens[str(char_id)] = new_token
    _save_all_tokens(tokens)
    return new_token


def remove_character(char_id: int) -> None:
    """Remove a character's token from disk."""
    tokens = load_all_tokens()
    tokens.pop(str(char_id), None)
    _save_all_tokens(tokens)
