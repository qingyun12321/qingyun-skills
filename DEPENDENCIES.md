# Skill dependency map

This file records the runtime relationship between the skills in this repository and their dependencies. It provides two indexes so the relationship can be searched in either direction.

## Scope

- `mise.toml` manages shared command-line tools and npm CLIs.
- `pyproject.toml` manages direct Python packages. `uv.lock` records their transitive dependencies.
- Python itself is not pinned in `mise.toml`. Skills use the system Python when available, or a Python installation and virtual environment managed by `uv`.
- `Core` means the normal skill path needs the dependency. `Optional` means only a specific format, platform, fallback, or integration needs it. Optional packages listed in the shared manifests are still installed by those managers.
- Skill-owned runtimes with their own lockfiles are documented separately rather than duplicated in the shared manifests.
- Dependencies used only to build OfficeCLI from source or run bundled OfficeCLI examples are excluded from the shared environment.

## Skill to dependency index

| Skill | Managed dependencies | External or host dependencies |
|---|---|---|
| `agentic-mermaid-diagram-workflow` | Core: `node`, `npm:agentic-mermaid`. Optional: `jq` for shell validation pipelines. | Optional hosted MCP: `https://agentic-mermaid.dev/mcp`. |
| `asr` | Core for local media: `ffmpeg`. | Python runtime, `curl`, `DASHSCOPE_API_KEY`, and DashScope network access. URL inputs do not need `ffmpeg`. |
| `baoyu-infographic` | None. | A host-provided raster image-generation capability or a separately configured image backend. The optional Codex CLI path requires an authenticated `codex` CLI and its image-generation wrapper. |
| `check` | Optional for GitHub work: `gh`. | Python runtime, `git`, `bash`, and the target project's own test toolchain. |
| `commit` | None. | `git`. |
| `eli5` | None. | A browser or host HTML artifact viewer. |
| `grilling` | None. | Host subagent capability for environment fact-finding. |
| `health` | None. | Python runtime, `git`, `bash`, and optional PowerShell on Windows. |
| `herdr` | None. | The host-provided `herdr` binary and `HERDR_ENV=1`. |
| `hunt` | None. | `git` and platform-specific diagnostic tools selected for the target problem. |
| `i-have-adhd` | None. | No fixed runtime dependency; it controls response style. |
| `json-canvas` | None. | Optional Obsidian application for opening `.canvas` files. |
| `kami` | Core Python: `weasyprint`, `pypdf`, `pymupdf`. Optional Python: `numpy`, `pygments`, `python-pptx`. Optional CLI: `node` for LaTeX formulas and Marp, `npm:@marp-team/marp-cli`, `pandoc`. | Python runtime. WeasyPrint native Cairo, Pango, and HarfBuzz libraries. Formula rendering requires the skill-owned MathJax runtime described below. Optional `rsvg-convert`, Poppler tools, fontconfig, LibreOffice, `curl`, and fonts. |
| `learn` | None. | The sibling `read` and `write` skills, host web search/fetch tools, and optional `curl` fallback. |
| `obsidian-bases` | None. | Obsidian application. Map views may also require the Obsidian Maps community plugin. |
| `obsidian-cli` | None. | A running Obsidian application with its `obsidian` CLI available. |
| `obsidian-markdown` | None. | Optional Obsidian application for rendering and validation. |
| `officecli` | Core: `node`, `npm:@officecli/officecli`, `jq`. Optional: `npm:@mermaid-js/mermaid-cli`, `playwright`. | Optional Chrome, Chromium, Edge, or Firefox browser. Network access may be needed for renderer assets. |
| `read` | Optional Python: `readability-lxml`, `html2text` for higher-quality local extraction; `requests`, `playwright`, `beautifulsoup4`, `lxml`, `pypdf` for specific input types. Optional CLI: `node`, `npm:@larksuite/cli`, `gh`. | Host web-fetch capability; Python runtime and `curl` for local scripts. Optional Chromium for Playwright, Poppler tools, Feishu credentials, and network access. The local extractor has a standard-library fallback. Proxy mode uses the `defuddle.md` and `r.jina.ai` HTTP services only with user opt-in; no Defuddle CLI is required. |
| `restoration` | None. | Python runtime and the host-provided `imagegen` capability. |
| `show-me` | None. | A browser and platform file opener for HTML output; a host Mermaid renderer for Mermaid output. |
| `think` | None. | No fixed runtime dependency. It uses the current project's files and available documentation tools. |
| `ui` | Optional: `node`, `npm:getdesign`. | The current project's frontend toolchain and optional host image-generation capability. |
| `unlimited-ocr` | Core: `uv`. | Python runtime managed or discovered by `uv`, `~/Unlimited-OCR`, the local model directory, NVIDIA GPU/CUDA, and WSL tools when Windows paths are used. |
| `update-changelog` | None. | `git`. |
| `uv` | Core: `uv`. | Network access to Python package indexes when resolving or installing packages. |
| `write` | Optional for GitHub release and public-reply modes: `gh`. | Python runtime, `bash`, and `git` for repository-grounded release writing. |

