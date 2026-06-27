---
name: unlimited-ocr
description: Use local Baidu Unlimited-OCR to OCR user-specified PDFs, single images, or image directories, then consolidate and correct the OCR pages into a polished human-readable Markdown file with renderable math formulas, code blocks, tables, and preserved document content. Use when Codex is asked to run OCR with Unlimited-OCR, Baidu Unlimited-OCR, local GPU OCR, document parsing, PDF OCR, image OCR, or when high-quality OCR/layout extraction and readable Markdown reconstruction are needed from local PDF or raster image files.
---

# Unlimited-OCR

Run the local Baidu Unlimited-OCR checkout for PDF or image OCR, then produce one corrected Markdown file suitable for human reading. Default paths are:

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
10. After OCR succeeds, create the combined Markdown from the page outputs next to the original input with the same filename and a `.md` extension. For `/path/name.pdf` or `/path/name.png`, write `/path/name.md`. For an image directory `/path/images`, write `/path/images.md`. The wrapper does this automatically unless `--combined-md` is provided.
11. Treat the wrapper-generated Markdown as the file to polish. Review and correct that same file into the final human-readable Markdown before finishing.
12. Report the page Markdown output directory, final Markdown path, server log path, and safe-exit result. Report metrics and monitor log paths only when monitoring was enabled. Do not claim native PDF/DOCX/HTML/JSON export unless a post-processor was actually written.

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

Use `--combined-md` only to override the default final Markdown location beside the source file.

Use `--dry-run` to print the command without executing it.

Use `--monitor` only when the user explicitly requests resource metrics:

```bash
python <this-skill>/scripts/run_unlimited_ocr.py <input> --monitor
```

The wrapper checks for new residual Unlimited-OCR/SGLang processes after the run by default. If any remain, it prints their PIDs and exits nonzero when OCR itself succeeded.

## Post-OCR Markdown Reconstruction

Always deliver a polished final Markdown file beside the original input, not only the raw page files.

1. Start from the wrapper-generated Markdown file at the source-adjacent path, such as `/path/name.md`. It removes common Unlimited-OCR detection tags, keeps page order, inserts page boundary comments, and adds closing code fences when a page has an unmatched fence.
2. Make corrections in that same Markdown file so the final result stays next to the original input with the same filename. Use the raw page files in `<run-dir>/pages` for traceability.
3. Correct OCR details conservatively:
   - Preserve all substantive text, headings, captions, tables, equations, code, footnotes, references, and list items unless they are clear OCR artifacts.
   - Fix obvious OCR substitutions, broken line wraps, hyphenation across line breaks, duplicated headers/footers, and page-break interruptions.
   - Keep original ordering. If a paragraph, formula, or code block spans pages, merge it into one coherent block.
4. Make math render in Markdown:
   - Use inline math as `$...$` and display math as `$$...$$`.
   - Do not place formulas inside backticks or code fences unless the source is literally code.
   - Preserve equation numbering, alignment cues, subscripts, superscripts, Greek letters, matrices, and multi-line derivations when present.
5. Make code render as code:
   - Use fenced code blocks with a language tag when it is obvious, such as `python`, `bash`, `json`, `sql`, `cpp`, or `text`.
   - Do not "correct" code semantically. Only repair OCR damage that is clear from context, such as missing indentation, confused quotes, or `l`/`1`/`I` substitutions.
6. Rebuild tables as Markdown tables when practical. For wide or complex tables where Markdown would lose structure, use HTML tables or fenced text blocks and keep all cell content.
7. If confidence is low for a formula, table, code block, or dense paragraph, inspect the corresponding source page image/PDF region or raw page Markdown before editing. Mark unresolved uncertainty with a short `<!-- OCR uncertain: ... -->` comment rather than silently dropping content.
8. Before reporting completion, scan the final Markdown for leftover detection tags, unbalanced code fences, broken math delimiters, empty pages, and suspiciously short sections.

## Outputs

The local SGLang `infer.py` writes raw page Markdown:

- PDF input: one `<pdf_stem>_page_0001.md` file per page.
- Image directory input: one `.md` file per image.
- Single image input through the wrapper: one `.md` file for that image.

The page content is model output with Markdown-like text and detection tags such as:

```text
<|det|>title [116, 54, 475, 83]<|/det|>Document title
```

The wrapper also writes the combined Markdown next to the original input with the same filename and a `.md` extension. The final deliverable should remain at that path after applying the reconstruction checklist above.

For structured JSON, HTML, plain text cleanup, PDF, DOCX, or other exports, implement a separate post-processing step over the corrected Markdown file.

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

After a direct run, build the readable draft:

```bash
python <this-skill>/scripts/build_readable_markdown.py <output-pages-dir> \
  --output <input-dir>/<input-stem>.md
```
