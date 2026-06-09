# izuna-video-lab

Python FastAPI backend MVP for manually pasted video transcripts. V1 cleans transcript text, splits it into chunks, and returns both the cleaned transcript and chunk metadata.

V1.1 adds deterministic mock summarization. It does not call an external LLM API, OpenAI API, YouTube, or Whisper.

V1.3 adds local JSON storage and deterministic keyword-based Q&A from saved transcript chunks.

V1.4 adds Markdown export for saved processed videos.

V1.5 replaces the generic mock summary with an improved deterministic rule-based summary. It is still not LLM summarization; it only uses the cleaned transcript and chunks.

V2.0 adds optional OpenAI-powered LLM summarization behind environment config. The default remains `rule_based`, and missing or failing OpenAI config falls back to the rule-based summarizer.

V2.1 adds response metadata so smoke tests can confirm whether a summary came from OpenAI or the rule-based fallback.

V2.1.1 loads local development config from a project-root `.env` file while still allowing environment variables to override `.env` values.

V2.1.2 adds safe OpenAI debug visibility with `GET /api/config` and a minimal `GET /api/llm/openai/smoke-test` endpoint. These endpoints never return the API key.

V2.2 adds optional Ollama-powered local LLM summarization using the local Ollama chat API. The default remains `rule_based`, and Ollama failures fall back to the rule-based summarizer.

V2.3 adds a YouTube caption fetcher endpoint for videos with available subtitles/captions. It does not download audio or transcribe speech.

V2.4 adds an optional local speech-to-text fallback with `yt-dlp` and `faster-whisper`. Captions are still tried first, and STT runs only when explicitly enabled.

## Project Structure

```text
backend/
  app/
    __init__.py
    config.py
    main.py
    schemas.py
    services/
      __init__.py
      llm_summarizer.py
      markdown_exporter.py
      ollama_summarizer.py
      qa_engine.py
      summarizer.py
      transcript_cleaner.py
      transcript_chunker.py
      youtube_audio_downloader.py
      youtube_caption_fetcher.py
      youtube_utils.py
    storage/
      __init__.py
      video_store.py
  data/
    videos.json
requirements.txt
README.md
```

## Local JSON Storage

Processed videos are saved locally to:

```text
backend/data/videos.json
```

The storage layer creates `backend/data` and `videos.json` automatically if they are missing. JSON is written with UTF-8 encoding and `ensure_ascii=False`, so Thai transcript text is preserved.

Stored video records include:

```json
{
  "video_id": "string",
  "title": "string",
  "source_url": "string or null",
  "language": "thai or english",
  "cleaned_transcript": "string",
  "chunks": [],
  "summary": {},
  "created_at": "ISO datetime string"
}
```

## Rule-based Summary

The summary returned by `POST /api/videos/process` is deterministic and based only on transcript text. It does not call OpenAI, an external LLM API, embeddings, or a vector database.

For Thai videos, generated summary content uses Thai wording for:

- TL;DR
- Main ideas
- Key takeaways
- Action items
- Questions to think

For English videos, generated summary content uses natural English wording.

## Optional LLM Summarization

Default mode is rule-based:

```text
SUMMARY_PROVIDER=rule_based
```

Supported providers:

- `rule_based`
- `openai`
- `ollama`

To configure optional LLM summarization, create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
OPENAI_API_KEY=your_real_api_key
OPENAI_MODEL=your_model
SUMMARY_PROVIDER=openai
```

For local Ollama summarization:

```text
SUMMARY_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

Do not commit `.env` or real secrets. The repository includes `.env.example` only.

Behavior:

