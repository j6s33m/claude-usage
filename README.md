# Claude Usage for Home Assistant

Track your Claude Pro usage (5-hour session limit and 7-day rolling limit) as Home Assistant sensors, with reset countdowns, a high-usage alert, and a monitor that tells you when your session cookie has expired.

This reads from the same internal endpoint that the **Settings > Usage** page in claude.ai uses. It is unofficial and cookie-authenticated. See the note at the bottom before you rely on it.

---

## What you get

- **Claude Session Usage** (%) — your current 5-hour window, with `session_resets_in` countdown
- **Claude Weekly Usage** (%) — your 7-day rolling window, with `week_resets_in` countdown
- **Claude Session/Weekly Resets** — friendly local reset times
- **Claude Cookie Stale** (binary sensor) — trips after 30 minutes of no data, meaning the cookie died or Cloudflare is serving a challenge page
- Two automations: a push when weekly usage crosses 85%, and a push when the cookie goes stale
- Optional dashboard banner that only appears when the cookie is stale

---

## Home Assistant dashboard card

If you want a richer Lovelace UI for these sensors, use the companion
[Claude Usage Gauge Card](https://github.com/j6s33m/claude-usage-gauge-card).

This package provides the Home Assistant sensors:

- `sensor.claude_session_usage`
- `sensor.claude_weekly_usage`
- `sensor.claude_weekly_resets`

The gauge card visualizes those entities as a themed session gauge with a weekly
usage bar and pacing indicator.

---

## Requirements

- Home Assistant with packages enabled
- A Claude Pro (or higher) account
- A browser you can log into claude.ai with
- A mobile notify service if you want the push alerts (optional)

---

## Install

1. Enable packages in `configuration.yaml` if you have not already:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

2. Copy `claude_usage.yaml` into `/config/packages/`.

3. Fill in the two placeholders (see the next two sections):
   - `YOUR_ORG_ID` in the `resource:` URL
   - `notify.mobile_app_your_phone` in both automations (or delete the automations if you do not want alerts)

4. Add your session cookie to `secrets.yaml` (see below).

5. Restart Home Assistant, or reload the REST and Template integrations.

---

## How to get your ORG_ID

1. Log into [claude.ai](https://claude.ai) in your browser.
2. Go to **Settings > Usage**.
3. Open your browser's developer tools (F12), and click the **Network** tab.
4. Reload the page. In the request list, find the call to `.../organizations/<something>/usage`.
5. The long value between `organizations/` and `/usage` is your ORG_ID. It looks like `12478870-41cc-4707-9730-c47bcd852942`.
6. Paste it in place of `YOUR_ORG_ID` in `claude_usage.yaml`.

---

## How to get your session cookie

The cookie is what authenticates the request as you. Treat it like a password.

1. Still in developer tools on the **Settings > Usage** page, find that same `usage` request.
2. Right-click it and choose **Copy > Copy as cURL**.
3. In the copied text, find the `-H 'Cookie: ...'` (or `-b '...'`) portion. That whole string is your cookie value.
4. In `secrets.yaml`, add:

   ```yaml
   claude_session_cookie: "PASTE_THE_ENTIRE_COOKIE_STRING_HERE"
   ```

   Keep it on one line, wrapped in double quotes.

Notes:
- The cookie includes several parts (session key, `cf_clearance`, and others). Paste the whole thing, not just one piece.
- If you get a 401 or an HTML challenge page instead of JSON, the cURL copy also shows other headers (`anthropic-anonymous-id`, `anthropic-client-platform`, and similar). Add those under `headers:` in the YAML verbatim.
- The `user-agent` in the YAML should ideally match your real browser. If polling fails, replace it with the exact `user-agent` from your cURL copy.

---

## Cookie expiry

The session cookie does not last forever. When it expires, the sensors go stale and the **Claude Cookie Stale** binary sensor trips after 30 minutes, firing a push if you set one up. When that happens, repeat the cookie steps above and update `secrets.yaml`, then reload the REST integration.

---

## Optional: dashboard banner

Add this card to the top of your dashboard. It stays hidden until the cookie is stale.

```yaml
type: conditional
conditions:
  - entity: binary_sensor.claude_cookie_stale
    state: "on"
card:
  type: markdown
  content: >
    ## Claude cookie expired

    Usage data has been stale for 30+ minutes. Re-grab your session cookie
    from the browser and update secrets.yaml, then reload the REST integration.


    [Open Claude Usage page](https://claude.ai/settings/usage)
```

---

## Polling frequency

Default is 300 seconds (5 minutes). The usage counters are coarse rolling windows, so faster polling gains you little. Going much below 2 minutes only raises your odds of a Cloudflare challenge and gives no extra signal. 5 to 15 minutes is the sensible range.

---

## Disclaimer

This uses an undocumented, cookie-authenticated endpoint rather than an official API. It can break at any time if the endpoint changes, and it depends on a session cookie you must refresh periodically. Use it for your own account only. It is provided as-is with no warranty.
