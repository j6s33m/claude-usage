"""Thin async client for the claude.ai usage endpoint.

This talks to an undocumented, cookie authenticated endpoint. Everything here
assumes the response can change shape or be replaced by a Cloudflare challenge
page at any time, so the client validates aggressively and raises typed errors
the rest of the integration can act on.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    DEFAULT_HEADERS,
    ORGANIZATIONS_PATH,
    REQUEST_TIMEOUT,
    USAGE_PATH,
)

_LOGGER = logging.getLogger(__name__)


class ClaudeUsageError(Exception):
    """Base error for this integration."""


class ClaudeUsageAuthError(ClaudeUsageError):
    """The cookie was rejected. The user must supply a fresh one."""


class ClaudeUsageChallengeError(ClaudeUsageError):
    """A bot challenge (usually Cloudflare) was served instead of JSON."""


class ClaudeUsageConnectionError(ClaudeUsageError):
    """The endpoint could not be reached."""


class ClaudeUsageResponseError(ClaudeUsageError):
    """The endpoint answered, but not with anything we recognise."""


class ClaudeUsageClient:
    """Minimal client for the two endpoints this integration needs."""

    def __init__(self, session: aiohttp.ClientSession, cookie: str) -> None:
        """Store the shared HA session and the user's cookie string."""
        self._session = session
        self._cookie = cookie.strip()

    @property
    def cookie(self) -> str:
        """Return the cookie currently in use."""
        return self._cookie

    def update_cookie(self, cookie: str) -> None:
        """Swap in a new cookie after a reauth."""
        self._cookie = cookie.strip()

    async def async_get_organizations(self) -> list[dict[str, Any]]:
        """Return the organizations this cookie can see.

        The usage endpoint needs an organization UUID. Fetching it here is what
        removes the manual DevTools step from setup. If this endpoint ever stops
        answering, the config flow falls back to asking for the ID directly.
        """
        data = await self._request(ORGANIZATIONS_PATH)
        if not isinstance(data, list):
            raise ClaudeUsageResponseError(
                f"Expected a list of organizations, got {type(data).__name__}"
            )
        orgs = [item for item in data if isinstance(item, dict) and item.get("uuid")]
        if not orgs:
            raise ClaudeUsageResponseError("No organizations returned for this cookie")
        return orgs

    async def async_get_usage(self, org_id: str) -> dict[str, Any]:
        """Return the raw usage payload for one organization."""
        data = await self._request(USAGE_PATH.format(org_id=org_id))
        if not isinstance(data, dict):
            raise ClaudeUsageResponseError(
                f"Expected a usage object, got {type(data).__name__}"
            )
        return data

    async def async_validate(self, org_id: str) -> dict[str, Any]:
        """Confirm the cookie and org together return a usable payload."""
        data = await self.async_get_usage(org_id)
        # `limits` is the one key that has survived every shape change so far,
        # so it is what we treat as proof the payload is real.
        if "limits" not in data and not any(
            isinstance(value, dict) and "utilization" in value
            for value in data.values()
        ):
            raise ClaudeUsageResponseError(
                "Usage payload contained no limits or utilization data"
            )
        return data

    async def _request(self, path: str) -> Any:
        """Perform one GET and return decoded JSON, or raise a typed error."""
        url = f"{BASE_URL}{path}"
        headers = {**DEFAULT_HEADERS, "Cookie": self._cookie}

        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as response:
                status = response.status
                content_type = (response.content_type or "").lower()
                body = await response.text()
        except TimeoutError as err:
            raise ClaudeUsageConnectionError(f"Timeout contacting {url}") from err
        except aiohttp.ClientError as err:
            raise ClaudeUsageConnectionError(f"Error contacting {url}: {err}") from err

        if status in (401, 403):
            # 403 is ambiguous: it is what both an expired cookie and a
            # Cloudflare block look like. The body tells them apart.
            if _looks_like_challenge(content_type, body):
                raise ClaudeUsageChallengeError(
                    "Received a bot challenge page instead of JSON. A cf_clearance "
                    "cookie may be required alongside sessionKey."
                )
            raise ClaudeUsageAuthError(
                f"Cookie rejected with HTTP {status}. It has most likely expired."
            )

        if status in (301, 302, 303, 307, 308):
            # A redirect to the login page is an expired cookie by another name.
            raise ClaudeUsageAuthError(
                f"Request was redirected (HTTP {status}), which usually means the "
                "cookie is no longer valid."
            )

        if status == 429:
            raise ClaudeUsageConnectionError(
                "Rate limited by claude.ai. Increase the polling interval."
            )

        if status >= 400:
            raise ClaudeUsageResponseError(f"HTTP {status} from {url}")

        if _looks_like_challenge(content_type, body):
            raise ClaudeUsageChallengeError(
                "Received an HTML page instead of JSON, which usually means a "
                "Cloudflare challenge."
            )

        try:
            return await _decode_json(body)
        except ValueError as err:
            _LOGGER.debug("Undecodable response body (first 200 chars): %s", body[:200])
            raise ClaudeUsageResponseError(
                "Response was not valid JSON. The endpoint may have changed."
            ) from err


def _looks_like_challenge(content_type: str, body: str) -> bool:
    """Return True when the response is a web page rather than JSON."""
    if "json" in content_type:
        return False
    stripped = body.lstrip()[:200].lower()
    return stripped.startswith("<") or "cf-browser-verification" in stripped


async def _decode_json(body: str) -> Any:
    """Decode JSON off the event loop-friendly path."""
    import json

    return json.loads(body)