## Dependency to skill index

### Tools managed by mise

| Dependency | Skills | Relationship |
|---|---|---|
| `uv` | `unlimited-ocr`, `uv` | Direct runtime dependency. It also bootstraps the shared Python environment used by Python-based skills. |
| `node` | `agentic-mermaid-diagram-workflow`, `kami`, `officecli`, `read`, `ui` | Runtime for their npm CLIs and Kami's LaTeX-to-SVG renderer. Kami formulas require Node.js 20 or 22+ and the skill-owned MathJax runtime. Optional except where the selected path requires it. |
| `ffmpeg` | `asr` | Required for local audio and video inputs. |
| `gh` | `check`, `read`, `write` | GitHub PR, CI, release, issue, and repository-content integration. |
| `jq` | `agentic-mermaid-diagram-workflow`, `officecli` | Structured JSON filtering in documented shell workflows. |
| `pandoc` | `kami` | Optional HTML to DOCX conversion. |
| `npm:agentic-mermaid` | `agentic-mermaid-diagram-workflow` | Provides `am`, `agentic-mermaid`, and `agentic-mermaid-mcp`. |
| `npm:@larksuite/cli` | `read` | Optional Feishu/Lark user-login fallback. |
| `npm:@marp-team/marp-cli` | `kami` | Optional Marp and Markdown slide rendering. |
| `npm:@mermaid-js/mermaid-cli` | `officecli` | Optional `mmdc` backend for Mermaid image rendering. |
| `npm:@officecli/officecli` | `officecli` | Provides the core `officecli` command and downloads its platform binary. |
| `npm:getdesign` | `ui` | Optional brand preset retrieval after user approval. |

### Python packages managed by uv

| Dependency | Skills | Relationship |
|---|---|---|
| `beautifulsoup4` | `read` | Parses WeChat article HTML after browser rendering. |
| `html2text` | `read` | Optional higher-quality local extraction: converts extracted HTML into Markdown. |
| `lxml` | `read` | HTML parsing and cleanup for the WeChat and readability paths. |
| `numpy` | `kami` | Optional acceleration for PDF page-density analysis. |
| `playwright` | `read`, `officecli` | Browser automation for the WeChat fallback and optional OfficeCLI screenshots. A browser installation is still required. |
| `pygments` | `kami` | Optional syntax highlighting for code blocks. |
| `pymupdf` | `kami` | PDF rasterization, visual review, density checks, and font-use inspection. |
| `pypdf` | `kami`, `read` | PDF metadata and page checks in Kami, plus local PDF text extraction fallback in Read. |
| `python-pptx` | `kami` | Optional editable PPTX output. |
| `readability-lxml` | `read` | Optional higher-quality, privacy-preserving local main-content extraction. |
| `requests` | `read` | Feishu/Lark API helper. |
| `weasyprint` | `kami` | Core HTML to PDF renderer. |

### Skill-owned runtimes

