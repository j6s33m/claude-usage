"""Polling coordinator and payload normalization for Claude Usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    ClaudeUsageAuthError,
    ClaudeUsageChallengeError,
    ClaudeUsageClient,
    ClaudeUsageError,
)
from .const import DOMAIN, PAYLOAD_KEY_MAP

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LimitInfo:
    """One usage window, normalized."""

    key: str
    utilization: float | None = None
    resets_at: datetime | None = None
    severity: str | None = None

    @property
    def has_data(self) -> bool:
        """Return True when this window reported a usable percentage."""
        return self.utilization is not None


@dataclass(slots=True)
class ClaudeUsageData:
    """Everything one poll produced."""

    limits: dict[str, LimitInfo] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str) -> LimitInfo | None:
        """Return one limit by internal key."""
        return self.limits.get(key)


class ClaudeUsageCoordinator(DataUpdateCoordinator[ClaudeUsageData]):
    """Fetch usage on an interval and hand normalized data to entities."""

    config_entry: ClaudeUsageConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ClaudeUsageConfigEntry,
        client: ClaudeUsageClient,
        org_id: str,
        scan_interval: int,
    ) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.org_id = org_id
        # Tracks whether the most recent failure was an auth failure, which is
        # what the cookie stale binary sensor reports.
        self.auth_failed = False

    async def _async_update_data(self) -> ClaudeUsageData:
        """Poll once."""
        try:
            raw = await self.client.async_get_usage(self.org_id)
        except (ClaudeUsageAuthError, ClaudeUsageChallengeError) as err:
            # Both mean "a human has to go get a new cookie". Raising
            # ConfigEntryAuthFailed makes Home Assistant open a repair issue and
            # start the reauth flow, which replaces the old 30 minute stale
            # sensor plus notify automation.
            self.auth_failed = True
            raise ConfigEntryAuthFailed(str(err)) from err
        except ClaudeUsageError as err:
            raise UpdateFailed(str(err)) from err

        self.auth_failed = False
        return normalize_payload(raw)


# Declared after the class so the alias resolves at import time. Annotations are
# strings thanks to `from __future__ import annotations`, so uses above are fine.
ClaudeUsageConfigEntry = ConfigEntry[ClaudeUsageCoordinator]


def normalize_payload(raw: dict[str, Any]) -> ClaudeUsageData:
    """Turn a raw usage payload into limits we can bind entities to.

    Written defensively on purpose: the payload has already changed shape once,
    and Max and Team accounts are unverified. Anything unparseable is skipped
    rather than raised, so one new key does not take the whole integration down.
    """
    severities = _extract_severities(raw)
    limits: dict[str, LimitInfo] = {}

    for payload_key, (internal_key, severity_groups) in PAYLOAD_KEY_MAP.items():
        block = raw.get(payload_key)
        if not isinstance(block, dict):
            continue
        info = _parse_limit_block(internal_key, block)
        if info is None:
            continue
        info.severity = _first_severity(severities, severity_groups)
        # Do not let a later, emptier alias overwrite a good earlier match.
        existing = limits.get(internal_key)
        if existing is None or (info.has_data and not existing.has_data):
            limits[internal_key] = info

    return ClaudeUsageData(limits=limits, raw=raw)


def _parse_limit_block(key: str, block: dict[str, Any]) -> LimitInfo | None:
    """Parse one window block."""
    utilization = _coerce_percentage(block.get("utilization"))
    resets_at = _coerce_datetime(block.get("resets_at"))
    if utilization is None and resets_at is None:
        return None
    return LimitInfo(key=key, utilization=utilization, resets_at=resets_at)


def _extract_severities(raw: dict[str, Any]) -> dict[str, str]:
    """Build a group to severity map from the payload's `limits` array."""
    result: dict[str, str] = {}
    limits = raw.get("limits")
    if not isinstance(limits, list):
        return result
    for item in limits:
        if not isinstance(item, dict):
            continue
        group = item.get("group")
        severity = item.get("severity")
        if isinstance(group, str) and isinstance(severity, str):
            result[group.lower()] = severity
    return result


def _first_severity(
    severities: dict[str, str], candidates: tuple[str, ...]
) -> str | None:
    """Return the first severity matching any candidate group name."""
    for candidate in candidates:
        if (value := severities.get(candidate.lower())) is not None:
            return value
    return None


def _coerce_percentage(value: Any) -> float | None:
    """Return a 0-100 float, or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    # Some payload versions express utilization as a 0-1 fraction. Anything at
    # or below 1 is ambiguous, but 0-1 floats with decimals are far more likely
    # to be fractions than a genuine "0.4 percent used".
    if 0 < number <= 1 and not float(number).is_integer():
        number *= 100
    return max(0.0, min(100.0, round(number, 2)))


def _coerce_datetime(value: Any) -> datetime | None:
    """Parse a reset timestamp in whatever form it arrives."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return dt_util.utc_from_timestamp(float(value))
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in ("none", "null", "unknown"):
            return None
        if parsed := dt_util.parse_datetime(text):
            return dt_util.as_utc(parsed)
        # Numeric string epoch.
        try:
            return dt_util.utc_from_timestamp(float(text))
        except (OverflowError, OSError, ValueError):
            return None
    return None
