# qingyun-skills Maintenance Prompt

Read this file before installing, upgrading, auditing, or uninstalling skills in this repository.

This document is written for both humans and agents. Treat it as the operating manual for the local skill mirror in this directory.

## Role

You are maintaining a portable local mirror of agent skills.

Your job is to keep four things consistent:

1. `skills/` contains the actual local skill folders.
2. `catalog.yaml` is the source of truth for provenance, dependencies, cleanup behavior, and maintenance policy.
3. `mise.toml` declares the curated runtime and global CLI layer.
4. `pyproject.toml` and `uv.lock` declare the curated project-local Python environment.

Python policy in this repo:

- Python packages are managed in `pyproject.toml` with `uv add`, `uv remove`, and `uv sync`.
- Python packages must not be installed into the system Python for this repo.
- Prefer Python 3.12 for the project environment: `uv sync --python 3.12` creates or updates `.venv`.
- CLI tools that are standalone global tools still use the existing manager documented for that tool: `mise` for npm-backed CLIs. Do not add a Python `uv tool install` policy unless a future tool requires it.

## Primary Files

- `catalog.yaml`
- `mise.toml`
- `pyproject.toml`
- `uv.lock`
- `skills/`

## Hard Rules

1. Resolve `REPO_ROOT` first. The canonical local checkout is `~/qingyun-skills`, but verify the actual path before running commands.
2. Do not persist absolute repository paths in tracked files when a repo-relative form is possible.
3. Do not guess a skill's upstream. Use `catalog.yaml`.
4. Do not remove a shared environment until no skill references it.
5. Upstream-backed skill refreshes use `rsync -a --delete` after confirming the catalog entry is not a local-created skill; local-created skills are never overwritten from an upstream directory.
6. When uninstalling a skill, delete that skill's own generated user data and local state by default.
7. Only keep skill-generated data if the uninstall task explicitly asks to preserve it.
8. If a skill has local wording adaptations or bootstrap artifacts, preserve them unless the maintenance task explicitly says to replace them.
9. Do not run privileged `sudo apt ...` commands on the user's behalf by default. Prepare the exact command and let the user run it manually.
10. Do not keep unused entries under `sources` in `catalog.yaml`. Every source must be referenced by at least one skill.

## Concepts

### `depends_on`

This is the required environment set for a skill.

If a skill references an environment here, the environment must exist for that skill's normal workflow to work.

### `optional_depends_on`

This is for expanded workflows, host integrations, or optional capabilities.

Examples:

- `drawio` can still produce `.drawio` files without the desktop app, but export workflows benefit from it.

### `sync_policy`

This explains how to refresh local skill folders from upstream.

Current meaning:

- preferred copy mode: `rsync -a --delete`
- default deletion policy: delete local extras when syncing upstream-backed skills
- local-created skills are exempt because their source of truth is this repository
- local wrappers follow their catalog notes instead of wholesale replacement unless those notes explicitly say the wrapper mirrors upstream

In plain language: upstream-backed skill folders are refreshed as mirrors of their recorded upstream path, while local-created skills are edited directly in this repository.

### Source Garbage Collection

A source entry in `catalog.yaml` should exist only if at least one skill still references it.

When a skill is reassigned to a different upstream, or when the last skill using a source is removed, prune the now-unused source entry in the same change.

### Environment Garbage Collection

A shared environment can be removed only if no remaining skill references it in either:

- `depends_on`
- `optional_depends_on`

For host applications marked `managed_by_repo: false`, this repo tracks the relationship but does not own installation or removal.

## Resolve `REPO_ROOT`

Before running any install or symlink commands, use the actual checkout path. On this machine the canonical local checkout is `~/qingyun-skills`:

```bash
cd "$HOME/qingyun-skills"
export REPO_ROOT="$PWD"
```

## Install Workflow

Follow this order on a new Ubuntu machine.

### 1. Install system packages

Install the required apt-managed packages referenced by the environment inventory.

Important:

- the apt package list is managed here in the repo
- the exact `sudo apt ...` command should be prepared by the agent
- the user is expected to run that privileged command manually

Suggested command for the user to run:

```bash
sudo apt update
sudo apt install -y \
  libreoffice qpdf pdftk-java tesseract-ocr poppler-utils pandoc
```

Host applications that are useful but not managed by this repo:

- draw.io Desktop for drawio export workflows
- an `obsidian` command or launcher for `obsidian-cli`

### 2. Install `mise` and `uv`

Use the official installers:

- `mise`: https://mise.jdx.dev/
- `uv`: https://docs.astral.sh/uv/

### 3. Install runtimes and global CLIs with `mise`

```bash
cd "$REPO_ROOT"
mise install
```

This installs the curated Node runtime layer and the global npm-backed CLI layer defined in `mise.toml`.

### 4. Create or update the project Python environment with `uv`

```bash
cd "$REPO_ROOT"
uv sync --python 3.12
uv run python -m playwright install chromium
```

`uv sync --python 3.12` creates or updates `$REPO_ROOT/.venv`.

### 5. Expose the repo Python environment first on PATH

