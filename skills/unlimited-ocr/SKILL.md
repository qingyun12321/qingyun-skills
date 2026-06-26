---
name: unlimited-ocr
description: Use local Baidu Unlimited-OCR to OCR user-specified PDFs, single images, or image directories into Markdown files. Use when Codex is asked to run OCR with Unlimited-OCR, Baidu Unlimited-OCR, local GPU OCR, document parsing, PDF OCR, image OCR, or when high-quality OCR/layout extraction is needed from local PDF or raster image files.
---

# Unlimited-OCR

Run the local Baidu Unlimited-OCR checkout for PDF or image OCR. Default paths are:

- Repo: `~/Unlimited-OCR`
- Model: `~/models/baidu/Unlimited-OCR`

## Workflow

1. Resolve the user input path. Accept PDFs, one image, or an image directory. For Windows paths inside WSL, convert paths such as `D:\file.pdf` with `wslpath -u`.
2. Check that the repo and model directories exist. If unspecified, use the defaults above.
3. Prefer the bundled wrapper:
   ```bash
   python <this-skill>/scripts/run_unlimited_ocr.py <input-path>
   ```
4. For PDFs, use `--image-mode base`. For image files or image directories, use `--image-mode gundam`. The wrapper chooses this automatically with `--image-mode auto`.
5. Use `--attention-backend flashinfer` by default on the local RTX 5070 Ti/Blackwell setup. The older `fa3` backend failed locally with `FlashAttention v3 Backend requires SM>=80 and SM<=90`.
6. Keep `--concurrency 1` unless intentionally testing memory headroom. A previous 31-page PDF run peaked at about `15760 MiB` on a `16303 MiB` GPU.
7. Do not enable monitoring by default. Run `infer.py` directly unless the user explicitly asks for monitoring, metrics, GPU memory tracking, system memory tracking, or elapsed-time monitoring.
8. When monitoring is explicitly requested, pass `--monitor`; it records elapsed time, process RAM, system RAM, and NVIDIA GPU memory/utilization through `~/Unlimited-OCR/scripts/monitor_infer.py`.
9. Keep the wrapper's default safe-exit check enabled. It snapshots matching Unlimited-OCR/SGLang processes before the run and reports any new related process that remains afterward. Use `--skip-exit-check` only when the user explicitly wants to bypass this.
10. Report the Markdown output directory, server log path, and safe-exit result. Report metrics and monitor log paths only when monitoring was enabled. Do not claim native PDF/DOCX/HTML/JSON export unless a post-processor was actually written.

## Wrapper Usage

```bash
python <this-skill>/scripts/run_unlimited_ocr.py <pdf-or-image-or-image-dir>
```

Common options:

```bash
python <this-skill>/scripts/run_unlimited_ocr.py <input> \
  --repo ~/Unlimited-OCR \
  --model-dir ~/models/baidu/Unlimited-OCR \
  --output-dir ~/Unlimited-OCR/outputs/my_ocr/pages \
  --concurrency 1 \
  --gpu 0 \
  --attention-backend flashinfer
```

Use `--dry-run` to print the command without executing it.

Use `--monitor` only when the user explicitly requests resource metrics:

```bash
python <this-skill>/scripts/run_unlimited_ocr.py <input> --monitor
```

The wrapper checks for new residual Unlimited-OCR/SGLang processes after the run by default. If any remain, it prints their PIDs and exits nonzero when OCR itself succeeded.

## Outputs

The local SGLang `infer.py` writes Markdown:

- PDF input: one `<pdf_stem>_page_0001.md` file per page.
- Image directory input: one `.md` file per image.
- Single image input through the wrapper: one `.md` file for that image.

The content is model output with Markdown-like text and detection tags such as:

```text
<|det|>title [116, 54, 475, 83]<|/det|>Document title
```

For structured JSON, HTML, plain text cleanup, or one combined Markdown file, implement a separate post-processing step over the generated `.md` files.

## Direct Command Pattern

When not using the wrapper, run from the Unlimited-OCR repo:

```bash
cd ~/Unlimited-OCR
uv run python infer.py \
  --pdf <input.pdf> \
  --output_dir <output-pages-dir> \
  --concurrency 1 \
  --image_mode base \
  --attention_backend flashinfer \
  --model_dir ~/models/baidu/Unlimited-OCR \
  --gpu 0 \
  --server_log <run-dir>/sglang_server.log
```

For image directories, replace `--pdf <input.pdf>` with `--image_dir <image-dir>` and use `--image_mode gundam`.
