# ROADMAP.md

## 1. Project Vision

izuna-video-lab is a video knowledge pipeline that turns long-form video content into reusable knowledge notes. It starts with manually pasted transcripts and gradually grows into a system that can summarize, ask questions, and search across videos.

Over time, the project should support Q&A and search across one or many videos while keeping each phase small, testable, and easy to reverse.

## 2. Pipeline Overview

```text
Video / Transcript
↓
Clean
↓
Chunk
↓
Summarize
↓
Ask & Search
↓
Personal Knowledge Base
```

## 3. Current Status

- [x] V1.0 FastAPI backend
- [x] Health endpoint
- [x] Manual transcript process endpoint
- [x] Transcript cleaning
- [x] Transcript chunking
- [x] V1.1 Mock summary
- [x] V1.2 Local storage
- [x] V1.3 Ask Q&A from chunks
- [x] V1.4 Export Markdown summary
- [x] V1.5 Improved Thai rule-based summary
- [x] V1.6 Regression tests
- [x] V2.0 Minimal LLM summarization integration
- [x] V2.1 OpenAI real smoke test support
- [x] V2.1.1 Config restructure and .env support
- [x] V2.1.2 OpenAI provider debug and .env-first config restructure
- [x] V2.2 Ollama local LLM provider
- [x] V2.3 YouTube Caption Fetcher

## 4. Phase 1: Manual Transcript MVP

- V1.0 Clean + Chunk
- V1.1 Mock Summary
- V1.2 Local JSON storage
- V1.3 Simple Q&A from chunks
- V1.4 Export Markdown summary
- V1.5 Improved Thai rule-based summary
- V1.6 Regression tests

## 5. Phase 2: Better Summarization

- [x] Add optional real LLM summarization
- [x] Add provider metadata for OpenAI smoke testing
- [x] Add project-root .env config support
- [x] Add safe OpenAI config debug and smoke-test endpoint
- [x] Add local Ollama provider and smoke-test endpoint
- Keep broader LLM summarization improvements as future work after the deterministic pipeline remains stable
- Add summary styles: short, study_note, deep
- Add structured output: TLDR, main ideas, key takeaways, action items, questions to think

## 6. Phase 3: Transcript Acquisition

- [x] Auto-fetch YouTube transcript when captions are available
- [x] Preserve manual transcript fallback
- Handle unavailable/private/restricted content safely
- Do not bypass access controls

## 7. Phase 4: Speech-to-Text Fallback

- Add Whisper or another ASR option
- Process uploaded audio/video
- Store generated transcript

## 8. Phase 5: Searchable Knowledge Base

- Chunk embeddings
- Vector search
- Ask across one video
- Ask across many videos
- Link answers back to chunk/timestamp when available

## 9. Phase 6: Frontend and UX

- Simple web UI
- Paste transcript form
- Summary view
- Q&A panel
- Markdown export

## 10. Guiding Principles

- Build small
- Keep the pipeline visible
- Prefer correctness over automation
- Do not add AI until the deterministic pipeline is stable
- Think in systems, not in features
