#!/usr/bin/env python3
"""Build a combined Markdown draft from Unlimited-OCR page outputs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


DET_TAG_RE = re.compile(r"<\|det\|>.*?\[[0-9,\s]+\]<\|/det\|>")
PAGE_NUM_RE = re.compile(r"(?:^|[_-])page[_-]?(\d+)", re.IGNORECASE)


def natural_key(path: Path) -> tuple[int, str]:
    match = PAGE_NUM_RE.search(path.stem)
    if match:
        return (int(match.group(1)), path.name)
    numbers = re.findall(r"\d+", path.stem)
    if numbers:
        return (int(numbers[-1]), path.name)
    return (10**9, path.name)


def clean_page(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = DET_TAG_RE.sub("", text)
    text = text.replace("<|det|>", "").replace("<|/det|>", "")
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned = "\n".join(lines).strip()
    if cleaned.count("```") % 2:
        cleaned = f"{cleaned}\n```"
    return cleaned


def build_markdown(pages_dir: Path, output: Path, page_separator: bool) -> None:
    pages = sorted(pages_dir.glob("*.md"), key=natural_key)
    if not pages:
        raise SystemExit(f"No Markdown pages found in {pages_dir}")

    parts: list[str] = []
    for index, page in enumerate(pages, start=1):
        text = clean_page(page.read_text(encoding="utf-8", errors="replace"))
        if not text:
            continue
        if page_separator and len(pages) > 1:
            parts.append(f"<!-- page {index}: {page.name} -->\n\n{text}")
        else:
            parts.append(text)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n---\n\n".join(parts).strip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages_dir", help="Directory containing Unlimited-OCR .md page outputs")
    parser.add_argument("--output", default="", help="Combined Markdown output path")
    parser.add_argument(
        "--no-page-separator",
        action="store_true",
        help="Do not insert page boundary comments and horizontal rules",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pages_dir = Path(args.pages_dir).expanduser().resolve(strict=False)
    output = (
        Path(args.output).expanduser().resolve(strict=False)
        if args.output
        else pages_dir.parent / "readable.md"
    )
    build_markdown(pages_dir, output, not args.no_page_separator)
    print(f"Readable Markdown draft: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
