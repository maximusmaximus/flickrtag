"""Flickr OAuth authentication flow."""

from __future__ import annotations

from pathlib import Path

import flickrapi
import structlog

from flickr_autotagger.config import Settings

logger = structlog.get_logger()


def get_flickr_client(settings: Settings) -> flickrapi.FlickrAPI:
    """Create and return an authenticated Flickr API client.

    Uses OAuth for authentication. The token is cached on disk so the user
    only needs to authorize once via their browser.
    """
    token_cache = str(settings.DATA_DIR / "auth_token")

    flickr = flickrapi.FlickrAPI(
        settings.FLICKR_API_KEY,
        settings.FLICKR_API_SECRET,
        format="parsed-json",
        token_cache_location=token_cache,
    )
    return flickr


def authenticate(settings: Settings) -> flickrapi.FlickrAPI:
    """Run the full OAuth flow — opens a browser for user authorization.

    Returns an authenticated FlickrAPI client.
    """
    flickr = get_flickr_client(settings)

    if not flickr.token_valid(perms="write"):
        logger.info("oauth_starting", message="Opening browser for Flickr authorization...")
        flickr.get_request_token(oauth_callback="oob")
        authorize_url = flickr.auth_url(perms="write")

        print(f"\n🔗 Open this URL in your browser to authorize:\n\n   {authorize_url}\n")
        verifier = input("📋 Enter the verification code from Flickr: ").strip()

        flickr.get_access_token(verifier)
        logger.info("oauth_success", message="Authentication successful!")
    else:
        logger.info("oauth_cached", message="Already authenticated (token cached).")

    return flickr


def verify_auth(settings: Settings) -> bool:
    """Check if we have a valid cached OAuth token."""
    try:
        flickr = get_flickr_client(settings)
        return bool(flickr.token_valid(perms="write"))
    except Exception as exc:
        logger.warning("auth_check_failed", error=str(exc))
        return False


def get_user_id(flickr: flickrapi.FlickrAPI) -> str:
    """Get the authenticated user's NSID."""
    result = flickr.test.login()
    return str(result["user"]["id"])
