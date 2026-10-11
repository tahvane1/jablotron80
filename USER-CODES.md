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

| Code mode | Encryption | Disarming through the optional card |
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

## Install the optional card

Copy `www/jablotron-user-code-card.js` to HA's `www` directory and register
`/local/jablotron-user-code-card.js?v=account-codes` as a JavaScript module resource.
Restart HA after installing the integration. Select `personal` in integration options.

```yaml
type: custom:jablotron-user-code-card
entity: alarm_control_panel.your_jablotron_panel
```

The card opens the native manual-PIN dialog for accounts without a saved code.
Saving shows confirmation beside the Save button and clears the input afterwards.
The optional card currently uses Czech text, independently of the HA language. Integration options are translated through the normal HA translation files. Saving a PIN confirms storage only; it does not confirm that the panel accepts that PIN. A successful disarm API response confirms that the command was submitted; the alarm entity reports the resulting panel state.

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
