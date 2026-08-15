"""Config flow for Claude Usage.

The whole point of this file is to delete the DevTools org ID step from setup.
The user pastes one cookie; we find the organization ourselves. If the
organizations endpoint ever stops answering, we ask for the ID rather than
failing, so a change upstream degrades to the old experience instead of a dead
integration.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import (
    ClaudeUsageAuthError,
    ClaudeUsageChallengeError,
    ClaudeUsageClient,
    ClaudeUsageConnectionError,
    ClaudeUsageError,
)
from .const import (
    CONF_COOKIE,
    CONF_ORG_ID,
    CONF_ORG_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import ClaudeUsageConfigEntry

_LOGGER = logging.getLogger(__name__)

COOKIE_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, multiline=True)
)

INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL,
        max=MAX_SCAN_INTERVAL,
        step=30,
        unit_of_measurement="seconds",
        mode=NumberSelectorMode.BOX,
    )
)


class ClaudeUsageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup, organization choice, and reauth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._cookie: str = ""
        self._scan_interval: int = DEFAULT_SCAN_INTERVAL
        self._organizations: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the cookie, then try to find the organization."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._cookie = str(user_input[CONF_COOKIE]).strip()
            self._scan_interval = int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )

            client = self._client(self._cookie)
            try:
                self._organizations = await client.async_get_organizations()
            except ClaudeUsageAuthError:
                errors["base"] = "invalid_auth"
            except ClaudeUsageChallengeError:
                errors["base"] = "challenge"
            except ClaudeUsageConnectionError:
                errors["base"] = "cannot_connect"
            except ClaudeUsageError:
                # The organizations endpoint did not behave. Fall back to
                # asking for the ID by hand rather than blocking setup.
                _LOGGER.debug(
                    "Organization discovery failed, falling back", exc_info=True
                )
                return await self.async_step_manual_org()
            else:
                if len(self._organizations) == 1:
                    org = self._organizations[0]
                    return await self._async_finish(str(org["uuid"]), _org_label(org))
                return await self.async_step_pick_org()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COOKIE): COOKIE_SELECTOR,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): INTERVAL_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_org(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose when the cookie can see several organizations."""
        errors: dict[str, str] = {}

        if user_input is not None:
            org_id = str(user_input[CONF_ORG_ID])
            label = next(
                (
                    _org_label(org)
                    for org in self._organizations
                    if str(org.get("uuid")) == org_id
                ),
                org_id,
            )
            return await self._async_finish(org_id, label)

        options = [
            {"value": str(org["uuid"]), "label": _org_label(org)}
            for org in self._organizations
        ]
        return self.async_show_form(
            step_id="pick_org",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORG_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_manual_org(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fallback when automatic organization discovery is unavailable."""
        errors: dict[str, str] = {}

        if user_input is not None:
            org_id = str(user_input[CONF_ORG_ID]).strip()
            return await self._async_finish(org_id, org_id, errors=errors)

        return self.async_show_form(
            step_id="manual_org",
            data_schema=vol.Schema({vol.Required(CONF_ORG_ID): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the cookie expires."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Take a fresh cookie for an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            cookie = str(user_input[CONF_COOKIE]).strip()
            client = self._client(cookie)
            try:
                await client.async_validate(entry.data[CONF_ORG_ID])
            except ClaudeUsageAuthError:
                errors["base"] = "invalid_auth"
            except ClaudeUsageChallengeError:
                errors["base"] = "challenge"
            except ClaudeUsageConnectionError:
                errors["base"] = "cannot_connect"
            except ClaudeUsageError:
                errors["base"] = "unknown_response"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_COOKIE: cookie}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_COOKIE): COOKIE_SELECTOR}),
            errors=errors,
            description_placeholders={
                "org": entry.data.get(CONF_ORG_NAME, entry.title)
            },
        )

    async def _async_finish(
        self,
        org_id: str,
        label: str,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Validate the cookie plus org pair, then create the entry."""
        errors = errors if errors is not None else {}

        await self.async_set_unique_id(org_id)
        self._abort_if_unique_id_configured()

        client = self._client(self._cookie)
        try:
            await client.async_validate(org_id)
        except ClaudeUsageAuthError:
            errors["base"] = "invalid_auth"
        except ClaudeUsageChallengeError:
            errors["base"] = "challenge"
        except ClaudeUsageConnectionError:
            errors["base"] = "cannot_connect"
        except ClaudeUsageError:
            errors["base"] = "unknown_response"

        if errors:
            # Send them back to the cookie step; that is what they can fix.
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_COOKIE): COOKIE_SELECTOR,
                        vol.Optional(
                            CONF_SCAN_INTERVAL, default=self._scan_interval
                        ): INTERVAL_SELECTOR,
                    }
                ),
                errors=errors,
            )

        return self.async_create_entry(
            title=label or "Claude Usage",
            data={
                CONF_COOKIE: self._cookie,
                CONF_ORG_ID: org_id,
                CONF_ORG_NAME: label,
            },
            options={CONF_SCAN_INTERVAL: self._scan_interval},
        )

    def _client(self, cookie: str) -> ClaudeUsageClient:
        """Build a client against Home Assistant's shared session."""
        return ClaudeUsageClient(async_get_clientsession(self.hass), cookie)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ClaudeUsageConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ClaudeUsageOptionsFlow()


class ClaudeUsageOptionsFlow(OptionsFlow):
    """Adjust the polling interval after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the interval."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_SCAN_INTERVAL, default=current): INTERVAL_SELECTOR}
            ),
        )


def _org_label(org: dict[str, Any]) -> str:
    """Return a human label for an organization."""
    name = org.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return str(org.get("uuid", "Claude"))
