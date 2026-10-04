# GitHub-Toshiba-AC

Home Assistant custom integration for Toshiba air conditioners. Talks to
Toshiba's cloud service to control units and read their state.

- **Domain:** `toshiba_ac` — **IoT class:** `cloud_push`
- **Version:** see `custom_components/toshiba_ac/manifest.json`
- **HACS:** yes, installable from the HACS default repository

## Where things live

```
custom_components/toshiba_ac/   the integration
├── __init__.py                 setup, connection, error classification
├── const.py                    domain, config keys
├── config_flow.py              UI setup and validation
├── entity.py                   base entity classes
├── entity_description.py       entity description dataclasses
├── feature_list.py             per-model feature flags
├── climate.py                  climate platform
├── select.py  sensor.py  switch.py   the other platforms
├── diagnostics.py              data for HA's diagnostics download
└── services.yaml               the reconnect service

tests/                          pytest suite, HA is stubbed in conftest.py
docs/                           publishable documentation
docs-internal/                  local notes, gitignored, never leave the machine
```

Start with `docs/codebase-architecture.md` for how a state update travels from
the cloud to an entity.

## Commands

There is a `.venv` and a devcontainer, and both work. Pick one:

```bash
# with the venv
./venv-create                    # creates .venv
.venv/bin/pip install -r requirements_dev.txt
.venv/bin/pre-commit run --all-files
.venv/bin/python -m pytest tests/

# with the devcontainer (container CLI, HA on :9123)
container start
container check
```

Run pre-commit before presenting any change. CI runs the same hooks plus
hassfest and HACS validation; it does **not** run pytest.

```bash
.venv/bin/pre-commit install                 # once, to hook into commits
.venv/bin/pre-commit run black --all-files   # a single hook
```

If a hook rewrites files, stage them again — otherwise the next commit sees a
stale index and the hook fails a second time.

## Dependencies

Runtime requirements live in `manifest.json`, not in `requirements.txt` —
that is what Home Assistant and HACS install. `toshiba-ac` contains all the
actual device communication; this repository only maps cloud calls onto HA
entities. Issues about protocol or device behaviour belong upstream at
[KaSroka/Toshiba-AC-control](https://github.com/KaSroka/Toshiba-AC-control).

Known discrepancy: `manifest.json` pins `toshiba-ac==0.3.13`, while
`requirements.txt` still says `0.3.11`. `manifest.json` is authoritative.

`azure-iot-device` is pinned to a release candidate because `toshiba-ac==0.3.13`
requires exactly that version. There is no stable 2.15.0 to move to.

## Working on the code

- Validate the shape of a Home Assistant API against the installed HA source
  before using it. `async_dismiss` and `async_create` on
  `homeassistant.components.persistent_notification` are `@callback`, meaning
  synchronous — awaiting them raises `TypeError`. The same applies to
  `async_update_entry` and `services.async_register`.
- Mock such APIs with `MagicMock`, not `AsyncMock`. An `AsyncMock` accepts being
  awaited and hides exactly this class of mistake.
- Tests stub Home Assistant in `tests/conftest.py`; there is no real HA in the
  venv. Add new stubs there rather than in each test module.
- Entity availability follows the device: while a unit is off it reports no
  values over AMQP, so its entities are `unavailable`. Feature-gated entities
  (fireplace mode, 8 °C heating) only exist on models that have them. Both are
  expected, not bugs.

## Things users hit most

- Toshiba allows **one** active connection per account. A second Home
  Assistant or the app being open makes commands fail with an error that looks
  like a credential problem. It is not one.
- Toshiba's WAF rate-limits `POST /api/Consumer/Login`. Repeated failed setups
  make it worse; wait instead of retrying.
- North American units use a different system entirely and will not work here.

## Releasing

Bump the version in **both** files, then merge to `main`:

1. `custom_components/toshiba_ac/manifest.json` → `"version": "YYYY.M.PATCH"`
2. this file → `- **Version:** YYYY.M.PATCH`

Format is `YYYY.M.PATCH` based on the current month, patch increments within a
month. `release.yml` picks up the version from the manifest and builds the
archive, so nothing else needs tagging by hand.

## Documentation

`docs/` is publishable — no IPs, no credentials, no local setups, no issue
analysis. Anything local goes in `docs-internal/` (German, gitignored) or
`secrets.env` (gitignored, referenced by path only).

| File | Content |
|------|---------|
| `docs/codebase-architecture.md` | Platforms, transports, error handling |
| `docs/authentication.md` | Credentials, token lifecycle, setup failures |
| `docs-internal/testumgebung.md` | Test instance, entities, test scenarios |
| `docs-internal/analyse.md` | Open issue analysis, PR triage |

The workspace rules in `/workspace/development/AGENTS.md` apply here too.

## Keeping this file honest

This file is read by every agent before it touches the repo, so a stale line
here causes wrong work. When changing something:

- Do not copy code into this file. Point at the file and let the agent read it.
  Verbatim imports and function bodies go stale silently.
- Do not write version numbers you have not just read out of the repo. If two
  files disagree, say so instead of picking one.
- Do not record the state of a task in progress or what was done for a past
  issue. Those belong in `docs-internal/analyse.md` or in the commit.
- After a change, re-check the numbers, paths and commands above against the
  repo. A stale command here wastes more time than a missing one.
