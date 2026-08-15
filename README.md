# Claude Usage for Home Assistant

Track your Claude usage (the 5-hour session window and the 7-day rolling window) as Home Assistant sensors, with reset countdowns and a proper reauth prompt when your session cookie expires.

Installs through HACS. Setup is one form: paste your cookie, click Submit. Your organization ID is detected for you.

Requires Home Assistant 2024.11 or newer.

[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

---

## Read this first

This integration reads the same undocumented, cookie-authenticated endpoint that the **Settings → Usage** page on claude.ai uses. There is no official API.

That means two things you should decide about before installing:

- **The cookie expires.** Every few weeks you will get a Home Assistant notification asking you to paste a fresh one. The integration makes that a two-click job instead of a YAML edit, but it does not eliminate it.
- **It can break without warning.** If Anthropic changes or closes the endpoint, the sensors go unavailable. There is no version of this that is not true.

Use it for your own account. It is provided as-is.

---

## What you get

| Entity | What it is |
|---|---|
| `sensor.claude_session_usage` | 5-hour window, percent used |
| `sensor.claude_weekly_usage` | 7-day rolling window, percent used |
| `sensor.claude_session_resets` | Friendly local reset time, e.g. `Fri 3:45 PM` |
| `sensor.claude_weekly_resets` | Friendly local reset time |
| `sensor.claude_session_reset_time` | Native timestamp, for template-free countdowns |
| `sensor.claude_weekly_reset_time` | Native timestamp |
| `sensor.claude_opus_weekly_usage` | Created only if your plan reports a separate Opus weekly limit |
| `binary_sensor.claude_cookie_stale` | On when the last poll failed |

The two percentage sensors carry `severity`, `*_resets_at`, `*_resets`, and a live `*_resets_in` countdown as attributes.

---

## Install

### 1. Add the repository to HACS

1. Home Assistant → **HACS**
2. Three-dot menu, top right → **Custom repositories**
3. URL: `https://github.com/j6s33m/claude-usage`, category: **Integration**, then **Add**
4. Find **Claude Usage** in the list and click **Download**
5. **Restart Home Assistant**

### 2. Add the integration

1. **Settings → Devices & Services → Add Integration**
2. Search for **Claude Usage**
3. Paste your cookie (next section), optionally change the polling interval, Submit

That is the whole setup. No `configuration.yaml`, no `secrets.yaml`, no packages, no org ID hunting.

---

## Getting your cookie

1. Log into [claude.ai](https://claude.ai) and go to **Settings → Usage**
2. Press **F12** to open developer tools, click the **Network** tab
3. Reload the page, filter to **Fetch/XHR**, click the request named **usage**
4. In the **Headers** tab, find the request header called **Cookie**
5. Copy the entire value and paste it into the integration form

It starts with `sessionKey=`. Copy the whole thing, not just that part: if Cloudflare is in play, the `cf_clearance` value in the same header is what keeps the request from being challenged.

Treat this string like a password. It is stored in Home Assistant's config entry storage, the same place every other integration keeps its credentials, in plaintext on disk. That is the same exposure the old `secrets.yaml` approach had.

### When it expires

Home Assistant raises a repair notification and a **Reconfigure** prompt. Click it, paste a fresh cookie, done. No restart, no reload.

---

## Dashboard card

The companion [Claude Usage Gauge Card](https://github.com/j6s33m/claude-usage-gauge-card) renders these sensors as a themed gauge with a weekly bar and pacing indicator.

Entity IDs and attribute names are unchanged from the old YAML package, so **existing card configurations work without edits**:

```yaml
type: custom:claude-usage-gauge-card
entity: sensor.claude_session_usage
label: Claude Usage
reset_attribute: session_resets_in
weekly_entity: sensor.claude_weekly_usage
weekly_reset_entity: sensor.claude_weekly_resets
weekly_period_days: 7
```

---

## Alerts

The old package hardcoded two automations you had to edit. That is now a blueprint you configure in the UI.

Import `blueprints/claude_usage_high_alert.yaml` from this repository, then create an automation from it: pick the sensor, the threshold, and your notify action.

Cookie expiry no longer needs an automation. Home Assistant's repair system handles it.

---

## Migrating from the YAML package

If you were running `claude_usage.yaml` in `/config/packages/`:

1. **Delete `/config/packages/claude_usage.yaml`.** Do this before adding the integration. If both are loaded you get duplicate entities with `_2` suffixes and neither works properly.
2. Delete the two `claude_*` automations if you copied them into your own automations file.
3. Remove `claude_session_cookie` from `secrets.yaml` (optional; it is just unused now).
4. Restart Home Assistant.
5. Install the integration as above.

Your entity IDs, dashboards, and any automations referring to them keep working. The old file is kept in [`legacy/`](legacy/) for reference.

**One behavior change worth knowing:** `binary_sensor.claude_cookie_stale` used to trip after 30 minutes of no data. It now trips on the first failed poll, and carries a `reason` attribute (`cookie_rejected`, `update_failed`, or `ok`).

---

## Polling

Default is 300 seconds. The counters are coarse rolling windows, so faster polling gains you almost nothing and increases your odds of being rate limited. 300 to 900 seconds is the sensible range. Change it under the integration's **Configure** button.

---

## Troubleshooting

**"That cookie was rejected"** — you probably copied only part of the Cookie header, or the cookie already expired. Grab it again.

**"claude.ai returned a bot challenge page"** — Cloudflare is challenging Home Assistant. Recopy the full Cookie header including `cf_clearance`. If it keeps happening, your Home Assistant's IP reputation may be the issue.

**Sensors unavailable after working fine** — check **Settings → Repairs** first, it is usually the cookie.

**No Opus sensor after upgrading your plan** — that entity is created at setup only if your account reports an Opus limit. Reload the integration (three dots → **Reload**) and it will appear.

**Anything else** — download diagnostics from the integration page (three dots → **Download diagnostics**) and attach them to an issue. They are redacted: no cookie, no org ID, and payload structure only, never your usage values.

---

## Development

```bash
ruff check . && ruff format --check .
```

CI runs `hassfest`, the HACS action, and ruff on every push.

To cut a release: bump `version` in `custom_components/claude_usage/manifest.json`, commit, then tag and publish a GitHub release with the matching tag. The release workflow fails the build if the tag and manifest disagree, because HACS reads the version from the tagged commit.

---

## License

MIT. See [LICENSE](LICENSE).