- `SUMMARY_PROVIDER=rule_based` always uses the deterministic local summarizer.
- `SUMMARY_PROVIDER=openai` uses OpenAI only when both `OPENAI_API_KEY` and `OPENAI_MODEL` are set.
- `SUMMARY_PROVIDER=ollama` uses local Ollama only when both `OLLAMA_BASE_URL` and `OLLAMA_MODEL` are set.
- If OpenAI config is missing or the API request fails, `POST /api/videos/process` falls back to the rule-based summarizer instead of crashing.
- If Ollama config is missing or the local API request fails, `POST /api/videos/process` falls back to the rule-based summarizer instead of crashing.
- OpenAI summarization is grounded in the cleaned transcript and asks the model to return the existing summary JSON structure.
- Ollama summarization uses `POST {OLLAMA_BASE_URL}/api/chat` with `stream=false` and asks the local model to return the same summary JSON structure.

`POST /api/videos/process` includes provider metadata:

```json
{
  "summary_provider": "rule_based",
  "summary_fallback_used": false
}
```

## Local .env Configuration

From the project root, create a local `.env` file:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
SUMMARY_PROVIDER=openai
OPENAI_API_KEY=your_real_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Run the API:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Check config visibility:

```text
GET /api/config
```

The response never returns the API key:

```json
{
  "summary_provider": "openai",
  "openai_model": "gpt-4.1-mini",
  "openai_api_key_present": true,
  "openai_model_present": true,
  "openai_config_valid": true,
  "ollama_base_url": "http://localhost:11434",
  "ollama_model": "qwen2.5:3b",
  "ollama_base_url_present": true,
  "ollama_model_present": true,
  "ollama_config_valid": true,
  "enable_local_stt": false,
  "stt_provider": "faster_whisper",
  "stt_model_size": "base",
  "stt_device": "cpu",
  "stt_compute_type": "int8",
  "stt_audio_dir": "backend/data/audio",
  "stt_max_duration_seconds": 900,
  "env_file_exists": true,
  "env_file_path": "D:\\Codex\\izuna-video-lab\\.env"
}
```

Then test:

```text
POST /api/videos/process
```

Expected OpenAI success:

```json
{
  "summary_provider": "openai",
  "summary_fallback_used": false
}
```

Expected fallback:

```json
{
  "summary_provider": "rule_based",
  "summary_fallback_used": true
}
```

Environment variables still override `.env` values. Do not commit `.env`, `.env.local`, or real API keys.

## Local Ollama Summarization

Make sure Ollama is running locally and the model exists:

```powershell
ollama pull qwen2.5:3b
```

Configure `.env`:

