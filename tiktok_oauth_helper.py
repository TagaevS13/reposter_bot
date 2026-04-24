from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from config import load_settings


VERIFIER_FILE = Path(".tiktok_pkce_verifier")


def _base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate_pkce_pair() -> tuple[str, str]:
    verifier = _base64url(secrets.token_bytes(64))
    challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorize_url(client_key: str, redirect_uri: str, scope: str, state: str, challenge: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "scope": scope,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"https://www.tiktok.com/v2/auth/authorize/?{query}"


def exchange_code_for_token(
    client_key: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> dict:
    form_data = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url="https://open.tiktokapis.com/v2/oauth/token/",
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
        return eval_json(payload)
    except urllib.error.HTTPError as err:
        payload = err.read().decode("utf-8", errors="ignore")
        try:
            data = eval_json(payload)
            data["_http_status"] = err.code
            return data
        except Exception:
            raise RuntimeError(f"TikTok token HTTP error {err.code}: {payload}") from err


def eval_json(raw_json: str) -> dict:
    import json

    return json.loads(raw_json)


def update_env_file(access_token: str, open_id: str, redirect_uri: str) -> None:
    env_path = Path(".env")
    if not env_path.exists():
        raise FileNotFoundError(".env file not found. Create it first from .env.example.")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updates = {
        "TIKTOK_ACCESS_TOKEN": access_token,
        "TIKTOK_OPEN_ID": open_id,
        "TIKTOK_REDIRECT_URI": redirect_uri,
    }

    existing_keys = set()
    new_lines: list[str] = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key, _ = line.split("=", 1)
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                existing_keys.add(key)
                continue
        new_lines.append(line)

    for key, value in updates.items():
        if key not in existing_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def parse_code_from_url(url_or_code: str) -> str:
    if url_or_code.startswith("http://") or url_or_code.startswith("https://"):
        parsed = urllib.parse.urlparse(url_or_code)
        query = urllib.parse.parse_qs(parsed.query)
        code_values = query.get("code")
        if not code_values:
            raise ValueError("No 'code' parameter found in the callback URL.")
        return code_values[0]
    return url_or_code.strip()


def main() -> None:
    load_dotenv()
    settings = load_settings()
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise RuntimeError("Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env first.")

    redirect_uri = settings.tiktok_redirect_uri or "http://localhost:3000/callback"
    scope = settings.tiktok_oauth_scope

    verifier, challenge = generate_pkce_pair()
    VERIFIER_FILE.write_text(verifier, encoding="utf-8")

    auth_url = build_authorize_url(
        client_key=settings.tiktok_client_key,
        redirect_uri=redirect_uri,
        scope=scope,
        state="tg_media_repost",
        challenge=challenge,
    )
    print("Open this URL and approve access:\n")
    print(auth_url)
    print("\nAfter redirect, paste full callback URL (or just code) and press Enter.")
    callback = input("> ").strip()
    if not callback:
        raise RuntimeError("Empty input. Paste full callback URL (or just code) from the browser.")
    code = parse_code_from_url(callback)
    if not code:
        raise RuntimeError("Authorization code is empty. Try login again and copy callback URL.")

    token_response = exchange_code_for_token(
        client_key=settings.tiktok_client_key,
        client_secret=settings.tiktok_client_secret,
        redirect_uri=redirect_uri,
        code=code,
        code_verifier=verifier,
    )

    if token_response.get("error"):
        raise RuntimeError(
            "TikTok token exchange failed: "
            f"{token_response}. "
            "Check that redirect URI in TikTok app exactly matches .env, "
            "the code was copied from the latest login, and code was not reused."
        )

    data = token_response.get("data")
    if isinstance(data, dict):
        access_token = data.get("access_token", "")
        open_id = data.get("open_id", "")
    else:
        # Some TikTok environments return token fields at top level.
        access_token = token_response.get("access_token", "")
        open_id = token_response.get("open_id", "")
    if not access_token or not open_id:
        raise RuntimeError(f"Unexpected token response: {token_response}")

    update_env_file(access_token=access_token, open_id=open_id, redirect_uri=redirect_uri)
    print("\nSuccess. Updated .env with TIKTOK_ACCESS_TOKEN, TIKTOK_OPEN_ID, TIKTOK_REDIRECT_URI.")


if __name__ == "__main__":
    main()
