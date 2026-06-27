#!/usr/bin/env python3
"""Submit Alibaba Cloud Model Studio Fun-ASR transcription jobs."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib import error, parse, request


DEFAULT_HOST = "llm-plmvo15iruk58svw.cn-beijing.maas.aliyuncs.com"
UPLOAD_POLICY_URL = "https://dashscope.aliyuncs.com/api/v1/uploads"
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELED", "UNKNOWN"}


class AsrError(RuntimeError):
    pass


def is_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https", "oss"}


def api_json(
    method: str,
    url: str,
    api_key: str,
    body: dict[str, Any] | None = None,
    *,
    async_task: bool = False,
    resolve_oss: bool = False,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if async_task:
        headers["X-DashScope-Async"] = "enable"
    if resolve_oss:
        headers["X-DashScope-OssResourceResolve"] = "enable"
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AsrError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise AsrError(f"{method} {url} failed: {exc}") from exc


def download_json(url: str) -> dict[str, Any]:
    try:
        with request.urlopen(url, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AsrError(f"download transcription_url failed: HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise AsrError(f"download transcription_url failed: {exc}") from exc


def prepare_local_audio(input_path: Path, temp_dir: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise AsrError("ffmpeg is required for local media files but was not found on PATH")
    output = temp_dir / f"{input_path.stem}.mono16k.wav"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output),
    ]
    subprocess.run(cmd, check=True)
    return output


def get_upload_policy(api_key: str, model_name: str) -> dict[str, Any]:
    query = parse.urlencode({"action": "getPolicy", "model": model_name})
    return api_json("GET", f"{UPLOAD_POLICY_URL}?{query}", api_key).get("data", {})


def upload_temporary_file(api_key: str, model_name: str, path: Path) -> str:
    policy = get_upload_policy(api_key, model_name)
    required = [
        "upload_dir",
        "upload_host",
        "oss_access_key_id",
        "signature",
        "policy",
        "x_oss_object_acl",
        "x_oss_forbid_overwrite",
    ]
    missing = [key for key in required if not policy.get(key)]
    if missing:
        raise AsrError(f"upload policy response missing field(s): {', '.join(missing)}")

    file_name = path.name
    object_key = f"{policy['upload_dir'].rstrip('/')}/{file_name}"
    cmd = [
        "curl",
        "-fsS",
        "-X",
        "POST",
        "-F",
        f"OSSAccessKeyId={policy['oss_access_key_id']}",
        "-F",
        f"Signature={policy['signature']}",
        "-F",
        f"policy={policy['policy']}",
        "-F",
        f"x-oss-object-acl={policy['x_oss_object_acl']}",
        "-F",
        f"x-oss-forbid-overwrite={policy['x_oss_forbid_overwrite']}",
        "-F",
        f"key={object_key}",
        "-F",
        "success_action_status=200",
        "-F",
        f"file=@{path};filename={file_name}",
        policy["upload_host"],
    ]
    subprocess.run(cmd, check=True)
    return f"oss://{object_key}"


def submit_task(args: argparse.Namespace, file_url: str) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "channel_id": [0],
        "diarization_enabled": True,
    }
    if args.speaker_count is not None:
        parameters["speaker_count"] = args.speaker_count
    if args.language_hints:
        parameters["language_hints"] = [item.strip() for item in args.language_hints.split(",") if item.strip()]

    body = {
        "model": args.model,
        "input": {"file_urls": [file_url]},
        "parameters": parameters,
    }
    url = f"https://{args.api_host}/api/v1/services/audio/asr/transcription"
    return api_json(
        "POST",
        url,
        args.api_key,
        body,
        async_task=True,
        resolve_oss=file_url.startswith("oss://"),
    )


def poll_task(args: argparse.Namespace, task_id: str, label: str) -> dict[str, Any]:
    url = f"https://{args.api_host}/api/v1/tasks/{parse.quote(task_id)}"
    deadline = time.time() + args.timeout
    last_status = ""
    while True:
        result = api_json("GET", url, args.api_key)
        output = result.get("output", {})
        status = output.get("task_status", "")
        if status and status != last_status:
            print(f"{label}: task {task_id}: {status}", file=sys.stderr)
            last_status = status
        if status in TERMINAL_STATUSES:
            return result
        if time.time() >= deadline:
            raise AsrError(f"task {task_id} did not finish within {args.timeout} seconds")
        time.sleep(args.poll_interval)


def result_url(query_result: dict[str, Any]) -> str:
    output = query_result.get("output", {})
    if output.get("task_status") != "SUCCEEDED":
        raise AsrError(f"task did not succeed: {json.dumps(query_result, ensure_ascii=False)}")
    for item in output.get("results", []):
        if item.get("subtask_status") == "SUCCEEDED" and item.get("transcription_url"):
            return item["transcription_url"]
    raise AsrError(f"no successful transcription_url found: {json.dumps(query_result, ensure_ascii=False)}")


def extract_text_lines(value: Any) -> list[str]:
    lines: list[str] = []

    def append(text: Any, speaker: Any = None) -> None:
        if not isinstance(text, str) or not text.strip():
            return
        prefix = f"Speaker {speaker}: " if speaker is not None else ""
        line = prefix + text.strip()
        if line not in lines:
            lines.append(line)

    if isinstance(value, dict) and isinstance(value.get("transcripts"), list):
        for transcript in value["transcripts"]:
            if not isinstance(transcript, dict):
                continue
            sentences = transcript.get("sentences")
            if isinstance(sentences, list) and sentences:
                for sentence in sentences:
                    if isinstance(sentence, dict):
                        append(
                            sentence.get("text") or sentence.get("content") or sentence.get("sentence"),
                            sentence.get("speaker_id", transcript.get("speaker_id")),
                        )
            else:
                append(transcript.get("text") or transcript.get("content"), transcript.get("speaker_id"))
        if lines:
            return lines

    def walk(node: Any, speaker: str | None = None) -> None:
        if isinstance(node, dict):
            current_speaker = str(node.get("speaker_id", speaker)) if node.get("speaker_id", speaker) is not None else None
            text = node.get("text") or node.get("content") or node.get("sentence")
            append(text, current_speaker)
            for key, child in node.items():
                if key == "words":
                    continue
                walk(child, current_speaker)
        elif isinstance(node, list):
            for child in node:
                walk(child, speaker)

    walk(value)
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe audio/video with Aliyun Fun-ASR.")
    parser.add_argument("inputs", nargs="+", help="Local audio/video file(s) or public HTTP/HTTPS media URL(s)")
    parser.add_argument("--output-dir", help="Directory for the transcript text output. Defaults to the input file directory for local files.")
    parser.add_argument("--api-host", default=os.getenv("ASR_API_HOST", DEFAULT_HOST))
    parser.add_argument("--api-key", default=os.getenv("DASHSCOPE_API_KEY"))
    parser.add_argument("--model", default="fun-asr")
    parser.add_argument("--language-hints", default="zh,en", help="Comma-separated language hints, default: zh,en")
    parser.add_argument("--speaker-count", type=int, help="Optional diarization speaker-count hint, 2-100")
    parser.add_argument("--jobs", type=int, help="Maximum concurrent transcription jobs. Defaults to input count for multiple inputs, otherwise 1.")
    parser.add_argument("--poll-interval", type=float, default=10.0)
    parser.add_argument("--timeout", type=int, default=6 * 3600)
    return parser.parse_args()


def transcribe_one(args: argparse.Namespace, media: str) -> Path:
    with tempfile.TemporaryDirectory(prefix="asr-") as temp:
        temp_dir = Path(temp)
        if is_url(media):
            file_url = media
            output_dir = Path(args.output_dir or "asr-output").expanduser().resolve()
            original_name = Path(parse.urlparse(media).path).name
        else:
            local_path = Path(media).expanduser().resolve()
            if not local_path.exists():
                raise AsrError(f"input file not found: {local_path}")
            output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else local_path.parent
            original_name = local_path.name
            converted = prepare_local_audio(local_path, temp_dir)
            file_url = upload_temporary_file(args.api_key, args.model, converted)
        output_dir.mkdir(parents=True, exist_ok=True)

        submit = submit_task(args, file_url)
        task_id = submit.get("output", {}).get("task_id")
        if not task_id:
            raise AsrError(f"submit response did not include task_id: {json.dumps(submit, ensure_ascii=False)}")
        query = poll_task(args, task_id, original_name or media)
        final_json = download_json(result_url(query))

        stem = Path(original_name).stem or "transcription"
        lines = extract_text_lines(final_json)
        output_path = output_dir / f"{stem}.txt"
        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return output_path


def main() -> int:
    args = parse_args()
    if not args.api_key:
        raise AsrError("DASHSCOPE_API_KEY or --api-key is required")
    if args.speaker_count is not None and not 2 <= args.speaker_count <= 100:
        raise AsrError("--speaker-count must be between 2 and 100")
    if args.jobs is not None and args.jobs < 1:
        raise AsrError("--jobs must be at least 1")

    jobs = args.jobs if args.jobs is not None else max(1, len(args.inputs))
    if jobs == 1:
        failures = 0
        for media in args.inputs:
            try:
                print(transcribe_one(args, media))
            except Exception as exc:
                failures += 1
                print(f"{media}: error: {exc}", file=sys.stderr)
        return 1 if failures else 0

    failures = 0
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        future_to_input = {executor.submit(transcribe_one, args, media): media for media in args.inputs}
        for future in as_completed(future_to_input):
            media = future_to_input[future]
            try:
                print(future.result())
            except Exception as exc:
                failures += 1
                print(f"{media}: error: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"command failed: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except AsrError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
