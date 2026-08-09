#!/usr/bin/env python3
"""Offline tests for Unlimited-OCR Markdown reconstruction."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_readable_markdown.py"
SPEC = importlib.util.spec_from_file_location("build_readable_markdown", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


class MarkdownCleaningTest(unittest.TestCase):
    def test_natural_key_orders_page_numbers_and_generic_numeric_names(self) -> None:
        paths = [
            Path("book_page_10.md"),
            Path("appendix.md"),
            Path("book-page-2.md"),
            Path("scan_3.md"),
            Path("book_page_001.md"),
        ]
        self.assertEqual(
            [path.name for path in sorted(paths, key=builder.natural_key)],
            ["book_page_001.md", "book-page-2.md", "scan_3.md", "book_page_10.md", "appendix.md"],
        )

    def test_clean_page_removes_detection_tags_and_closes_code_fence(self) -> None:
        raw = (
            "<|det|>title [116, 54, 475, 83]<|/det|># Heading  \r\n"
            "<|det|>body<|/det|>\r"
            "```python\nprint('ok')   \n"
        )
        self.assertEqual(builder.clean_page(raw), "# Heading\nbody\n```python\nprint('ok')\n```")

    def test_clean_page_normalizes_blank_content(self) -> None:
        self.assertEqual(builder.clean_page(" \r\n\t\r\n"), "")
        self.assertEqual(builder.clean_page("<|det|><|/det|>"), "")


class MarkdownBuildTest(unittest.TestCase):
    def test_build_naturally_sorts_pages_skips_empty_page_and_keeps_physical_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = root / "pages"
            pages.mkdir()
            (pages / "doc_page_10.md").write_text("Tenth\n", encoding="utf-8")
            (pages / "doc_page_2.md").write_text("Second\n", encoding="utf-8")
            (pages / "doc_page_3.md").write_text("  \n", encoding="utf-8")
            output = root / "document.md"

            builder.build_markdown(pages, output, page_separator=True)

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "<!-- page 1: doc_page_2.md -->\n\nSecond\n\n---\n\n"
                "<!-- page 3: doc_page_10.md -->\n\nTenth\n",
            )

    def test_build_can_omit_page_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = root / "pages"
            pages.mkdir()
            (pages / "page_1.md").write_text("First", encoding="utf-8")
            (pages / "page_2.md").write_text("Second", encoding="utf-8")
            output = root / "combined.md"

            builder.build_markdown(pages, output, page_separator=False)

            self.assertEqual(output.read_text(encoding="utf-8"), "First\n\n---\n\nSecond\n")

    def test_all_empty_pages_produce_an_empty_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = root / "pages"
            pages.mkdir()
            (pages / "page_1.md").write_text(" \n", encoding="utf-8")
            output = root / "combined.md"

            builder.build_markdown(pages, output, page_separator=True)

            self.assertEqual(output.read_text(encoding="utf-8"), "\n")

    def test_missing_page_files_fail_without_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = root / "pages"
            pages.mkdir()
            output = root / "combined.md"

            with self.assertRaisesRegex(SystemExit, "No Markdown pages found"):
                builder.build_markdown(pages, output, page_separator=True)

            self.assertFalse(output.exists())

    def test_parse_args_and_main_accept_explicit_argv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pages = root / "pages"
            pages.mkdir()
            (pages / "page_1.md").write_text("Text", encoding="utf-8")
            output = root / "result.md"

            parsed = builder.parse_args([str(pages), "--output", str(output), "--no-page-separator"])
            self.assertEqual(parsed.pages_dir, str(pages))
            self.assertTrue(parsed.no_page_separator)

            with contextlib.redirect_stdout(io.StringIO()):
                result = builder.main([str(pages), "--output", str(output)])
            self.assertEqual(result, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "Text\n")


if __name__ == "__main__":
    unittest.main()