Edit `~/.config/env.sh` so later path prepends put the repo virtual environment before system Python. Add this line immediately after the existing `_env_prepend_path "$HOME/llama.cpp/build/bin"` line:

```sh
_env_prepend_path "$HOME/qingyun-skills/.venv/bin"
```

After `.venv` exists and `~/.config/env.sh` is sourced, `python` should resolve to `$REPO_ROOT/.venv/bin/python`.

### 6. Create the `.agents` symlink

```bash
mkdir -p "$HOME/.agents"
ln -sfn "$REPO_ROOT/skills" "$HOME/.agents/skills"
```

## Upgrade Workflow

When updating one skill or a group of skills:

1. Look up the skill entry in `catalog.yaml`.
2. Check the skill `type` before copying anything:
   - If `type: local_created`, do not run upstream `rsync`; edit the local skill directly.
   - If `type: local_wrapper`, follow the entry `notes` and do not replace the wrapper wholesale unless the notes explicitly say the wrapper mirrors upstream.
   - If `type: upstream`, continue with the upstream refresh.
3. Use its `source`, `upstream_path`, and `upstream_url` to locate the correct upstream folder.
4. Refresh the upstream clone.
5. Copy the upstream folder into the matching local folder with `rsync -a --delete`.
6. Review `notes` before syncing and preserve any documented local exceptions.
7. Re-run any skill-specific bootstrap steps if needed.
8. Verify the updated skill still resolves through `.agents/skills`.

Example upgrade command pattern for upstream-backed skills:

```bash
rsync -a --delete "$UPSTREAM_DIR/" "$REPO_ROOT/skills/<skill-name>/"
```

`--delete` is required for upstream-backed skills, so review `notes` before syncing and never apply the upstream rsync command to `local_created` skills.

## Uninstall Workflow

When removing one skill cleanly:

1. Remove the skill folder under `skills/`.
2. Remove the skill entry from `catalog.yaml`.
3. If that removal leaves its `source` unused, remove the now-unreferenced source entry from `catalog.yaml`.
4. Remove the paths listed by the skill's `cleanup_profile` by default.
5. Recompute which environments are still referenced by remaining skills.
6. Remove only the environments that have zero remaining references and are safe to uninstall.
7. Re-run verification.

## Dependency Impact Check

To see which skills still use a given environment:

```bash
uv run python - <<'PY'
import yaml
from pathlib import Path

catalog = yaml.safe_load(Path("catalog.yaml").read_text(encoding="utf-8"))
target = "uv-pkg/playwright"

for skill in catalog["skills"]:
    refs = set(skill.get("depends_on", [])) | set(skill.get("optional_depends_on", []))
    if target in refs:
        print(skill["name"])
PY
```

Change `target` to any environment key from `catalog.yaml`.

## Suggested Environment Removal Commands

These commands are examples. Use them only after the dependency impact check says the environment is no longer referenced.

### Remove a `mise` runtime or global CLI

```bash
mise uninstall <tool-spec>
```

Examples:

- `mise uninstall node`
- `mise uninstall npm:defuddle`

### Add project Python packages with `uv`

```bash
uv add --raw <package-name>
uv sync --python 3.12
```

Use `--raw` so unpinned package names stay unpinned unless the maintainer intentionally supplies a version specifier.

### Remove project Python packages with `uv`

```bash
uv remove <package-name>
uv sync --python 3.12
```

Examples:

- `uv remove playwright`
- `uv remove lxml`

### Remove apt-managed packages

As with apt installation, the agent should prepare the exact `sudo apt remove ...` command, but the user should run it manually.

```bash
sudo apt remove <package-name>
```

Use this only when the environment is truly unreferenced and nothing else on the machine needs it.

## Cleanup Profiles

### `none`

No known extra cleanup outside the skill directory.

## Verification

Run this after install, upgrade, or uninstall work:

```bash
cd "$REPO_ROOT"
uv sync --python 3.12
. "$HOME/.config/env.sh"
command -v python
python -c 'import sys; assert sys.executable.endswith("/qingyun-skills/.venv/bin/python"), sys.executable; assert sys.version_info[:2] == (3, 12), sys.version'

uv run python - <<'PY'
import yaml
from pathlib import Path

catalog = yaml.safe_load(Path("catalog.yaml").read_text(encoding="utf-8"))
envs = set(catalog["environments"])

for skill in catalog["skills"]:
    for key in skill.get("depends_on", []) + skill.get("optional_depends_on", []):
        if key not in envs:
            raise SystemExit(f"missing environment reference: {skill['name']} -> {key}")
    if "type" not in skill:
        raise SystemExit(f"missing skill type: {skill['name']}")

print("catalog references and skill types are internally consistent")
PY

test -L "$HOME/.agents/skills"
test "$(readlink -f "$HOME/.agents/skills")" = "$REPO_ROOT/skills"
```

## Short Decision Rules

- Installing a new skill: add the skill entry, add any new shared environments if needed, then install only the missing environments.
- Upgrading a skill: sync from the recorded upstream according to skill `type`, preserve local exceptions, then verify.
- Removing a skill: remove the skill entry first, then garbage-collect only the unreferenced environments.
- Unsure about an upstream: stop and update `catalog.yaml` before touching files.
