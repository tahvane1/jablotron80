# Account-scoped Jablotron codes

Integration options select `common` (default, preserving the original behavior)
or `personal`. In common mode **Require code to disarm** controls whether to prompt
for a PIN or use the configured master PIN. In personal mode the authenticated API
uses only the logged-in HA account's saved code; accounts without a code get a manual
prompt. The standard alarm entity requires a supplied PIN in personal mode and never
falls back to the master code for disarming. Switching modes retains personal codes without using
them in common mode. Saved account codes are used only for disarming. Arming keeps the panel's existing code requirements: if a PIN is required and **Require code to arm** is disabled, the original master-PIN behavior remains. This feature does not remove the stored master PIN.

Saving a PIN does not program the panel and does not verify its validity. Supply an
existing four-digit panel user code. Each person needs a separate HA account: anyone
logged in to an account can use its saved code. The card does not manage HA permissions.

## Relationship to upstream issues

This section explains how the integration addresses related upstream issues and
which limitations remain. Partial coverage does not mean that an issue is fully
resolved.

| Upstream issue | Supported behavior | Remaining scope |
| --- | --- | --- |
| [#43: use a normal user code and never store the master code](https://github.com/tahvane1/jablotron80/issues/43) | **Partial.** Personal mode disarms with the signed-in account's existing panel user PIN, without falling back to the master PIN. Optional encryption protects stored master, imported and personal codes. | The master PIN is still retained and used by existing configuration/arming paths. Encryption does not implement the request to never store it. Personal codes are currently for disarming, not account-specific arming. See [ENCRYPTION.md](ENCRYPTION.md). |
| [#170: options and disarming without typing the PIN](https://github.com/tahvane1/jablotron80/issues/170) | **The saved-PIN workflow is provided; the overall issue is only partially covered.** The optional disarm card uses the current account's saved PIN, and this guide explains common/personal modes and the existing master-code option. | In common mode, disarming without a PIN prompt is available when **Require code to disarm** is disabled. Labels and available modes in the native alarm dialog are controlled by Home Assistant. Dashboard layout remains the user's choice. |
| [#201: installing the control panel in HA](https://github.com/tahvane1/jablotron80/issues/201) | **Partial documentation coverage.** The installation section below gives the exact bundled resource URL and card YAML, and explains the difference between PIN management, saved-code disarming and native alarm controls. | The disarm card provides disarming only; it is not a complete arm/disarm panel. The integration does not create a dashboard automatically. |
| [#181: alarm starts arming again after disarming](https://github.com/tahvane1/jablotron80/issues/181) | **A mitigation limited to the saved-code API.** It disables automatic PIN retries, serializes requests per panel, applies attempt limits and blocks sending a PIN when HA or the panel already reports disarmed. Tests cover those guards. | Native manual service calls retain their existing retry behavior. A sent command is not confirmation of panel acceptance; stale state, communication faults and the original reporter's conditions still require hardware reproduction. This is not a general fix for #181. |

## Defaults and storage

| Code mode | Encryption | Disarming through the optional disarm card |
| --- | --- | --- |
| `common` (default) | Disabled (default) | Manual PIN by default; configured master PIN if **Require code to disarm** is disabled. |
| `common` | Enabled | Same behavior; stored master/imported codes and retained personal codes are encrypted. |
| `personal` | Disabled | Current HA account's saved PIN; native manual dialog if none is saved. Stored PINs are plaintext. |
| `personal` | Enabled | Same behavior; stored master/imported codes and personal codes are encrypted. |

The original credentials are in HA's `.storage/core.config_entries`. Personal
codes are in `.storage/jablotron80.user_codes`. With encryption enabled, the
plaintext `password` and imported `codes` fields are replaced by an encrypted
bundle; personal PIN records are encrypted too. Encryption and code mode are
independent settings and can be changed in either order or together. Enabling
personal mode does not automatically enable encryption. The configured master PIN
is retained in both code modes and is encrypted when encryption is enabled.

## Optional frontend, separate from your dashboard

The integration provides alarm entities, panel communication, credential storage
and authenticated APIs. It does not create or edit dashboards, add cards, or
register dashboard resources automatically. Each dashboard owner chooses the
layout and controls.

Two independent, optional cards are bundled in the integration:

* **My Jablotron code** (`jablotron-user-code-manager`) only saves, replaces or forgets
  the signed-in account's existing panel PIN. It cannot arm or disarm the alarm.
* **Disarm Jablotron** (`jablotron-disarm-card`) requests disarming using the saved
  code without a PIN in the request. It opens the native manual-code dialog if no
  personal code is saved. In common mode it follows the existing manual/common-code
  setting. It has no PIN-management form and no arming or zone controls.

Native HA alarm controls remain usable with manual PIN entry. They do not
implicitly resolve an account's saved PIN; use the optional disarm card or the
authenticated saved-code API for that feature. Personal PINs are not panel-programming
commands, and saving one does not check it against the panel.

### Why a small bundled JavaScript form?

Ordinary users need to manage their own PIN without administrative access to
integration settings. Standard configuration/options flows are administrative UI;
an `input_text` helper would put the PIN into entity state, while a PIN-bearing
service action would send it through HA's normal service-event path. The dedicated
HTTP write endpoint avoids those paths and never reads a saved PIN back. Authorization
is enforced on the server for every operation, independently of card visibility.

The optional form uses custom JavaScript served by your own HA instance, with no
CDN, remote imports, external libraries, analytics, or browser credential storage.
Like any custom HA frontend code, it runs in a signed-in environment and requires
trust in the integration's code. Bundling is a compatibility and maintenance choice,
not a security guarantee. Other scripts running in the same frontend can still pose
a risk. Encryption at rest does not protect a PIN while it is being entered.

The module is installed inside `custom_components/jablotron80/frontend`, so HACS
updates the Python backend and frontend file together. Only the JavaScript file is
served publicly; it contains no user configuration, PINs or encryption keys. The
APIs require authentication and alarm-control permission. This design does not
expose the integration's directory or private credential files.

### Install and choose cards

Home Assistant already runs JavaScript in its browser/app frontend. There is no
separate JavaScript switch to enable and no Node.js, add-on or frontend library to
install, even if these are your first custom cards. The integration installs and
serves the module, but does not register it as a dashboard resource or add cards
for you. A Home Assistant administrator performs the following setup once.

The recommended setup uses the Home Assistant UI:

1. Install/update the integration and restart HA. No file needs to be copied to `www`.
2. Go to **Settings > Dashboards**, open the top-right menu and select **Resources**.
3. Select **Add resource**, enter
   `/jablotron80/frontend/jablotron-user-code-card.js` and choose
   **JavaScript module**. Register this URL only once; the resource is shared by
   all dashboards.
4. Reload the page in each browser/app frontend that will use the cards.
5. Select `personal` in integration options if you want account codes. Encryption
   is an independent setting and can be enabled before, after or together with
   personal mode.
6. Open your chosen editable dashboard, select **Edit dashboard > Add card > Manual**,
   and paste one of the card examples below. Replace
   `alarm_control_panel.your_jablotron_panel` with your actual Jablotron alarm entity.
   These cards currently use manual YAML configuration; they do not appear as named
   entries in the community-card picker and have no visual configuration editor.
   PIN management can be placed on a separate view from the disarm control.

For the standard resource-registration procedure, see the
[Home Assistant resource documentation](https://contributors.home-assistant.io/frontend/custom-ui/resources/).

#### Alternative: resources managed in YAML

Use this alternative if you manage dashboard resources in YAML instead of through
the UI. In `configuration.yaml`, merge the following into the existing `lovelace`
section, retaining any other resource entries. This is not dashboard/card YAML:

```yaml
lovelace:
  resource_mode: yaml
  resources:
    - url: /jablotron80/frontend/jablotron-user-code-card.js
      type: module
```

With `resource_mode: yaml`, resources are managed by this configuration rather
than the UI Resources page. Do not switch an existing UI-managed resource list
without also preserving its other resources in YAML. Reload resources with the
`lovelace.reload_resources` action (or restart HA), then reload the browser/app.
Continue with the integration options and manual card examples described above.
Switching the dashboard itself to YAML mode is not required.

Management only:

```yaml
type: custom:jablotron-user-code-manager
entity: alarm_control_panel.your_jablotron_panel
```

Optional saved-code disarming, independently of the management card:

```yaml
type: custom:jablotron-disarm-card
entity: alarm_control_panel.your_jablotron_panel
```

Card labels follow HA's language (Czech, English or French; English fallback).
French translations are provided for the integration options and bundled cards,
but have not been manually verified in the Home Assistant UI or reviewed by a
native French speaker.

Backend errors and technical logs use fixed English messages, matching upstream.
Expected HTTP failures include a stable `code` and an English `message`; WebSocket
failures use the same identifier in `error.code`. Cards translate known codes
locally (Czech, English or French, with English fallback) and show a generic
translated message for unknown codes, network failures or older API responses.
They never display arbitrary exception text. Configuration/options-flow errors
continue to use HA translation keys in `strings.json` and `translations/*.json`.
Clients should branch on error codes, not message text.

The form clears the PIN immediately
on submission, after invalid input, account/entity changes, and when removed from
the page. It never pre-fills a saved PIN. Saving confirms storage only. A disarm API
success confirms submission, not panel acceptance; check the alarm's actual state.

The cards load account settings automatically. There is no permanent Refresh
button. If loading fails, **Try again** repeats only the status read; it never
resubmits a PIN or a disarm command. Changes made by the management card update
other bundled cards on the same page automatically. Reload the page after changes
made in a different browser session.

### Updating

After an integration update, restart Home Assistant and reload each browser or app
frontend to load the updated JavaScript module. An already open frontend continues
running the previously loaded module until refreshed.

The resource URL is `/jablotron80/frontend/jablotron-user-code-card.js`. The card
types are `custom:jablotron-user-code-manager` and `custom:jablotron-disarm-card`.

Updates do not automatically add cards or change dashboard layouts and resource
registration.

## Security and limits

* Authenticated account IDs come from HA, never from request data. Every operation
  rechecks an active, non-system account and permission to control the alarm entity.
* HTTP accepts saves/removals; there is no API to read a stored PIN back. Status and
  disarm WebSocket messages contain no PIN. The saved-code path adds no PIN to dashboard configuration,
  entities, service-call events, automation traces, or the audit event. Native manual
  PIN service calls retain HA's existing behavior and are outside that guarantee.
* Personal PINs use private, atomic HA Store writes to `.storage/jablotron80.user_codes`
  with permissions 0600. Storage is plaintext unless encryption is enabled; see [ENCRYPTION.md](ENCRYPTION.md). Protect server access and backups, and do not log HTTP request bodies.
* Disarm requests serialize per panel, wait at least 15 seconds between attempts,
  and allow at most three attempts per five minutes. Limits reset on HA restart.
  Saved-code commands disable automatic serial retries. The native manual controls
  retain their existing behavior.
* Already disarmed/disarming, unavailable, unknown, and service states block sending a
  saved PIN. This matters because a repeated master PIN can toggle arming back on.
