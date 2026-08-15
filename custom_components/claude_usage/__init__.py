"""The Claude Usage integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ClaudeUsageClient
from .const import CONF_COOKIE, CONF_ORG_ID, DEFAULT_SCAN_INTERVAL
from .coordinator import ClaudeUsageConfigEntry, ClaudeUsageCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ClaudeUsageConfigEntry) -> bool:
    """Set up Claude Usage from a config entry."""
    session = async_get_clientsession(hass)
    client = ClaudeUsageClient(session, entry.data[CONF_COOKIE])

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = ClaudeUsageCoordinator(
        hass,
        entry,
        client,
        entry.data[CONF_ORG_ID],
        scan_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ClaudeUsageConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant, entry: ClaudeUsageConfigEntry
) -> None:
    """Reload when the polling interval changes."""
    await hass.config_entries.async_reload(entry.entry_id)
