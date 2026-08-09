#!/usr/bin/env python3
"""Offline tests for the Unlimited-OCR runner."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_unlimited_ocr.py"
SPEC = importlib.util.spec_from_file_location("run_unlimited_ocr", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ocr = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ocr
SPEC.loader.exec_module(ocr)


class InputHelpersTest(unittest.TestCase):
    def test_detect_input_types_and_rejects_unknown_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image_dir = root / "images"
            image_dir.mkdir()

            self.assertEqual(ocr.detect_input(image_dir), "image_dir")
            self.assertEqual(ocr.detect_input(root / "SCAN.PDF"), "pdf")
            for suffix in (".png", ".JPG", ".jpeg", ".webp", ".bmp"):
                with self.subTest(suffix=suffix):
                    self.assertEqual(ocr.detect_input(root / f"scan{suffix}"), "single_image")
            with self.assertRaisesRegex(SystemExit, "Unsupported input type"):
                ocr.detect_input(root / "notes.txt")

    def test_safe_stem_sanitizes_names_and_has_a_fallback(self) -> None:
        self.assertEqual(ocr.safe_stem(Path("Quarterly report (final).pdf")), "Quarterly-report-final")
        self.assertEqual(ocr.safe_stem(Path("...---.pdf")), "ocr")
        self.assertEqual(ocr.safe_stem(Path("报告.pdf")), "ocr")

    def test_default_combined_markdown_is_source_adjacent(self) -> None:
        source = Path("/work/report.PDF")
        self.assertEqual(ocr.default_combined_md(source, "pdf"), Path("/work/report.md"))
        self.assertEqual(
            ocr.default_combined_md(Path("/work/page.PNG"), "single_image"),
            Path("/work/page.md"),
        )
        self.assertEqual(
            ocr.default_combined_md(Path("/work/scans"), "image_dir"),
            Path("/work/scans.md"),
        )


class CommandConstructionTest(unittest.TestCase):
    def args(self, image_mode: str = "auto") -> argparse.Namespace:
        return argparse.Namespace(
            image_mode=image_mode,
            concurrency=2,
            attention_backend="flashinfer",
            gpu="1",
        )

    def test_pdf_command_uses_pdf_input_and_base_mode(self) -> None:
        command = ocr.build_infer_command(
            Path("/repo"),
            Path("/model"),
            "pdf",
            Path("/input/file.pdf"),
            Path("/output/pages"),
            Path("/output/server.log"),
            self.args(),
        )

        self.assertEqual(command[:4], ["uv", "run", "python", "infer.py"])
        self.assertEqual(command[command.index("--image_mode") + 1], "base")
        self.assertEqual(command[command.index("--concurrency") + 1], "2")
        self.assertEqual(command[command.index("--gpu") + 1], "1")
        self.assertEqual(command[-2:], ["--pdf", "/input/file.pdf"])
        self.assertNotIn("--image_dir", command)

    def test_image_command_uses_directory_input_and_gundam_mode(self) -> None:
        command = ocr.build_infer_command(
            Path("/repo"),
            Path("/model"),
            "image_dir",
            Path("/input/images"),
            Path("/output/pages"),
            Path("/output/server.log"),
            self.args(),
        )

        self.assertEqual(command[command.index("--image_mode") + 1], "gundam")
        self.assertEqual(command[-2:], ["--image_dir", "/input/images"])
        self.assertNotIn("--pdf", command)

    def test_parse_args_and_main_accept_explicit_argv(self) -> None:
        parsed = ocr.parse_args(["scan.pdf", "--gpu", "3", "--dry-run"])
        self.assertEqual(parsed.input, "scan.pdf")
        self.assertEqual(parsed.gpu, "3")
        self.assertTrue(parsed.dry_run)

        with mock.patch.object(ocr, "run", return_value=13) as run:
            self.assertEqual(ocr.main(["other.pdf", "--concurrency", "4"]), 13)
        self.assertEqual(run.call_args.args[0].input, "other.pdf")
        self.assertEqual(run.call_args.args[0].concurrency, 4)


class ProcessSafetyTest(unittest.TestCase):
    def test_matching_processes_filters_unrelated_and_current_processes(self) -> None:
        process_table = """\
