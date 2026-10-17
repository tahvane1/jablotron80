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
bundle; personal PIN records are encrypted too. Choose encryption explicitly
when enabling personal codes; changing code mode alone does not enable it.
Existing master credentials are retained in both code modes.

## Optional frontend, separate from your dashboard

The integration provides alarm entities, panel communication, credential storage
and authenticated APIs. It does not create or edit dashboards, add cards, or
register dashboard resources automatically. Each dashboard owner chooses the
layout and controls. The compact A/AB/ABC prototype and its hold-to-confirm buttons
are not part of this integration.

Two independent, optional cards are bundled in the integration:

* **My Jablotron code** (`jablotron-user-code-card`) only saves, replaces or forgets
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

1. Install/update the integration and restart HA. No file needs to be copied to `www`.
2. In dashboard resources add this URL as a **JavaScript module**:
   `/jablotron80/frontend/jablotron-user-code-card.js`.
   For YAML-managed resources use:

   ```yaml
   resources:
     - url: /jablotron80/frontend/jablotron-user-code-card.js
       type: module
   ```

3. Select `personal` in integration options if you want account codes. Choose
   encryption separately; enabling personal mode alone does not enable encryption.
4. Add either card to your chosen dashboard, or put PIN management on a separate view.

Management only:

```yaml
type: custom:jablotron-user-code-card
entity: alarm_control_panel.your_jablotron_panel
```

Optional saved-code disarming, independently of the management card:

```yaml
type: custom:jablotron-disarm-card
entity: alarm_control_panel.your_jablotron_panel
```

Card labels follow HA's language (Czech, English or French; English fallback).
Fixed backend error messages remain Czech; the cards show a local translated error
instead of displaying arbitrary exception text. The form clears the PIN immediately
on submission, after invalid input, account/entity changes, and when removed from
the page. It never pre-fills a saved PIN. Saving confirms storage only. A disarm API
success confirms submission, not panel acceptance; check the alarm's actual state.

### Updating and migrating from the prototype

After an integration update, restart HA and reload each browser/app frontend so the
new module is loaded. The asset is served without long-lived cache headers. An
already open browser still runs its previously loaded module until refreshed.

Replace the old `/local/jablotron-user-code-card.js?...` resource with the bundled
URL; do not load both. The old file in `www` is not removed automatically and may
be deleted after other dashboards have been checked. The earlier combined
`jablotron-user-code-card` now displays management only: add the separate disarm card
if you previously used its disarm button. Dashboard YAML, resource choices, existing
PINs and encryption keys are not changed automatically. Do not replace unrelated
custom dashboard controls unless you intend to migrate them.

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
* The previous prototype was exercised with a JA83 and JA82-T on HA 2026.9.1;
  this branch additionally has account, permission, persistence, API and frontend tests.
  The test suite uses HA stubs, not a complete running HA environment.

HACS updates from the original repository can overwrite custom changes.
