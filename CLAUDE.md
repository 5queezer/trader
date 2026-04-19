# CLAUDE.md

Autonomous trading agent on Gnosis chain (Open Autonomy / ABCI / Tendermint).
Python 3.10–3.11 (not 3.12). Package manager: uv. Linters: tomte.

## Commands

```bash
tox -e py3.10-linux                             # full skill tests
pytest packages/valory/skills/<skill>/tests/    # one skill
make format                                     # black + isort
make code-checks                                # full lint suite
make security                                   # bandit + safety + gitleaks
make all-checks                                 # everything
make generators                                 # regen hashes + copyrights + docstrings
autonomy packages lock                          # content-addressed hash refresh
make run-agent                                  # run locally with tendermint
```

## Conventions

- Black (88 cols), isort (3-line), sphinx docstrings (darglint), type hints (mypy strict optional).
- Apache 2.0 copyright header + `# -*- coding: utf-8 -*-` on every file — auto-checked.
- After modifying any `packages/` content: **`make generators`** + `autonomy packages lock`, or CI fails the hash check.
- **CI enforces 100% coverage**. After editing, run `--cov=packages.valory.skills.<skill>.<module>` for *every* file you touched, not just the primary one.
- After adding/removing deps: update `pyproject.toml` **and** `tox.ini` ([deps-packages], [extra-deps]), then `uv lock` + `uv sync --all-groups`, then `tox -e check-dependencies`.

## Pull context — read when the task touches these areas

Deeper notes live in a separate Obsidian vault so they don't eat every session's token budget. Read the relevant file when relevant:

- **`obsidian/Architecture overview.md`** — three-repo system (this repo + `5queezer/olas-operate-middleware` + `5queezer/olas-dashboard`), what runs where, ABCI skill pattern, composition via `trader_abci`.
- **`obsidian/Deploying trader changes.md`** — end-to-end runbook from code edit to running agent: `make generators` → IPFS push → hetzner IPFS transfer → middleware PATCH. Non-obvious.
- **`obsidian/IPFS setup.md`** — why we self-host kubo on hetzner instead of using Autonolas's registry or Pinata.
- **`obsidian/Credentials and secrets.md`** — middleware login password, key locations, agent addresses on Gnosis.
- **`obsidian/Troubleshooting.md`** — catalogue of every weird failure we've hit (stale Coolify containers, aea_cli_ipfs version check, Pinata paid tier, PATCH timeouts). Check here before diagnosing fresh.
- **`obsidian/Tech debt.md`** — known workarounds and cleanup candidates.

The vault also has a `README.md` that indexes everything as Obsidian wikilinks.
