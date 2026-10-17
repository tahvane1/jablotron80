# Optional encrypted code storage

Account-scoped codes and encryption are provided together. Encryption is an independent option:
`common` and `personal` modes both support encryption enabled or disabled.
Defaults remain common mode and unencrypted storage for compatibility.

Fernet authenticated encryption protects the configured master PIN, the complete
imported panel code table (including code1/code2), and all personal PINs for this
config entry, including accounts whose codes are not used in common mode. Tokens
bind panel and account identity to prevent copying a token into another record.
Raw serial debug logs now honor the existing HIDE_CODE/HIDE_KEY_PRESS flags
(default enabled), including code-table packets; parser error logs omit raw records.
Do not disable these flags or add external raw bus logging.
The master PIN remains stored for configuration and existing panel operations; encryption does not remove its privileges or replace it with a user PIN. This partially addresses the security concern in [upstream #43](https://github.com/tahvane1/jablotron80/issues/43), but does not implement its request to never store the master PIN. See [the upstream issue coverage](USER-CODES.md#relationship-to-upstream-issues) for the exact limits of personal-code disarming and related requests.
HA decrypts credentials in memory when needed. No plaintext PIN is returned to the
frontend; encryption status contains only a boolean.

## Enable on any HA installation

1. Install the updated integration and restart HA. The bundled frontend is optional;
   see [USER-CODES.md](USER-CODES.md) for resource registration.
2. Open integration options. Select the code mode independently of encryption.
3. Enable **Encrypt stored codes**. Enter an absolute key-file path as seen by the
   HA process. For first-time setup, enable **Create encryption key file if missing**.
4. Save. The key is generated with 32 random bytes and permissions 0600, using
   exclusive creation. An existing key is validated and never replaced. Existing
   credentials are migrated before applying settings. Migration never controls
   the alarm or tests a PIN against the panel.

The default key path is `hass.config.path(".jablotron80.key")`; there is no required
Docker path, environment variable, external vault, or operating-system service.
HA OS users can use the default config-directory path directly from the UI.
HA Core users can supply a private file readable by the HA service account.
Automatically created key files request permissions **0600** (`rw-------`): only
the owner can read and write; the group and other users have no access. The owner
is the operating-system user running Home Assistant, not the HA account signed
in through the browser. The process umask may further restrict these permissions;
it cannot grant additional access. The parent directory must already exist and
be writable by HA. Existing key files are validated, never overwritten or
automatically chmodded.
A pre-created Fernet key file must have owner-only permissions (0600 or 0400).
Do not place a key under `www`, and do not paste its contents into a PIN field.

## Separating the key from configuration backups

**Recommended: store the key outside `/config` and back it up separately from
HA configuration and encrypted code files.** Anyone who obtains both ciphertext
and its key can decrypt the saved PINs. Keeping both in the same directory backup
therefore removes this protection if that backup is disclosed. File permissions
alone do not protect a backup that already includes the key.

The default config-directory path is a convenient setup option, including on HA
OS, but does not provide this backup separation. An alternative path must be
persistent and accessible to the HA process after a reboot. Entering a path in
integration options does not create a Docker mount or grant access to host files.
On HA OS, only choose a location actually available to Home Assistant Core; do not
assume that a path visible in an app/add-on is also visible to Core.

Storing the key outside `/config` is not sufficient if a full-system backup or
snapshot still captures both locations. Check what each backup includes and keep
the separate key backup private and recoverable. Without the original key,
encrypted codes cannot be recovered. This separation protects copies made without
the key; an administrator or compromised HA process able to read both can still
decrypt them.
Protect existing backups too: migrating current files does not erase old plaintext
backups or securely erase filesystem history, snapshots, or SSD blocks.

For Docker, an optional read-only mount is sufficient:

```yaml
services:
  homeassistant:
    volumes:
      - /path/on/host/jablotron80.key:/run/secrets/jablotron80.key:ro
```

Generate the key on the host first, restrict access to its owner, and make it
readable by the user running HA inside the container. Then enter
`/run/secrets/jablotron80.key` in integration options; leave key creation disabled.
The mount is an installation detail, not an integration requirement. Docker Compose
file-based secrets likewise do not encrypt the source key file on the host.

## Rotation, restore, disabling, and rollback

Generate a new key at a **different path**, keep the old file readable, and save
options with the new path. Migration decrypts with each original key, validates
account/panel scope, and re-encrypts with the new key. Keep old keys until you no
longer need backups encrypted with them. Never overwrite an active key file.

Turning encryption off requires the original key and deliberately writes plaintext
again. There is no fallback to a master PIN for missing personal credentials or
undecryptable data. Missing, invalid, over-permissive keys or corrupt encrypted
records reject migration; encrypted setup does not silently become unencrypted.
Recover the original key at its recorded path when restoring a backup, or migrate
with the old key accessible before changing paths. Without the key the old codes
cannot be recovered; resupply credentials rather than replace the key silently.

Config entries and the private user Store are separate HA files. Each encrypted
record carries its format version and key-file path, allowing restart recovery if
only part of a migration was persisted. There is no cross-file atomic transaction;
a storage failure may leave a mixture of valid old/new records. Do not remove old
keys until migration and backups have been checked. Normal HA config-entry writes
use HA's own persistence scheduling.

Before returning to an older integration, disable encryption successfully using
this version. The older integration cannot read the encrypted bundle. Otherwise
restore a matching pre-upgrade configuration backup with the old integration.

Encryption protects code files copied without the key. It does not protect against
an administrator able to read both files, malicious code running inside HA, or
access to a logged-in HA account. Decrypted codes necessarily exist in HA memory.
Removing the key file does not erase already decrypted runtime memory; restart
is required to unload the integration. Panel programming/PIN changes remain manual.

## Dependencies and references

Fernet reference: https://cryptography.io/en/latest/fernet/
HA 2026.9.1 supplies cryptography as a Core dependency:
https://github.com/home-assistant/core/blob/2026.9.1/pyproject.toml
The integration uses that dependency without imposing a conflicting version pin.
