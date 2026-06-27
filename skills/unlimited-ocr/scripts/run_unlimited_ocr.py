#!/usr/bin/env python3
"""Run local Baidu Unlimited-OCR on a PDF, image, or image directory."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def wsl_or_local_path(raw: str) -> Path:
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        converted = subprocess.check_output(["wslpath", "-u", raw], text=True).strip()
        return Path(converted).expanduser().resolve(strict=False)
    return Path(os.path.expandvars(raw)).expanduser().resolve(strict=False)


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-")
    return stem or "ocr"


def default_run_dir(repo: Path, input_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return repo / "outputs" / "skill_ocr" / f"{safe_stem(input_path)}-{stamp}"


def default_combined_md(input_path: Path, input_kind: str) -> Path:
    if input_kind == "image_dir":
        name = input_path.name or safe_stem(input_path)
        return input_path.parent / f"{name}.md"
    return input_path.with_suffix(".md")


def detect_input(path: Path) -> str:
    if path.is_dir():
        return "image_dir"
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_EXTS:
        return "single_image"
    raise SystemExit(f"Unsupported input type: {path}")


def link_or_copy(src: Path, dst: Path) -> None:
    try:
        dst.symlink_to(src)
    except OSError:
        shutil.copy2(src, dst)


def require_path(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def matching_processes(repo: Path, model_dir: Path) -> dict[int, str]:
    try:
        output = subprocess.check_output(
            ["ps", "-eo", "pid=,args="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return {}

    current_pid = os.getpid()
    matches: dict[int, str] = {}
    repo_text = str(repo)
    model_text = str(model_dir)
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_text, _, command = line.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == current_pid:
            continue
        if (
            "sglang.launch_server" in command
            or ("infer.py" in command and (repo_text in command or model_text in command))
            or ("monitor_infer.py" in command and repo_text in command)
        ):
            matches[pid] = command
    return matches


def check_safe_exit(repo: Path, model_dir: Path, before: dict[int, str]) -> int:
    after = matching_processes(repo, model_dir)
    residual = {pid: command for pid, command in after.items() if pid not in before}
    if not residual:
        print("Safe exit check: no new Unlimited-OCR/SGLang processes remain")
        return 0

    print("Safe exit check: residual Unlimited-OCR/SGLang processes detected")
    for pid, command in sorted(residual.items()):
        print(f"  PID {pid}: {command}")
    return 2


def build_readable_markdown(output_dir: Path, combined_md: Path) -> int:
    script = Path(__file__).with_name("build_readable_markdown.py")
    completed = subprocess.run(
        [
            "python",
            str(script),
            str(output_dir),
            "--output",
            str(combined_md),
        ]
    )
    return completed.returncode


def build_infer_command(
    repo: Path,
    model_dir: Path,
    input_kind: str,
    input_path: Path,
    output_dir: Path,
    server_log: Path,
    args: argparse.Namespace,
) -> list[str]:
    image_mode = args.image_mode
    if image_mode == "auto":
        image_mode = "base" if input_kind == "pdf" else "gundam"

    cmd = [
        "uv",
        "run",
        "python",
        "infer.py",
        "--output_dir",
        str(output_dir),
        "--concurrency",
        str(args.concurrency),
        "--image_mode",
        image_mode,
        "--attention_backend",
        args.attention_backend,
        "--model_dir",
        str(model_dir),
        "--gpu",
        args.gpu,
        "--server_log",
        str(server_log),
    ]

    if input_kind == "pdf":
        cmd.extend(["--pdf", str(input_path)])
    else:
        cmd.extend(["--image_dir", str(input_path)])

    return cmd


def run(args: argparse.Namespace) -> int:
    if shutil.which("uv") is None:
        raise SystemExit("uv not found on PATH")

    repo = wsl_or_local_path(args.repo)
    model_dir = wsl_or_local_path(args.model_dir)
    input_path = wsl_or_local_path(args.input)

    require_path(repo / "infer.py", "Unlimited-OCR infer.py")
    require_path(model_dir, "Unlimited-OCR model directory")
    require_path(input_path, "Input path")

    input_kind = detect_input(input_path)
    run_dir = wsl_or_local_path(args.run_dir) if args.run_dir else default_run_dir(repo, input_path)
    output_dir = wsl_or_local_path(args.output_dir) if args.output_dir else run_dir / "pages"
    log_dir = run_dir / "_run"
    combined_md = (
        wsl_or_local_path(args.combined_md)
        if args.combined_md
        else default_combined_md(input_path, input_kind)
    )

    server_log = log_dir / "sglang_server.log"
    infer_log = log_dir / "infer_run.log"
    metrics = log_dir / "metrics.json"

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    infer_input = input_path
    infer_kind = input_kind
    if input_kind == "single_image":
        temp_dir = tempfile.TemporaryDirectory(prefix="unlimited_ocr_image_")
        temp_input = Path(temp_dir.name) / input_path.name
        link_or_copy(input_path, temp_input)
        infer_input = Path(temp_dir.name)
        infer_kind = "image_dir"

    try:
        infer_cmd = build_infer_command(
            repo=repo,
            model_dir=model_dir,
            input_kind=infer_kind,
            input_path=infer_input,
            output_dir=output_dir,
            server_log=server_log,
            args=args,
        )

        monitor_script = repo / "scripts" / "monitor_infer.py"
        if args.monitor:
            require_path(monitor_script, "Unlimited-OCR monitor script")
            cmd = [
                "uv",
                "run",
                "python",
                str(monitor_script),
                "--metrics",
                str(metrics),
                "--log",
                str(infer_log),
                "--interval",
                str(args.interval),
                "--",
                *infer_cmd,
            ]
        else:
            cmd = infer_cmd

        print("Repository:", repo)
        print("Model:", model_dir)
        print("Input:", input_path)
        print("Output Markdown:", output_dir)
        print("Readable Markdown:", combined_md)
        print("Run logs:", log_dir)
        print("Command:", " ".join(cmd))

        if args.dry_run:
            return 0

        log_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        before_processes = matching_processes(repo, model_dir)
        completed = subprocess.run(cmd, cwd=repo)
        safe_exit_code = 0 if args.skip_exit_check else check_safe_exit(repo, model_dir, before_processes)
        if completed.returncode != 0:
            return completed.returncode
        combine_code = build_readable_markdown(output_dir, combined_md)
        if combine_code != 0:
            return combine_code
        return safe_exit_code
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="PDF, image file, image directory, or WSL-convertible Windows path")
    parser.add_argument("--repo", default="~/Unlimited-OCR", help="Unlimited-OCR checkout")
    parser.add_argument("--model-dir", default="~/models/baidu/Unlimited-OCR", help="Local model directory")
    parser.add_argument("--output-dir", default="", help="Directory for generated Markdown files")
    parser.add_argument("--run-dir", default="", help="Directory for logs and metrics")
    parser.add_argument("--combined-md", default="", help="Path for the combined final Markdown")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--image-mode", choices=("auto", "base", "gundam"), default="auto")
    parser.add_argument("--attention-backend", default="flashinfer")
    parser.add_argument("--interval", type=float, default=0.5, help="Monitor sampling interval in seconds")
    parser.add_argument("--monitor", action="store_true", help="Enable monitor_infer.py metrics collection")
    parser.add_argument("--skip-exit-check", action="store_true", help="Do not check for new residual OCR processes")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without running OCR")
    return parser.parse_args()


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
