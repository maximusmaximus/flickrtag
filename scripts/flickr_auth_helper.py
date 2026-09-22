#!/usr/bin/env python3
"""Flickr OAuth two-step authorization helper.

Step 1: Run with --get-url to generate the URL for the user.
Step 2: Run with --verifier <CODE> to complete authentication and save the token.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, "/mnt/d/flickrtag/src")

from flickr_autotagger.config import get_settings
from flickr_autotagger.auth import get_flickr_client

CACHE_FILE = Path("/root/.flickr-autotagger/oauth_request_token.json")


def step1():
    settings = get_settings()
    flickr = get_flickr_client(settings)

    if flickr.token_valid(perms="write"):
        print("ALREADY_AUTHENTICATED", flush=True)
        return

    flickr.get_request_token(oauth_callback="oob")
    auth_url = flickr.auth_url(perms="write")

    key = flickr.flickr_oauth.oauth.client.resource_owner_key
    secret = flickr.flickr_oauth.oauth.client.resource_owner_secret

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"key": key, "secret": secret}))

    print("AUTH_URL:", auth_url, flush=True)


def step2(verifier: str):
    settings = get_settings()
    flickr = get_flickr_client(settings)

    if not CACHE_FILE.exists():
        print("ERROR: No pending authorization found. Run step 1 first.", flush=True)
        sys.exit(1)

    data = json.loads(CACHE_FILE.read_text())

    clean_verifier = verifier.strip().replace(" ", "").replace("-", "")
    print(f"Exchanging verifier '{clean_verifier}' for access token...", flush=True)

    flickr.flickr_oauth.oauth.client.resource_owner_key = data["key"]
    flickr.flickr_oauth.oauth.client.resource_owner_secret = data["secret"]
    flickr.flickr_oauth.verifier = clean_verifier
    flickr.flickr_oauth.requested_permissions = "write"

    token = flickr.flickr_oauth.get_access_token()
    flickr.token_cache.token = token

    if flickr.token_valid(perms="write"):
        CACHE_FILE.unlink(missing_ok=True)
        login = flickr.test.login()
        print("SUCCESS! Authenticated as:", login["user"]["username"]["_content"], flush=True)
    else:
        print("FAILED: Token not valid after exchange.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--get-url":
        step1()
    elif len(sys.argv) > 2 and sys.argv[1] == "--verifier":
        step2(sys.argv[2])
    else:
        print("Usage: flickr_auth_helper.py --get-url | --verifier <CODE>")
