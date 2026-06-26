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

Bash equivalent:

```bash
./.venv/Scripts/python.exe -m pytest -v
```

Home Assistant is deliberately **not** installed; the stubs in `conftest.py`
provide everything the integration imports at module load time.
