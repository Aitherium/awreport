# awreport for agents

Read this if you are an agent (or a human) editing this package. Short on
purpose: the commands, the traps that cost a session, and where the rest lives.
Nothing here is read at runtime — it is for you.

## What this is

PyPI distribution **`awreport`** (version in `pyproject.toml`), import package
`awreport`, Python >= 3.10. File a bug report that has already scrubbed your
secrets and collapsed the duplicate.

This repository is a **synced mirror** of the AitherOS monorepo (lane
`.github/workflows/sync-awreport.yml`). Hand edits made here are overwritten on
the next sync — change the source and let the lane publish.

## Build, test, verify

```bash
python -m pytest tests -q        # the suite: 84 tests, green at v0.2.0
pip install -e .                 # editable install for developing against it
```

The suite was run from a source checkout with no prior install. The publish
lane (`publish-brick.yml`) additionally builds the wheel, installs it and
imports it — a tree that tests green can still ship a broken wheel.

## Rules that keep this useful

- **The redactor is adversarially tested, and that test wins.** 
  `test_redact_adversarial.py` exists because a scrubbing pass that is
  "usually right" leaks the one report that mattered. Any change to
  redaction lands with new adversarial cases in the same commit — and when
  in doubt, scrub.
- **A report that cannot be scrubbed does not get filed.** The consumer
  contract (`adk/bugreport.py`) refuses to file anything the redactor
  cannot vouch for; keep that refusal reachable and loud.
- **Garbage collects at the intake.** Duplicate collapse is part of the
  product (`test_hosted_intake.py`), not a nicety — the same crash filed
  forty times is how a real report gets missed.
- **The registry drives the public surface.** This repo's README header and
  `aither-manifest.json` are generated from the ecosystem registry (one yaml
  in the AitherOS monorepo) and rewritten on every sync. Change the registry;
  do not hand-edit the generated blocks.

## Read next

- `llms.txt` — the install/use card written for an agent to execute
- `README.md` — the human front door
- `docs/` — the generated docs site source
