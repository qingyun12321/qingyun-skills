from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_latest_imagegen_result.py"
SPEC = importlib.util.spec_from_file_location("extract_latest_imagegen_result", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load extractor module from {SCRIPT_PATH}")
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)

VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
VALID_RESULT = base64.b64encode(VALID_PNG).decode("ascii")


def image_result(result: str = VALID_RESULT, call_id: str = "call-1") -> dict[str, str]:
    return {
        "type": "image_generation_end",
        "result": result,
        "call_id": call_id,
    }


class ExtractLatestImagegenResultTests(unittest.TestCase):
    def test_iter_jsonl_files_scans_active_and_archived_sessions_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory)
            active = codex_home / "sessions" / "active.jsonl"
            archived = codex_home / "archived_sessions" / "nested" / "archived.jsonl"
            active.parent.mkdir(parents=True)
            archived.parent.mkdir(parents=True)
            active.write_text("{}\n", encoding="utf-8")
            archived.write_text("{}\n", encoding="utf-8")
            os.utime(active, (100, 100))
            os.utime(archived, (200, 200))

            self.assertEqual(
                extractor.iter_jsonl_files(codex_home, None),
                [archived, active],
            )
            self.assertEqual(
                extractor.iter_jsonl_files(codex_home, active),
                [active],
            )

    def test_find_latest_result_skips_bad_json_and_finds_last_nested_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / "session.jsonl"
            first = {"payload": image_result(call_id="first")}
            last = {"outer": [{"inner": image_result(call_id="last")}]} 
            session.write_text(
                "\n".join((json.dumps(first), "{bad json", json.dumps(last))) + "\n",
                encoding="utf-8",
            )

            source, result, call_id = extractor.find_latest_result([session])

            self.assertEqual(source, session)
            self.assertEqual(result, VALID_RESULT)
            self.assertEqual(call_id, "last")

    def test_find_latest_result_skips_unreadable_or_empty_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing.jsonl"
            empty = root / "empty.jsonl"
            valid = root / "valid.jsonl"
            empty.write_text("not json\n", encoding="utf-8")
            valid.write_text(json.dumps(image_result(call_id="valid")) + "\n", encoding="utf-8")

            source, _, call_id = extractor.find_latest_result([missing, empty, valid])

            self.assertEqual(source, valid)
            self.assertEqual(call_id, "valid")

    def test_safe_stem_removes_unsafe_characters_and_has_a_fallback(self) -> None:
        cases = {
            "plain_name-2.png": "plain_name-2.png",
            "hello world": "hello-world",
            "../../evil": "evil",
            "...": "imagegen-enhanced",
            "你好": "imagegen-enhanced",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(extractor.safe_stem(value), expected)

    def test_non_overwriting_path_uses_next_available_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory)
            (out_dir / "restored.png").write_bytes(b"existing")
            (out_dir / "restored-v2.png").write_bytes(b"existing")

            candidate = extractor.non_overwriting_path(out_dir, "restored")

            self.assertEqual(candidate, out_dir / "restored-v3.png")
            self.assertFalse(candidate.exists())

    def test_main_accepts_argv_writes_valid_png_and_prints_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "session.jsonl"
            out_dir = root / "output"
            session.write_text(
                json.dumps({"payload": image_result(call_id="png-call")}) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                return_code = extractor.main(
                    [
                        "--session",
                        str(session),
                        "--out-dir",
                        str(out_dir),
                        "--stem",
                        "restored image",
                    ]
                )

            report = json.loads(stdout.getvalue())
            output = out_dir / "restored-image.png"
            self.assertEqual(return_code, 0)
            self.assertEqual(output.read_bytes(), VALID_PNG)
            self.assertEqual(
                report,
                {
                    "output": str(output),
                    "bytes": len(VALID_PNG),
                    "call_id": "png-call",
                    "source_session": str(session),
                },
            )

    def test_main_rejects_decoded_data_without_png_signature(self) -> None:
        invalid_result = base64.b64encode(b"\x89PNGnot-a-valid-png").decode("ascii")
        self.assertTrue(invalid_result.startswith(extractor.PNG_PREFIX))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "session.jsonl"
            out_dir = root / "output"
            session.write_text(json.dumps(image_result(invalid_result)) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "not a PNG"):
                extractor.main(
                    [
                        "--session",
                        str(session),
                        "--out-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(list(out_dir.glob("*.png")), [])


if __name__ == "__main__":
    unittest.main()