| Dependency | Skills | Management and relationship |
|---|---|---|
| `@mathjax/src` | `kami` | Required when rendering LaTeX formulas. Pinned by `skills/kami/scripts/mathjax-runtime/package.json` and its `package-lock.json`; installed into the user cache by `bash skills/kami/scripts/ensure_mathjax.sh` using `npm ci`. Requires Node.js 20 or 22+. Do not add a global MathJax package to `mise.toml`: the renderer uses its own locked runtime. |

### Transitive Python packages

These are locked by `uv.lock`; they should not be added to `pyproject.toml` unless a skill starts importing them directly.

| Direct dependency | Transitive dependencies | Skills |
|---|---|---|
| `beautifulsoup4` | `soupsieve`, `typing-extensions` | `read` |
| `playwright` | `greenlet`, `pyee`, `typing-extensions` | `read`, `officecli` |
| `python-pptx` | `pillow`, `xlsxwriter`, `lxml`, `typing-extensions` | `kami` |
| `readability-lxml` | `chardet`, `cssselect`, `lxml-html-clean`, `lxml` | `read` |
| `requests` | `certifi`, `charset-normalizer`, `idna`, `urllib3` | `read` |
| `weasyprint` | `brotli`, `cffi`, `cssselect2`, `fonttools`, `pillow`, `pycparser`, `pydyf`, `pyphen`, `tinycss2`, `tinyhtml5`, `webencodings`, `zopfli` | `kami` |

### System and host dependencies not managed by this project

| Dependency | Skills | Reason it is not in `mise.toml` or `pyproject.toml` |
|---|---|---|
| Python runtime | All skills that run Python scripts | Supplied by the system or managed on demand by `uv`; it is intentionally not pinned as a separate mise tool. |
| `git` | `check`, `commit`, `health`, `hunt`, `kami`, `update-changelog`, `write` | Expected base development tool and often tied to host credentials. |
| `bash` and coreutils | `check`, `health`, `kami`, `read`, `write` | Base shell environment rather than a project package. |
| `curl` | `asr`, `kami`, `learn`, `officecli`, `read` | Base network utility; some uses are optional or installation-only. |
| Poppler tools | `kami`, `read` | Optional `pdffonts` and `pdftotext` capabilities installed at the OS level. |
| Cairo, Pango, HarfBuzz | `kami` | Native WeasyPrint libraries installed by the operating system. |
| `rsvg-convert` | `kami` | Optional librsvg system tool for SVG to PNG conversion before DOCX export. |
| Chromium or another supported browser | `officecli`, `read` | Browser binary and data are installed separately from the Python Playwright package. |
| Obsidian | `json-canvas`, `obsidian-bases`, `obsidian-cli`, `obsidian-markdown` | Desktop host application. |
| Herdr | `herdr` | Host terminal multiplexer with its own session environment. |
| DashScope API and credentials | `asr` | External service configured with `DASHSCOPE_API_KEY`. |
| Raster image generation | `restoration`, `baoyu-infographic` | `restoration` requires the host's `imagegen` capability. `baoyu-infographic` uses an available host image tool or a separately configured backend; its optional Codex CLI route also needs authentication and a wrapper. |
| Browser / HTML artifact viewer and file opener | `eli5`, `show-me` | Host capability for viewing generated HTML, not a Python or npm dependency. |
| Mermaid renderer | `show-me` | Host capability for displaying Mermaid output; no specific CLI is prescribed. |
| Subagent capability | `grilling` | Supplied by the agent host for environment fact-finding. |
| Unlimited-OCR repository, model, CUDA, and GPU | `unlimited-ocr` | Dedicated external ML environment that owns its own dependencies. |

## Maintenance rule

When a skill adds or removes a dependency:

1. Update the appropriate manager file: `mise.toml` for shared tools and npm CLIs, or `pyproject.toml` for directly used Python packages. Keep skill-owned locked runtimes under their own manager and document them separately.
2. Update both indexes in this file.
3. Run `uv lock --check`, `uv sync --locked`, and a TOML parse check for `mise.toml`.
4. Keep host capabilities and target-project toolchains out of the shared environment unless they become a normal runtime requirement for this repository.
