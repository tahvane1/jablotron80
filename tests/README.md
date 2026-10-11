# jablotron80 starter test suite

A small, runnable pytest suite for the `jablotron80` Home Assistant custom
integration. It tests the integration's core logic **without installing Home
Assistant** - `conftest.py` stubs the few `homeassistant.*` modules that
`jablotron.py` (and the package `__init__.py`) import.

## What is covered

| File | What it protects |
| --- | --- |
| `test_reconciliation.py` | The **#153 per-sensor-close** logic: a closed detector turns off independently of another still-open one (`_activate_source` / `_update_device` on `JA80CentralUnit`). This is the most important test on the `fix/153-per-sensor-close` branch. |
| `test_state.py` | `JablotronState` status-byte classification helpers (`is_armed_state`, `is_disarmed_state`, `is_alarm_state`, exit/entering delay, maintenance). |
| `test_keypress.py` | `JablotronKeyPress.get_beep_option`, including upstream **issue #44** (`KeyError: 6` for the missing beep code), captured via `pytest.raises`. |

## How the Home Assistant stub works

`jablotron.py` imports `homeassistant.{core,const,config_entries}` at module top,
and importing the `custom_components.jablotron80` package also runs its
`__init__.py`, which pulls in the HA platform stack
(`homeassistant.components.*`, `homeassistant.helpers.*`).

`tests/conftest.py` inserts lightweight fake modules into `sys.modules` **before**
the integration is imported, and adds the repo root to `sys.path` so that
`import custom_components.jablotron80.jablotron` resolves as a package. No real
Home Assistant install is required (or wanted).

Setting a device's `.active` runs through a `@log_change` decorator that schedules
`asyncio ... create_task(publish_updates())`. The `event_loop_for_setters` fixture
installs a real current event loop so those setters are safe, and drains the
no-op tasks at teardown.

## Running

From the repo root (`C:\dev\jablotron-upstream`):

```powershell
# one-time setup
C:\Python314\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install pytest pyserial crccheck

# run the suite
.\.venv\Scripts\python.exe -m pytest -v
```

Bash equivalent (including dependencies for the credential tests):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pytest pyserial crccheck voluptuous cryptography
.venv/bin/python -m pytest -v
node tests/test_user_code_card.cjs
```

## Account-scoped codes and encryption

`test_user_codes.py` and `test_user_code_api.py` exercise authenticated account
ownership, permissions, validation, persistence, manual fallback, disarm throttling,
secret-free replies/audit events, and commands without automatic PIN retries.
`test_credentials.py` uses real Fernet encryption and temporary keys to exercise
scope binding, master/imported-code protection, key rotation, interrupted migration,
wrong/missing keys, and disabling encryption. `test_credential_options.py` covers
options-flow migration, all four code-mode/encryption combinations, unchanged legacy
defaults, key generation, and failed-write rejection.

The Node test uses a fake card DOM and HA client to check input clearing, account
switches, save confirmation, secret-free disarm calls, and native manual fallback.
These tests do not contact a real alarm or use production PINs. HA API/storage
interfaces are stubs; passing them does not replace testing startup and UI rendering
in a running HA instance.

Home Assistant is deliberately **not** installed; the stubs in `conftest.py`
provide everything the integration imports at module load time.
