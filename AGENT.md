# AGENT.md

## 1. Project Identity

- Name: izuna-video-lab
- Purpose: Convert video transcripts into structured, searchable knowledge
- Mental model: Video -> Transcript -> Clean -> Chunk -> Summarize -> Ask/Search -> Knowledge Base

## 2. Current Scope

- Manual transcript input only
- FastAPI backend only
- Local development only
- Mock summarization only for now
- No production deployment yet

## 3. Strict Non-Goals For Now

- Do not fetch YouTube transcripts automatically yet
- Do not use Whisper yet
- Do not add vector database yet
- Do not add frontend yet
- Do not add authentication yet
- Do not call external LLM APIs unless explicitly requested
- Do not introduce unnecessary dependencies
- Do not commit secrets, API keys, tokens, or credentials

## 4. Architecture Rules

- Keep the pipeline modular
- Separate API layer, schema layer, service layer, and storage layer
- Keep transcript_cleaner.py focused only on cleaning
- Keep transcript_chunker.py focused only on chunking
- Keep summarizer.py focused only on summarization
- Prefer simple deterministic logic before adding AI calls
- Each new feature should be small, testable, and reversible

## 5. Development Rules

- Update README.md when adding or changing API behavior
- Keep response schemas explicit with Pydantic models
- Add type hints where reasonable
- Prefer clear names over clever abstractions
- Before adding a dependency, explain why it is needed
- After changes, show the changed files and how to test them

## 6. Testing Rules

- Test with Swagger UI at /docs
- Test POST /api/videos/process after every pipeline change
- Include at least one Thai transcript example and one English transcript example when relevant
- Validate empty transcript behavior

## 7. Agent Behavior

- Read this file before making changes
- Follow the roadmap
- Do not jump to later phases unless explicitly asked
- When unsure, ask before expanding scope