```text
SUMMARY_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

Run the API:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Check safe config metadata:

```text
GET /api/config
```

Run the Ollama smoke test:

```text
GET /api/llm/ollama/smoke-test
```

Then call:

```text
POST /api/videos/process
```

Expected Ollama success:

```json
{
  "summary_provider": "ollama",
  "summary_fallback_used": false
}
```

Expected fallback:

```json
{
  "summary_provider": "rule_based",
  "summary_fallback_used": true
}
```

If `/api/config` is valid but `/api/llm/ollama/smoke-test` fails, check that Ollama is running at `OLLAMA_BASE_URL` and that `OLLAMA_MODEL` is installed.

## V2.3 YouTube Caption Fetcher

`POST /api/videos/process-youtube` lets you process a YouTube URL when captions or subtitles are available.

Important limits:

- This only works when YouTube captions/subtitles are available.
- It does not download audio.
- It does not transcribe speech.
- If captions are missing, disabled, blocked, or unavailable for the requested language, use manual transcript mode with `POST /api/videos/process`.

Example request:

```json
{
  "source_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "thai",
  "title": "Optional title"
}
```

The response uses the same shape as `POST /api/videos/process` and adds:

```json
{
  "transcript_source": "youtube_caption",
  "youtube_video_id": "VIDEO_ID",
  "transcript_language": "th",
  "transcript_is_generated": false
}
```

If captions are unavailable, the endpoint returns a readable failure:

```json
{
  "ok": false,
  "reason": "transcript_not_found",
  "message": "ไม่พบ subtitle/caption สำหรับวิดีโอนี้ กรุณาวาง transcript เองผ่าน /api/videos/process",
  "source_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

## V2.4 Local Speech-to-Text Fallback

Local STT is optional. `POST /api/videos/process-youtube` always tries YouTube captions first. It only downloads audio and runs local speech-to-text when:

- request body has `use_stt_fallback: true`
- `.env` has `ENABLE_LOCAL_STT=true`

Use this only for videos you own or are permitted to process.

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Install `ffmpeg` separately on the machine. `yt-dlp` needs it for audio extraction. The first `faster-whisper` run may download a Whisper model.

Example `.env`:

```text
ENABLE_LOCAL_STT=true
STT_PROVIDER=faster_whisper
STT_MODEL_SIZE=base
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
STT_AUDIO_DIR=backend/data/audio
STT_MAX_DURATION_SECONDS=900
```

Check safe config:

```text
GET /api/config
```

Check STT readiness without downloading YouTube audio or loading a model:

```text
GET /api/stt/smoke-test
```

Example request:

```json
{
  "source_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "thai",
  "title": "YouTube STT Test",
  "use_stt_fallback": true
}
```

If captions are missing and local STT is disabled, the endpoint returns:

```json
{
  "ok": false,
  "reason": "local_stt_disabled",
  "message": "ไม่พบ subtitle/caption และ local STT ยังไม่ได้เปิดใช้งาน",
  "source_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

## Debugging OpenAI Integration

Create local config from the project root:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```text
SUMMARY_PROVIDER=openai
OPENAI_API_KEY=your_real_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Run the API:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Check safe config metadata:

```text
GET /api/config
```

Run the minimal OpenAI smoke test:

```text
GET /api/llm/openai/smoke-test
```

This endpoint sends a tiny request asking OpenAI to return `{"ok": true, "message": "pong"}`. It may incur a small API usage charge. It never returns `OPENAI_API_KEY`.

Interpretation:

- `GET /api/config` has `openai_config_valid = false`: `.env` or environment variables are missing `OPENAI_API_KEY` or `OPENAI_MODEL`.
- `GET /api/config` has `openai_config_valid = true`, but smoke test returns `ok = false` with `stage = "openai_call"`: the model name, key permissions, quota, network, or OpenAI call is failing.
- Smoke test returns `ok = true`, but `POST /api/videos/process` falls back to `summary_provider = "rule_based"` and `summary_fallback_used = true`: the OpenAI summary call likely failed during summary generation or JSON parsing. Check the terminal logs for the safe fallback reason.

Then test normal processing:

```text
POST /api/videos/process
```

Expected OpenAI success:

```json
{
  "summary_provider": "openai",
  "summary_fallback_used": false
}
```

Expected fallback:

```json
{
  "summary_provider": "rule_based",
  "summary_fallback_used": true
}
```

## V2.1 OpenAI Smoke Test

Use environment variables only. Do not commit `.env` files or API keys.

Rule-based mode:

```powershell
cd backend
$env:SUMMARY_PROVIDER="rule_based"
python -m uvicorn app.main:app --reload
```

OpenAI mode:

```powershell
cd backend
$env:SUMMARY_PROVIDER="openai"
$env:OPENAI_API_KEY="your_real_api_key_here"
$env:OPENAI_MODEL="gpt-5.4-mini"
python -m uvicorn app.main:app --reload
```

If `OPENAI_MODEL` is unavailable for your account, use another available OpenAI model from your dashboard.

Then call `POST /api/videos/process` and check:

- `summary_provider = "openai"` and `summary_fallback_used = false` means OpenAI generated the summary.
- `summary_provider = "rule_based"` and `summary_fallback_used = false` means rule-based mode was used directly.
- `summary_provider = "rule_based"` and `summary_fallback_used = true` means OpenAI was requested but config was missing or the API call failed.

## Setup on Windows PowerShell

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, allow scripts for the current user:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Run the API

```powershell
uvicorn app.main:app --reload --app-dir backend
```

Open the health endpoint:

```powershell
curl.exe http://127.0.0.1:8000/
```

## Testing

From the project root:

```powershell
cd backend
python -m pytest
```

The regression tests cover:

- Transcript cleaning
- Transcript chunking
- Thai rule-based summarization
- Full API processing pipeline
- Q&A from saved chunks
- Markdown export
- Optional LLM config fallback behavior
- Summary provider smoke-test metadata
- Safe OpenAI config and smoke-test debug endpoints
- YouTube URL parsing and mocked YouTube caption processing
- Local STT fallback config and mocked STT processing

## Test Transcript Processing

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/videos/process" `
  -H "Content-Type: application/json" `
  -d "{\"title\":\"Sample video\",\"source_url\":null,\"language\":\"english\",\"transcript\":\"[00:01] Hello everyone. 00:01:23 This is a test transcript. It should be cleaned and chunked.\"}"
```

## Test in Swagger UI

1. Start the server:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

2. Open Swagger UI in your browser:

```text
http://127.0.0.1:8000/docs
```

3. Expand `POST /api/videos/process`.
4. Click `Try it out`.
5. Paste this request body:

```json
{
  "title": "Sample video",
  "source_url": null,
  "language": "english",
  "transcript": "[00:01] Hello everyone. 00:01:23 This is a test transcript. It should be cleaned, chunked, and summarized with the mock V1.1 summarizer."
}
```

6. Click `Execute`.

Expected response shape:

```json
{
  "video_id": "9df6f76e-95ae-468b-a3f6-7d9482f89e70",
  "title": "Sample video",
  "source_url": null,
  "language": "english",
  "cleaned_transcript": "Hello everyone. This is a test transcript. It should be cleaned, chunked, and summarized with the mock V1.1 summarizer.",
  "chunks": [
    {
      "chunk_index": 1,
      "text": "Hello everyone. This is a test transcript. It should be cleaned, chunked, and summarized with the mock V1.1 summarizer.",
      "char_count": 119
    }
  ],
  "summary": {
    "tldr": "Hello everyone. This is a test transcript. It should be cleaned, chunked, and summarized with the mock V1.1 summarizer.",
    "main_ideas": [
      "Chunk 1: Hello everyone. This is a test transcript. It should be cleaned, chunked, and summarized with the mock V1.1 summarizer."
    ],
    "key_takeaways": [
      "The transcript covers a topic across 1 processed chunk(s).",
      "The cleaned text is ready for manual review or a future LLM summarization step.",
      "The opening context is: Hello everyone. This is a test transcript. It should be cleaned, chunked, and summarized with the mock V1.1 summarizer."
    ],
    "action_items": [
      "Review the generated chunks and refine any transcript sections that need more context.",
      "Use the main ideas as a starting point before replacing this mock summary with an LLM-backed summary."
    ],
    "questions_to_think": [
      "Which parts of the transcript are most important for the target audience?",
      "What follow-up topics or decisions should be explored after reading this transcript?"
    ]
  }
}
```

## List Saved Videos

```powershell
curl.exe http://127.0.0.1:8000/api/videos
```

Expected response shape:

```json
[
  {
    "video_id": "9df6f76e-95ae-468b-a3f6-7d9482f89e70",
    "title": "Sample video",
    "source_url": null,
    "language": "english",
    "created_at": "2026-06-08T08:00:00+00:00"
  }
]
```

This endpoint returns metadata only. It does not return full transcripts, chunks, or summaries.

## Ask a Question From Saved Chunks

Replace `<video_id>` with the ID returned by `POST /api/videos/process`:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/videos/<video_id>/ask" `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"วิดีโอนี้พูดถึง deep work ยังไง\"}"
```

Expected response shape:

```json
{
  "video_id": "9df6f76e-95ae-468b-a3f6-7d9482f89e70",
  "question": "วิดีโอนี้พูดถึง deep work ยังไง",
  "answer": "This is a simple keyword-based answer from the saved chunks...",
  "related_chunks": [
    {
      "chunk_index": 1,
      "text": "string",
      "char_count": 123,
      "score": 2
    }
  ]
}
```

The Q&A engine is deterministic and keyword-based. It does not use embeddings, vector search, OpenAI, or any external LLM API.

## Export Markdown

Replace `<video_id>` with an ID returned by `POST /api/videos/process` or `GET /api/videos`:

```powershell
curl.exe "http://127.0.0.1:8000/api/videos/<video_id>/export/markdown"
```

The endpoint returns `text/markdown` and includes:

- Title
- Source URL
- Language
- Created at
- TL;DR
- Main ideas
- Key takeaways
- Action items
- Questions to think
- Transcript chunks

You can also test it directly in a browser:

```text
http://127.0.0.1:8000/api/videos/<video_id>/export/markdown
```

To use the output in Obsidian or Notion:

- Obsidian: copy the Markdown response and paste it into a new `.md` note.
- Notion: copy the Markdown response and paste it into a Notion page; Notion will convert headings and bullet lists.

## Swagger UI V1.3 Test Flow

1. Start the server:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

2. Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

3. Expand `POST /api/videos/process`, click `Try it out`, and submit this Thai transcript:

```json
{
  "title": "Deep Work Thai Notes",
  "source_url": null,
  "language": "thai",
  "transcript": "[00:01] วิดีโอนี้พูดถึง deep work และการทำงานอย่างมีสมาธิ 00:45 ผู้พูดอธิบายว่าควรปิดสิ่งรบกวน วางแผนช่วงเวลาทำงานลึก และทบทวนผลลัพธ์หลังจบงาน"
}
```

4. Copy the returned `video_id`.
5. Expand `POST /api/videos/{video_id}/ask`, click `Try it out`, paste the copied `video_id`, and use this request body:

```json
{
  "question": "วิดีโอนี้พูดถึง deep work ยังไง"
}
```

6. Click `Execute`.

Expected result:

- HTTP 200
- `answer` explains that it is based on simple keyword matching
- `related_chunks` contains at least one chunk when the transcript includes matching terms

## Swagger UI V1.4 Markdown Export Test Flow

1. Start the server:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

2. Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

3. Use `GET /api/videos` to find a saved `video_id`.
4. Expand `GET /api/videos/{video_id}/export/markdown`.
5. Click `Try it out`, paste the `video_id`, and click `Execute`.

Expected result:

- HTTP 200
- Response content type is Markdown text
- Response body includes the title, summary sections, and transcript chunks

## Swagger UI V1.5 Thai Summary Test Flow

1. Start the server:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

2. Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

3. Expand `POST /api/videos/process`, click `Try it out`, and submit:

```json
{
  "title": "Deep Work Test",
  "source_url": "https://youtube.com/test",
  "language": "thai",
  "transcript": "00:01 วันนี้เราจะพูดถึง deep work 00:05 deep work คือการทำงานแบบมีสมาธิลึกและไม่ถูกรบกวน 00:10 ปัญหาของยุคนี้คือมือถือ notification และ social media ทำให้เราหลุดโฟกัสบ่อย 00:15 เมื่อเราเช็กมือถือ สมองจะได้รับ dopamine สั้น ๆ ทำให้เราติดการสลับความสนใจ 00:20 ถ้าอยากทำงานลึก เราควรปิด notification วางมือถือให้ไกล และกำหนดช่วงเวลาทำงานที่ชัดเจน"
}
```

4. Confirm the response summary is Thai and does not contain generic English placeholder text.
5. Copy the returned `video_id`.
6. Use `GET /api/videos/{video_id}/export/markdown`.
7. Confirm the Markdown includes Thai TL;DR, main ideas, key takeaways, action items, questions to think, and transcript chunks.