100 python -m sglang.launch_server --model /elsewhere
101 python /repo/infer.py --model_dir /model
102 python /elsewhere/infer.py --model_dir /elsewhere
103 python /repo/scripts/monitor_infer.py -- command
104 harmless worker
bad malformed
"""
        with (
            mock.patch.object(ocr.os, "getpid", return_value=100),
            mock.patch.object(ocr.subprocess, "check_output", return_value=process_table),
        ):
            matches = ocr.matching_processes(Path("/repo"), Path("/model"))

        self.assertEqual(
            matches,
            {
                101: "python /repo/infer.py --model_dir /model",
                103: "python /repo/scripts/monitor_infer.py -- command",
            },
        )

    def test_matching_processes_treats_ps_failure_as_no_matches(self) -> None:
        failure = subprocess.CalledProcessError(1, ["ps"])
        with mock.patch.object(ocr.subprocess, "check_output", side_effect=failure):
            self.assertEqual(ocr.matching_processes(Path("/repo"), Path("/model")), {})

    def test_safe_exit_reports_only_new_processes(self) -> None:
        before = {10: "existing server"}
        after = {10: "existing server", 12: "new infer"}
        output = io.StringIO()
        with (
            mock.patch.object(ocr, "matching_processes", return_value=after),
            contextlib.redirect_stdout(output),
        ):
            result = ocr.check_safe_exit(Path("/repo"), Path("/model"), before)

        self.assertEqual(result, 2)
        self.assertIn("PID 12: new infer", output.getvalue())
        self.assertNotIn("PID 10", output.getvalue())

        with mock.patch.object(ocr, "matching_processes", return_value=before):
            self.assertEqual(ocr.check_safe_exit(Path("/repo"), Path("/model"), before), 0)

    def test_run_preserves_infer_failure_and_returns_residual_code_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            model = root / "model"
            source = root / "source.pdf"
            (repo / "infer.py").parent.mkdir(parents=True)
            (repo / "infer.py").touch()
            model.mkdir()
            source.touch()
            base_argv = [
                str(source),
                "--repo",
                str(repo),
                "--model-dir",
                str(model),
                "--run-dir",
                str(root / "run"),
            ]

            for infer_code, expected, combines in ((7, 7, False), (0, 2, True)):
                with self.subTest(infer_code=infer_code):
                    args = ocr.parse_args(base_argv)
                    completed = argparse.Namespace(returncode=infer_code)
                    process_snapshots = [{10: "existing"}, {10: "existing", 11: "new"}]
                    with (
                        mock.patch.object(ocr.shutil, "which", return_value="/usr/bin/uv"),
                        mock.patch.object(ocr.subprocess, "run", return_value=completed),
                        mock.patch.object(ocr, "matching_processes", side_effect=process_snapshots),
                        mock.patch.object(ocr, "build_readable_markdown", return_value=0) as build,
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        result = ocr.run(args)

                    self.assertEqual(result, expected)
                    self.assertEqual(build.called, combines)

    def test_dry_run_uses_default_markdown_without_starting_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            model = root / "model"
            source = root / "source.pdf"
            (repo / "infer.py").parent.mkdir(parents=True)
            (repo / "infer.py").touch()
            model.mkdir()
            source.touch()
            args = ocr.parse_args(
                [str(source), "--repo", str(repo), "--model-dir", str(model), "--dry-run"]
            )
            output = io.StringIO()
            with (
                mock.patch.object(ocr.shutil, "which", return_value="/usr/bin/uv"),
                mock.patch.object(ocr.subprocess, "run") as subprocess_run,
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(ocr.run(args), 0)

            subprocess_run.assert_not_called()
            self.assertIn(f"Readable Markdown: {source.with_suffix('.md')}", output.getvalue())


if __name__ == "__main__":
    unittest.main()
