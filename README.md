# izuna-video-lab

Python FastAPI backend MVP for manually pasted video transcripts. V1 cleans transcript text, splits it into chunks, and returns both the cleaned transcript and chunk metadata.

V1.1 adds deterministic mock summarization. It does not call an external LLM API, OpenAI API, YouTube, or Whisper.

V1.3 adds local JSON storage and deterministic keyword-based Q&A from saved transcript chunks.

V1.4 adds Markdown export for saved processed videos.

## Project Structure

```text
backend/
  app/
    __init__.py
    main.py
    schemas.py
    services/
      __init__.py
      markdown_exporter.py
      qa_engine.py
      summarizer.py
      transcript_cleaner.py
      transcript_chunker.py
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
