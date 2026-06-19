#!/usr/bin/env python3
"""Extract the latest built-in image_gen PNG result from Codex session JSONL."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path


PNG_PREFIX = "iVBOR"


def iter_jsonl_files(codex_home: Path, explicit_session: Path | None) -> list[Path]:
    if explicit_session is not None:
        return [explicit_session]

    roots = [
        codex_home / "sessions",
        codex_home / "archived_sessions",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(root.rglob("*.jsonl"))
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def find_latest_result(files: list[Path]) -> tuple[Path, str, str | None]:
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for line in reversed(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            found = find_result_in_object(obj)
            if found is not None:
                result, call_id = found
                return path, result, call_id

    raise RuntimeError("No inline built-in image_gen PNG result found in Codex session JSONL files")


def find_result_in_object(value: object) -> tuple[str, str | None] | None:
    if isinstance(value, dict):
        if (
            value.get("type") == "image_generation_end"
            and isinstance(value.get("result"), str)
            and value["result"].startswith(PNG_PREFIX)
        ):
            return value["result"], value.get("call_id")

        for child in value.values():
            found = find_result_in_object(child)
            if found is not None:
                return found

    if isinstance(value, list):
        for child in value:
            found = find_result_in_object(child)
            if found is not None:
                return found

    return None


def safe_stem(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return value or "imagegen-enhanced"


def non_overwriting_path(out_dir: Path, stem: str) -> Path:
    candidate = out_dir / f"{stem}.png"
    index = 2
    while candidate.exists():
        candidate = out_dir / f"{stem}-v{index}.png"
        index += 1
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, help="Directory where the recovered PNG should be written")
    parser.add_argument("--stem", default="imagegen-enhanced", help="Output filename stem")
    parser.add_argument("--session", help="Optional specific Codex session JSONL file")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"))
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser()
    session = Path(args.session).expanduser() if args.session else None
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    source, result, call_id = find_latest_result(iter_jsonl_files(codex_home, session))
    raw = base64.b64decode(result)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Decoded image_gen result was not a PNG")

    output = non_overwriting_path(out_dir, safe_stem(args.stem))
    output.write_bytes(raw)

    print(json.dumps({
        "output": str(output),
        "bytes": len(raw),
        "call_id": call_id,
        "source_session": str(source),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
