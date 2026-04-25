# qingyun-skills Maintenance Prompt

Read this file before installing, upgrading, auditing, or uninstalling skills in this repository.

This document is written for both humans and agents. Treat it as the operating manual for the local skill mirror in this directory.

## Role

You are maintaining a portable local mirror of agent skills.

Your job is to keep four things consistent:

1. `skills/` contains the actual local skill folders.
2. `catalog.yaml` is the source of truth for provenance, dependencies, cleanup behavior, and maintenance policy.
3. `mise.toml` declares the curated runtime and global CLI layer.
4. `uv-requirements.txt` declares the curated shared Python package layer.

Python policy in this repo:

- CLI tools: install with `uv tool install`
- Python packages for the default machine Python: install with `uv pip install --system`
- Do not pin a Python version if the system already has a usable default Python
- If the machine has no usable Python, let `uv` download one explicitly, for example `uv python install 3.12`

## Primary Files

- `catalog.yaml`
- `mise.toml`
- `uv-requirements.txt`
- `skills/`

## Hard Rules

1. Resolve `REPO_ROOT` first. Do not assume this repository lives in `~/projects`.
2. Do not persist absolute repository paths in tracked files when a repo-relative form is possible.
3. Do not guess a skill's upstream. Use `catalog.yaml`.
4. Do not remove a shared environment until no skill references it.
5. Do not use `rsync --delete` or equivalent destructive sync behavior by default.
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
- `browser-use` can run in different browser modes; some host browser setups are optional, not mandatory.

### `sync_policy`

This explains how to refresh local skill folders from upstream.

Current meaning:

- preferred copy mode: `rsync -a`
- default deletion policy: do not delete local extras
- rationale: some skill folders intentionally keep local bootstrap artifacts or tiny local wording changes

In plain language: sync forward carefully, but do not assume the local mirror must be byte-identical to upstream after every update.

### Source Garbage Collection

A source entry in `catalog.yaml` should exist only if at least one skill still references it.

When a skill is reassigned to a different upstream, or when the last skill using a source is removed, prune the now-unused source entry in the same change.

### Environment Garbage Collection

A shared environment can be removed only if no remaining skill references it in either:

- `depends_on`
- `optional_depends_on`

For host applications marked `managed_by_repo: false`, this repo tracks the relationship but does not own installation or removal.

## Resolve `REPO_ROOT`

Before running any install or symlink commands:

```bash
cd /path/to/qingyun-skills
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

- Chrome or Chromium for browser-backed skills
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

This installs the curated Node/Bun runtime layer and the global npm-backed CLI layer defined in `mise.toml`.

### 4. Install Python packages and tools with `uv`

```bash
cd "$REPO_ROOT"
uv tool install browser-use
uv pip install --system -r uv-requirements.txt
python -m playwright install chromium
```

If the machine does not already have a usable system Python, use a fallback interpreter managed by `uv`:

```bash
uv python install 3.12
uv tool install --python 3.12 browser-use
uv pip install --python 3.12 -r uv-requirements.txt
uv run --python 3.12 python -m playwright install chromium
```

Optional if you want `browser-use` to launch its own managed Chromium instead of attaching to an existing browser:

```bash
browser-use install
```

### 5. Create the `.agents` symlink

```bash
mkdir -p "$HOME/.agents"
ln -sfn "$REPO_ROOT/skills" "$HOME/.agents/skills"
```

### 6. Bootstrap local helper dependencies for selected `baoyu-*` skills

Some `baoyu-*` skills keep local helper dependencies inside the skill directory.

```bash
for d in "$REPO_ROOT"/skills/baoyu-{danger-gemini-web,danger-x-to-markdown,format-markdown,markdown-to-html,post-to-wechat,post-to-weibo,post-to-x,translate,url-to-markdown}/scripts; do
  (cd "$d" && npx -y bun install)
done

(cd "$REPO_ROOT"/skills/baoyu-slide-deck/scripts && npx -y bun add pptxgenjs pdf-lib)
(cd "$REPO_ROOT"/skills/baoyu-comic/scripts && npx -y bun add pdf-lib)
```

## Upgrade Workflow

When updating one skill or a group of skills:

1. Look up the skill entry in `catalog.yaml`.
2. Use its `source`, `upstream_path`, and `upstream_url` to locate the correct upstream folder.
3. Refresh the upstream clone.
4. Copy the upstream folder into the matching local folder with `rsync -a`.
5. Preserve any local exceptions documented in `notes`.
6. Re-run any skill-specific bootstrap steps if needed.
7. Verify the updated skill still resolves through `.agents/skills`.

Example upgrade command pattern:

```bash
rsync -a "$UPSTREAM_DIR/" "$REPO_ROOT/skills/<skill-name>/"
```

Do not add `--delete` unless the maintenance task explicitly calls for destructive cleanup and you have reviewed local-only artifacts first.

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
python3 - <<'PY'
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
- `mise uninstall bun`
- `mise uninstall npm:defuddle`
- `mise uninstall npm:vercel`

### Remove a `uv` tool

```bash
uv tool uninstall browser-use
```

### Remove shared `uv` Python packages from the system Python

```bash
uv pip uninstall --system <package-name>
```

Examples:

- `uv pip uninstall --system playwright`
- `uv pip uninstall --system lxml`

If the machine is using the fallback Python that `uv` downloaded instead of a system Python, use the matching fallback form:

```bash
uv pip uninstall --python 3.12 <package-name>
```

### Remove apt-managed packages

As with apt installation, the agent should prepare the exact `sudo apt remove ...` command, but the user should run it manually.

```bash
sudo apt remove <package-name>
```

Use this only when the environment is truly unreferenced and nothing else on the machine needs it.

## Cleanup Profiles

### `none`

No known extra cleanup outside the skill directory.

### `baoyu-user-config`

These skills may store preferences or prompts outside the repo:

- `~/.baoyu-skills/<skill-name>`
- `$XDG_CONFIG_HOME/baoyu-skills/<skill-name>`

Delete these by default when uninstalling that skill.

## Verification

Run this after install, upgrade, or uninstall work:

```bash
cd "$REPO_ROOT"

python3 - <<'PY'
import yaml
from pathlib import Path

catalog = yaml.safe_load(Path("catalog.yaml").read_text(encoding="utf-8"))
envs = set(catalog["environments"])

for skill in catalog["skills"]:
    for key in skill.get("depends_on", []) + skill.get("optional_depends_on", []):
        if key not in envs:
            raise SystemExit(f"missing environment reference: {skill['name']} -> {key}")

print("catalog references are internally consistent")
PY

test -L "$HOME/.agents/skills"
test "$(readlink -f "$HOME/.agents/skills")" = "$REPO_ROOT/skills"
ls -1 "$HOME/.agents/skills" | wc -l
```

## Short Decision Rules

- Installing a new skill: add the skill entry, add any new shared environments if needed, then install only the missing environments.
- Upgrading a skill: sync from the recorded upstream, preserve local exceptions, then verify.
- Removing a skill: remove the skill entry first, then garbage-collect only the unreferenced environments.
- Unsure about an upstream: stop and update `catalog.yaml` before touching files.
