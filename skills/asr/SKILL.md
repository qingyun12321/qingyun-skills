---
name: asr
description: Transcribe audio or video files with Alibaba Cloud Model Studio non-realtime Fun-ASR. Use when Codex needs speech-to-text, meeting/interview/call transcription, speaker diarization, or subtitle/transcript extraction from local audio/video files or public HTTP/HTTPS media URLs.
---

# ASR

Use Alibaba Cloud Model Studio non-realtime Fun-ASR for speech transcription. Default to:

- Model: `fun-asr`
- API host: `llm-plmvo15iruk58svw.cn-beijing.maas.aliyuncs.com`
- Speaker diarization: enabled
- Emotion recognition: disabled / not requested
- Timestamp extras: not requested

## Quick Start

Use the helper script for normal work:

```bash
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py \
  /path/to/input.mp4
```

For multiple inputs, pass all files in one command and set `--jobs` when a specific concurrency limit is needed:

```bash
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py \
  /path/to/a.mp4 /path/to/b.wav /path/to/c.mov --jobs 3
```

Required environment:

- `DASHSCOPE_API_KEY`: Model Studio API key.
- `ffmpeg`: required for local files, especially video extraction and mono audio normalization.

For local input files, the script converts media to single-channel WAV in a temp directory because speaker diarization only supports mono audio. The script then uses the same `DASHSCOPE_API_KEY` to request a DashScope temporary upload policy, uploads the converted local file to the temporary storage returned by the API, and submits the resulting `oss://` URL. No separate OSS access key configuration is required.

If the input is already an HTTP/HTTPS URL, the script submits it directly.

## Workflow

1. Resolve input and output directory.
   - Accept one or more local file paths or public HTTP/HTTPS URLs.
   - Process multiple inputs concurrently by default.
   - Default concurrency is the number of inputs.
   - Use `--jobs N` to cap or override concurrent transcriptions.
   - Default output directory for local files is the original input file's directory.
   - For URL inputs, default output directory is `./asr-output` unless `--output-dir` is set.
   - Create the output directory if it does not exist.
2. For local files, run ffmpeg synchronously.
   - Extract audio from video inputs.
   - Normalize all local media to mono WAV for diarization.
   - Keep converted audio in a temporary directory only.
3. Make the audio available to the API.
   - For local files, upload the converted audio through DashScope's temporary-file URL API.
   - For HTTP/HTTPS URLs, submit the URL directly.
   - When submitting `oss://` temporary URLs over HTTP, include `X-DashScope-OssResourceResolve: enable`.
4. Submit the async Fun-ASR task and poll it.
   - Use `POST /api/v1/services/audio/asr/transcription`.
   - Use `GET /api/v1/tasks/{task_id}` until terminal status.
   - Keep `parameters` present for the dedicated host.
5. Save results.
   - Save only a plain text transcript.
   - Name the output from the original user input file stem, such as `meeting.mp4` -> `meeting.txt`.
   - Do not name the output after intermediate converted files such as `meeting.mono16k.wav`.
6. Cleanup.
   - Use an independent temporary directory for each input.
   - Remove temporary conversion files for each finished input.
   - Do not keep downloaded JSON task/result files.
   - Do not delete cloud temporary files; DashScope expires them automatically.
   - Do not leave background ffmpeg, HTTP server, or polling processes running.

## Script Options

Useful examples:

```bash
# Local video or audio file, output directory explicit
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py input.mov --output-dir out

# Local video or audio file, output next to input by default
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py /path/to/input.mov

# Multiple local files, concurrent by default
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py \
  /path/to/input-a.mov /path/to/input-b.wav

# Multiple local files, concurrency capped explicitly
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py \
  /path/to/input-a.mov /path/to/input-b.wav --jobs 2

# Public media URL, no local conversion or upload
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py \
  'https://example.com/audio.wav' --output-dir out

# Override expected language hints and speaker count
python /home/qingyun/qingyun-skills/skills/asr/scripts/transcribe.py input.wav \
  --output-dir out --language-hints zh,en --speaker-count 2
```

Default `language_hints` is `zh,en`. Do not enable emotion recognition or extra timestamp parameters unless the user explicitly asks and the selected model supports them. Speaker diarization may emit `speaker_id` fields in the JSON result.

## API Notes

Read `references/aliyun-fun-asr.md` when changing API payloads, host behavior, limits, or result parsing.
