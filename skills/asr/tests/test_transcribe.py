from __future__ import annotations

import argparse
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "transcribe.py"
SPEC = importlib.util.spec_from_file_location("asr_transcribe", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
TRANSCRIBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRANSCRIBE)


class UrlTests(unittest.TestCase):
    def test_recognizes_supported_remote_urls(self) -> None:
        for value in (
            "http://example.com/audio.wav",
            "https://example.com/audio.wav",
            "oss://bucket/audio.wav",
        ):
            with self.subTest(value=value):
                self.assertTrue(TRANSCRIBE.is_url(value))

    def test_rejects_local_and_unsupported_values(self) -> None:
        for value in ("audio.wav", "/tmp/audio.wav", "ftp://example.com/audio.wav"):
            with self.subTest(value=value):
                self.assertFalse(TRANSCRIBE.is_url(value))


class ResultParsingTests(unittest.TestCase):
    def test_extracts_sentence_text_with_speakers_and_deduplicates(self) -> None:
        result = {
            "transcripts": [
                {
                    "speaker_id": 1,
                    "sentences": [
                        {"text": " Hello ", "speaker_id": 1},
                        {"content": "World", "speaker_id": 2},
                        {"text": "Hello", "speaker_id": 1},
                    ],
                }
            ]
        }

        self.assertEqual(
            TRANSCRIBE.extract_text_lines(result),
            ["Speaker 1: Hello", "Speaker 2: World"],
        )

    def test_extracts_nested_fallback_text_but_not_word_fragments(self) -> None:
        result = {
            "result": {
                "speaker_id": "A",
                "segments": [{"text": "First", "words": [{"text": "ignored"}]}],
                "summary": {"content": "Second"},
            }
        }

        self.assertEqual(
            TRANSCRIBE.extract_text_lines(result),
            ["Speaker A: First", "Speaker A: Second"],
        )

    def test_returns_successful_transcription_url(self) -> None:
        query = {
            "output": {
                "task_status": "SUCCEEDED",
                "results": [
                    {"subtask_status": "FAILED", "transcription_url": "https://bad"},
                    {"subtask_status": "SUCCEEDED", "transcription_url": "https://good"},
                ],
            }
        }

        self.assertEqual(TRANSCRIBE.result_url(query), "https://good")

    def test_rejects_failed_task_or_missing_successful_result(self) -> None:
        cases = (
            {"output": {"task_status": "FAILED"}},
            {"output": {"task_status": "SUCCEEDED", "results": []}},
        )
        for query in cases:
            with self.subTest(query=query):
                with self.assertRaises(TRANSCRIBE.AsrError):
                    TRANSCRIBE.result_url(query)


class SubmissionTests(unittest.TestCase):
    def test_submit_task_builds_expected_payload_without_network(self) -> None:
        args = argparse.Namespace(
            api_host="asr.example.test",
            api_key="test-key",
            model="fun-asr",
            language_hints=" zh, en, ,",
            speaker_count=2,
        )
        response = {"output": {"task_id": "task-1"}}

        with mock.patch.object(TRANSCRIBE, "api_json", return_value=response) as api_json:
            actual = TRANSCRIBE.submit_task(args, "oss://bucket/audio.wav")

        self.assertIs(actual, response)
        api_json.assert_called_once_with(
            "POST",
            "https://asr.example.test/api/v1/services/audio/asr/transcription",
            "test-key",
            {
                "model": "fun-asr",
                "input": {"file_urls": ["oss://bucket/audio.wav"]},
                "parameters": {
                    "channel_id": [0],
                    "diarization_enabled": True,
                    "speaker_count": 2,
                    "language_hints": ["zh", "en"],
                },
            },
            async_task=True,
            resolve_oss=True,
        )



