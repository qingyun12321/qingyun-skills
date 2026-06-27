# Aliyun Fun-ASR Notes

Source pages:

- https://help.aliyun.com/zh/model-studio/get-temporary-file-url
- https://help.aliyun.com/zh/model-studio/non-realtime-speech-recognition-user-guide
- https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api
- https://help.aliyun.com/zh/model-studio/asr-model/#asr-audio-spec02

Core facts verified from the official docs:

- Non-realtime Fun-ASR uses async submit and poll.
- Beijing dedicated host endpoints:
  - Submit: `POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/asr/transcription`
  - Query: `GET https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/tasks/{task_id}`
- Dedicated hosts require a `parameters` object in the submit body, even when empty.
- Request headers include:
  - `Authorization: Bearer $DASHSCOPE_API_KEY`
  - `Content-Type: application/json`
- Submit requests include `X-DashScope-Async: enable`.
- Do not send `X-DashScope-Async` on task polling for the configured dedicated host; this host can return 403 with that header.
- When using DashScope temporary `oss://` URLs in HTTP model calls, also send `X-DashScope-OssResourceResolve: enable`.
- `input.file_urls` is required, supports HTTP/HTTPS, and a single request supports one URL.
- For local files, get a temporary upload policy from `GET https://dashscope.aliyuncs.com/api/v1/uploads?action=getPolicy&model=fun-asr`, upload to `data.upload_host` with the returned multipart fields, and pass `oss://{data.upload_dir}/{filename}` as the file URL.
- DashScope temporary URLs are valid for 48 hours and are automatically cleaned up by DashScope. Do not add cloud deletion cleanup to this skill.
- `output.results[].transcription_url` points to the downloadable JSON result and is valid for 24 hours.
- The helper script downloads that JSON only in memory and writes only `{original-input-stem}.txt`.
- For local files, the default output directory is the original input file's directory. For URL inputs, default to `./asr-output` unless `--output-dir` is set.
- Output filenames must be based on the user's original audio/video filename, not the intermediate mono WAV filename.
- The helper script accepts multiple inputs. With multiple inputs, default concurrency is the number of inputs; use `--jobs N` to cap or override concurrent transcriptions.
- Each input must use its own local temporary directory so cleanup for one transcription cannot delete another transcription's intermediate audio.
- Fun-ASR non-realtime models support speaker diarization; set `parameters.diarization_enabled` to `true`.
- Speaker diarization only applies to mono audio. For diarization, official docs recommend audio no longer than 2 hours.
- General non-realtime limits for Fun-ASR include up to 2 GB and up to 12 hours, but diarization has the stricter 2-hour recommendation.
- `speaker_count` is optional, only affects diarization, accepts integer 2 to 100, and is only a reference hint.
- Default `language_hints` for this skill is `["zh", "en"]`.
- Do not add emotion recognition or timestamp options by default for this skill.

Default payload shape:

```json
{
  "model": "fun-asr",
  "input": {
    "file_urls": ["https://example.com/audio.wav"]
  },
  "parameters": {
    "channel_id": [0],
    "diarization_enabled": true,
    "language_hints": ["zh", "en"]
  }
}
```

If the user gives a local video or audio file, convert it first:

```bash
ffmpeg -y -i input.mp4 -vn -ac 1 -ar 16000 output.wav
```

Then upload the converted file to a storage URL that Alibaba Cloud can access. Localhost URLs are not suitable unless the host is externally reachable.
