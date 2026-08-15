"""Constants for the Claude Usage integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "claude_usage"

# Config entry keys
CONF_COOKIE: Final = "cookie"
CONF_ORG_ID: Final = "org_id"
CONF_ORG_NAME: Final = "org_name"

# Polling
DEFAULT_SCAN_INTERVAL: Final = 300
MIN_SCAN_INTERVAL: Final = 60
MAX_SCAN_INTERVAL: Final = 3600

# Endpoint. Undocumented and cookie authenticated; see README.
BASE_URL: Final = "https://claude.ai"
ORGANIZATIONS_PATH: Final = "/api/organizations"
USAGE_PATH: Final = "/api/organizations/{org_id}/usage"
REQUEST_TIMEOUT: Final = 20

# Sent so the request looks like the browser call it is imitating. Without a
# plausible user agent and referer the endpoint is more likely to be
# challenged by Cloudflare.
DEFAULT_HEADERS: Final[dict[str, str]] = {
    "accept": "application/json",
    "referer": "https://claude.ai/settings/usage",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}

# Internal limit keys used throughout the integration.
LIMIT_SESSION: Final = "session"
LIMIT_WEEKLY: Final = "weekly"
LIMIT_OPUS_WEEKLY: Final = "opus_weekly"

# Maps a top level key in the usage payload to our internal limit key, and to
# the candidate `group` values used in the payload's `limits` array to look up
# a severity. The payload has changed shape before, so several spellings are
# accepted for each.
PAYLOAD_KEY_MAP: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "five_hour": (LIMIT_SESSION, ("session", "five_hour", "5h")),
    "seven_day": (LIMIT_WEEKLY, ("weekly", "seven_day", "7d")),
    "seven_day_opus": (
        LIMIT_OPUS_WEEKLY,
        ("weekly_opus", "opus_weekly", "seven_day_opus", "opus"),
    ),
    "seven_day_oauth_apps": (LIMIT_WEEKLY, ("weekly", "seven_day")),
}

# Attributes that carry a live countdown. They are refreshed once a minute so
# the value stays honest, and excluded from the recorder so that refresh does
# not write a database row every minute for the life of the install.
COUNTDOWN_ATTRIBUTES: Final = frozenset(
    {"session_resets_in", "week_resets_in", "opus_week_resets_in"}
)

# How often countdown attributes are recomputed.
COUNTDOWN_REFRESH_SECONDS: Final = 60