class LocalMediaTests(unittest.TestCase):
    def test_prepares_compact_mono_opus_for_diarization(self) -> None:
        with mock.patch.object(TRANSCRIBE.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with mock.patch.object(TRANSCRIBE.subprocess, "run") as run:
                output = TRANSCRIBE.prepare_local_audio(
                    Path("/media/lesson.mp4"), Path("/tmp/asr-work")
                )

        self.assertEqual(output, Path("/tmp/asr-work/lesson.mono16k.opus"))
        command = run.call_args.args[0]
        self.assertIn("libopus", command)
        self.assertIn("32k", command)
        self.assertEqual(command[command.index("-ac") + 1], "1")
        self.assertEqual(command[command.index("-ar") + 1], "16000")

    def test_temporary_upload_has_transfer_deadlines_and_redacts_policy(self) -> None:
        policy = {
            "upload_dir": "tmp/upload",
            "upload_host": "https://upload.example.test",
            "oss_access_key_id": "temporary-access-id",
            "signature": "temporary-signature",
            "policy": "temporary-policy",
            "x_oss_object_acl": "private",
            "x_oss_forbid_overwrite": "true",
        }
        failure = TRANSCRIBE.subprocess.CalledProcessError(28, ["curl", "secret"])

        with mock.patch.object(TRANSCRIBE, "get_upload_policy", return_value=policy):
            with mock.patch.object(TRANSCRIBE.subprocess, "run", side_effect=failure) as run:
                with self.assertRaises(TRANSCRIBE.AsrError) as raised:
                    TRANSCRIBE.upload_temporary_file(
                        "api-key", "fun-asr", Path("/tmp/audio.opus")
                    )

        command = run.call_args.args[0]
        self.assertEqual(
            command[command.index("--connect-timeout") + 1],
            str(TRANSCRIBE.UPLOAD_CONNECT_TIMEOUT_SECONDS),
        )
        self.assertEqual(
            command[command.index("--max-time") + 1],
            str(TRANSCRIBE.UPLOAD_TIMEOUT_SECONDS),
        )
        self.assertEqual(
            run.call_args.kwargs["timeout"], TRANSCRIBE.UPLOAD_TIMEOUT_SECONDS + 5
        )
        self.assertEqual(
            str(raised.exception), "temporary upload failed with curl exit code 28"
        )



class ResumeTests(unittest.TestCase):
    @staticmethod
    def args(output_dir: Path) -> argparse.Namespace:
        return argparse.Namespace(
            output_dir=str(output_dir),
            api_host="asr.example.test",
            api_key="test-key",
            model="fun-asr",
            language_hints="zh,en",
            speaker_count=None,
            poll_interval=0,
            timeout=60,
            restart=False,
        )

    def test_poll_timeout_keeps_checkpoint_and_rerun_resumes_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / "lesson.mp4"
            media.write_bytes(b"media")
            output_dir = root / "output"
            args = self.args(output_dir)

            with mock.patch.object(
                TRANSCRIBE, "prepare_local_audio", return_value=root / "audio.opus"
            ), mock.patch.object(
                TRANSCRIBE, "upload_temporary_file", return_value="oss://audio"
            ), mock.patch.object(
                TRANSCRIBE, "submit_task", return_value={"output": {"task_id": "task-1"}}
            ), mock.patch.object(
                TRANSCRIBE,
                "poll_task",
                side_effect=TRANSCRIBE.AsrError("task did not finish"),
            ):
                with self.assertRaisesRegex(TRANSCRIBE.AsrError, "did not finish"):
                    TRANSCRIBE.transcribe_one(args, str(media))

            checkpoint = output_dir / ".lesson.asr-task.json"
            self.assertTrue(checkpoint.exists())
            succeeded = {
                "output": {
                    "task_status": "SUCCEEDED",
                    "results": [
                        {
                            "subtask_status": "SUCCEEDED",
                            "transcription_url": "https://result.example.test/task-1.json",
                        }
                    ],
                }
            }
            with mock.patch.object(TRANSCRIBE, "prepare_local_audio") as prepare, mock.patch.object(
                TRANSCRIBE, "upload_temporary_file"
            ) as upload, mock.patch.object(TRANSCRIBE, "submit_task") as submit, mock.patch.object(
                TRANSCRIBE, "poll_task", return_value=succeeded
            ) as poll, mock.patch.object(
                TRANSCRIBE, "download_json", return_value={}
            ), mock.patch.object(
                TRANSCRIBE, "extract_text_lines", return_value=["Speaker 0: 你好"]
            ):
                transcript = TRANSCRIBE.transcribe_one(args, str(media))

            prepare.assert_not_called()
            upload.assert_not_called()
            submit.assert_not_called()
            self.assertEqual(poll.call_args.args[1], "task-1")
            self.assertEqual(transcript.read_text(encoding="utf-8"), "Speaker 0: 你好\n")
            self.assertFalse(checkpoint.exists())

    def test_terminal_failure_removes_checkpoint_for_clean_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / "lesson.mp4"
            media.write_bytes(b"media")
            output_dir = root / "output"
            args = self.args(output_dir)

            with mock.patch.object(
                TRANSCRIBE, "prepare_local_audio", return_value=root / "audio.opus"
            ), mock.patch.object(
                TRANSCRIBE, "upload_temporary_file", return_value="oss://audio"
            ), mock.patch.object(
                TRANSCRIBE, "submit_task", return_value={"output": {"task_id": "task-2"}}
            ), mock.patch.object(
                TRANSCRIBE,
                "poll_task",
                return_value={"output": {"task_status": "FAILED"}},
            ):
                with self.assertRaisesRegex(TRANSCRIBE.AsrError, "did not succeed"):
                    TRANSCRIBE.transcribe_one(args, str(media))

            self.assertFalse((output_dir / ".lesson.asr-task.json").exists())

    def test_restart_discards_saved_task_before_new_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            media = root / "lesson.mp4"
            media.write_bytes(b"media")
            output_dir = root / "output"
            output_dir.mkdir()
            args = self.args(output_dir)
            args.restart = True
            checkpoint = output_dir / ".lesson.asr-task.json"
            TRANSCRIBE.save_checkpoint(
                checkpoint,
                fingerprint=TRANSCRIBE.input_fingerprint(str(media)),
                api_host=args.api_host,
                model=args.model,
                task_id="task-old",
            )

            with mock.patch.object(
                TRANSCRIBE,
                "prepare_local_audio",
                side_effect=TRANSCRIBE.AsrError("conversion failed"),
            ):
                with self.assertRaisesRegex(TRANSCRIBE.AsrError, "conversion failed"):
                    TRANSCRIBE.transcribe_one(args, str(media))

            self.assertFalse(checkpoint.exists())


class ArgumentBoundaryTests(unittest.TestCase):
    def test_missing_api_key_fails_before_processing(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(TRANSCRIBE, "transcribe_one") as transcribe_one:
                with self.assertRaisesRegex(TRANSCRIBE.AsrError, "API_KEY"):
                    TRANSCRIBE.main(["input.wav"])

        transcribe_one.assert_not_called()

    def test_speaker_count_rejects_values_outside_inclusive_range(self) -> None:
        for count in (1, 101):
            with self.subTest(count=count):
                with mock.patch.object(TRANSCRIBE, "transcribe_one") as transcribe_one:
                    with self.assertRaisesRegex(TRANSCRIBE.AsrError, "between 2 and 100"):
                        TRANSCRIBE.main(
                            ["input.wav", "--api-key", "test-key", "--speaker-count", str(count)]
                        )
                transcribe_one.assert_not_called()

    def test_speaker_count_accepts_both_boundaries(self) -> None:
        for count in (2, 100):
            with self.subTest(count=count):
                with mock.patch.object(
                    TRANSCRIBE, "transcribe_one", return_value=Path("transcript.txt")
                ) as transcribe_one:
                    with mock.patch("sys.stdout", new_callable=io.StringIO):
                        exit_code = TRANSCRIBE.main(
                            [
                                "input.wav",
                                "--api-key",
                                "test-key",
                                "--speaker-count",
                                str(count),
                                "--jobs",
                                "1",
                            ]
                        )

                self.assertEqual(exit_code, 0)
                self.assertEqual(transcribe_one.call_args.args[0].speaker_count, count)

    def test_jobs_rejects_zero_and_accepts_one(self) -> None:
        with mock.patch.object(TRANSCRIBE, "transcribe_one") as transcribe_one:
            with self.assertRaisesRegex(TRANSCRIBE.AsrError, "at least 1"):
                TRANSCRIBE.main(["input.wav", "--api-key", "test-key", "--jobs", "0"])
        transcribe_one.assert_not_called()

        with mock.patch.object(
            TRANSCRIBE, "transcribe_one", return_value=Path("transcript.txt")
        ) as transcribe_one:
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                exit_code = TRANSCRIBE.main(
                    ["input.wav", "--api-key", "test-key", "--jobs", "1"]
                )

        self.assertEqual(exit_code, 0)
        transcribe_one.assert_called_once()
        self.assertEqual(transcribe_one.call_args.args[0].jobs, 1)


if __name__ == "__main__":
    unittest.main()
