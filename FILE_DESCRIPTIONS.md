# InstaGPT GraphRAG - File Descriptions

## Project Overview
URL-to-Knowledge-Graph pipeline that extracts content from URLs, enriches entities with web search, categorizes them, and stores them in a neural graph (Neo4j + Qdrant).

---

## Root Files

| File | Description |
|------|-------------|
| `cli.py` | Typer CLI for processing URLs, viewing graph stats, searching entities, and exporting the knowledge graph. Commands: `process`, `graph`, `search`, `entity`, `config`. |
| `run_api.py` | Entry point to start the FastAPI server on port 8000 with hot reload. |
| `debug_extractor.py` | Debug script that extracts content from a single Instagram URL and writes raw text to `debug_output.txt`. |
| `_debug_pipeline.py` | Debug script testing the full extract → chunk → entity detection pipeline on a single URL. |
| `pyproject.toml` | Python project config: dependencies (Pydantic, httpx, Playwright, OpenAI, Qdrant, Neo4j, etc.), ruff/mypy/pytest settings. Requires Python ≥3.11. |
| `requirements.txt` | Pip dependencies: FastAPI, SQLAlchemy, OpenAI, Groq, yt-dlp, faster-whisper, tavily-python, Neo4j, sentence-transformers, OpenCV, etc. |
| `docker-compose.yml` | Docker services: Qdrant (ports 6333/6334) and Neo4j (ports 7474/7687) with persistent volumes. |
| `.env.example` | Template for environment variables: LLM provider keys (OpenAI, OpenRouter, NVIDIA, Google, Ollama, Colab), Qdrant/Neo4j URLs, pipeline tuning params. |
| `opencode.json` | OpenCode IDE config: references `docs/development-standards.md`, enables file-read caching via MCP. |
| `.gitignore` | Ignores temp dirs, env files, Python caches, IDE files, `docs/`, `*.txt`, `outputs/`. |
| `cookiesinsta.txt` | Netscape-format cookies file for Instagram authentication during scraping. |

---

## `src/` — Core Package

### `src/__init__.py`
Package init. Exports all public classes: `Settings`, `ContentExtractor`, `SemanticChunker`, `EntityDetector`, `EnrichmentPipeline`, `Categorizer`, `LLMClient`, `GraphStore`, `Neo4jGraphStore`, `Embedder`, `VectorStore`, `KnowledgeGraphPipeline`, `MarkdownGenerator`, `JSONGenerator`.

---

### `src/config/`

| File | Description |
|------|-------------|
| `__init__.py` | Re-exports `get_settings`, `Settings`, and all Pydantic models. |
| `config.py` | `Settings` class (Pydantic BaseSettings). Loads from `.env`. Contains all config: LLM providers, Qdrant/Neo4j, search, pipeline tuning, Playwright, output dir. Cached via `@lru_cache`. |
| `models.py` | Pydantic data models: `ContentType` (enum: tutorial, best_practice, etc.), `EntityType` (enum: framework, library, tool, etc.), `TopicCategory` (enum: frontend, backend, etc.), `ExtractedContent`, `DocumentChunk`, `EnrichedEntity`, `CategorizedItem`, `ProcessingResult`, `PipelineStage`. |

---

### `src/extraction/`

| File | Description |
|------|-------------|
| `__init__.py` | Exports `ContentExtractor`, `SemanticChunker`, `ExtractionStrategy`, `clean_text`. |
| `extractor.py` | **ContentExtractor**: Multi-strategy URL content extraction. Tries trafilatura → readability → webcrawl → Playwright. Special Instagram extraction using saved cookies. **SemanticChunker**: Splits text by markdown headers, respects token limits, adds overlap context. **clean_text()**: Strips whitespace and boilerplate. |

---

### `src/enrichment/`

| File | Description |
|------|-------------|
| `__init__.py` | Exports `EntityDetector`, `WebSearcher`, `EnrichmentPipeline`, `LLMClient`, `Categorizer`, and related types. |
| `enrichment.py` | **EntityDetector**: Regex-based tech entity detection with blacklists and known-entity boosting. **WebSearcher**: DuckDuckGo search with URL/title blacklisting; finds entity info and alternatives. **EnrichmentPipeline**: Orchestrates detect → search → batch LLM description generation. |
| `llm_client.py` | **LLMClient**: Unified async LLM client supporting OpenAI, OpenRouter, NVIDIA, Google, Ollama, Colab. Automatic fallback chain, retry logic (tenacity), streaming, structured JSON output. `ModelConfig` dataclass with cost tracking. |
| `categorizer.py` | **Categorizer**: LLM-based entity classification. Assigns topic (frontend/backend/etc.), content type (tutorial/comparison/etc.), subtopics, summary, key points. Uses `TOPIC_TAXONOMY` and `CONTENT_TYPE_DEFINITIONS` for validation. |

---

### `src/pipeline/`

| File | Description |
|------|-------------|
| `__init__.py` | Exports `KnowledgeGraphPipeline`, `PipelineResult`. |
| `pipeline.py` | **KnowledgeGraphPipeline**: 7-stage orchestrator: (1) Extract, (2) Chunk, (3) Embed, (4) Enrich, (5) Categorize, (6) Generate outputs, (7) Update graph. Handles single URL and batch processing with concurrency limits. Deduplicates entities. |

---

### `src/graph/`

| File | Description |
|------|-------------|
| `__init__.py` | Exports `GraphStore`, `Neo4jGraphStore`, `create_graph_store`, `MergeResult`. |
| `graph_store.py` | **GraphStore**: NetworkX-based in-memory graph. Creates entity/topic/subtopic nodes, SIMILAR_TO edges, episodic memory nodes. Deduplicates via vector similarity search. Exports to GraphML/GEXF/JSON. Includes `consolidate_graph()` for background dedup. |
| `neo4j_graph_store.py` | **Neo4jGraphStore**: Neo4j-backed graph with Qdrant for vector search. Creates constraints/indexes (unique names, vector index, fulltext search). Upserts entities with embedding similarity + exact name matching. Creates episodic memory nodes for updates. Topic/subtopic hierarchy with BELONGS_TO edges. |

---

### `src/vector/`

| File | Description |
|------|-------------|
| `__init__.py` | Exports `Embedder`, `VectorStore`. |
| `vector_store.py` | **Embedder**: OpenAI/NVIDIA/Google embedding with fallback and dimension adjustment. **VectorStore**: Qdrant client. Upserts document chunks and entities. Supports similarity search, hybrid search, source URL filtering. |

---

### `src/output/`

| File | Description |
|------|-------------|
| `__init__.py` | Exports `MarkdownGenerator`, `JSONGenerator`, `generate_outputs`. |
| `output_generator.py` | **MarkdownGenerator**: Produces structured markdown grouped by topic/subtopic with badges, descriptions, key points, similar tools, references, tags. **JSONGenerator**: Serializes categorized items with metadata. **generate_outputs()**: Creates both `.md` and `.json` files with timestamps. |
| `frontend.py` | **FastAPI app**: REST API + WebSocket for real-time updates. Endpoints: `/api/process` (background job), `/api/jobs`, `/api/search`, `/api/entity`, `/api/graph/stats`, `/api/graph/export`, `/api/outputs`. Serves static HTML. |

---

### `src/static/`

| File | Description |
|------|-------------|
| `index.html` | Dark-themed single-page web UI with tabs: Process URLs, Search, Graph Stats. Features: WebSocket real-time job updates, URL input management, entity search with topic filter, graph statistics display, result cards with markdown/JSON links, entity detail modal. |

---

## `scripts/video_pipeline/`

| File | Description |
|------|-------------|
| `video_pipeline.py` | Master orchestrator for 5-step video pipeline. Runs steps sequentially: download → extract frames → deduplicate → OCR → JSON. Supports skip flags and CLI args. |
| `download_videos.py` | Downloads YouTube videos with short transcripts (<50 chars) using yt-dlp. Limits to 720p. Skips already-downloaded files. |
| `extract_frames.py` | OpenCV-based frame extraction. Two modes: scene-change detection (histogram diff) or fixed-interval. Outputs PNG frames per video. |
| `deduplicate_frames.py` | Removes duplicate frames using perceptual hashing (imagehash) and color histogram correlation. Keeps unique frames only. |
| `ocr_frames.py` | Tesseract OCR on extracted frames. Outputs `.txt` files per frame and combined text per video. Configurable language and confidence threshold. |
| `process_ocr_to_json.py` | Processes OCR text files into JSON entries with auto-classification (13 categories). Extracts URLs, tools mentioned, word counts. Appends to master JSON. |

---

## `frontend/` — React App

| File | Description |
|------|-------------|
| `package.json` | React 19 + Vite 8 project. Dependencies: @xyflow/react (graph viz), zustand (state), react-router-dom, @tanstack/react-query, Tailwind CSS. |
| `vite.config.ts` | Vite config with React plugin. |
| `tsconfig.json` | TypeScript config. |
| `tailwind.config.js` | Tailwind CSS config. |
| `postcss.config.js` | PostCSS config for Tailwind. |
| `index.html` | HTML entry point. |
| `src/main.tsx` | React app bootstrap. |
| `src/App.tsx` | Root component with routing. |
| `src/index.css` | Global styles with Tailwind. |
| `src/types/index.ts` | TypeScript type definitions. |
| `src/store/index.ts` | Zustand state store. |
| `src/services/api.ts` | API client for backend communication. |
| `src/components/Layout.tsx` | App layout component. |
| `src/components/NodeSidebar.tsx` | Sidebar for node details in graph view. |
| `src/pages/HomePage.tsx` | Home page. |
| `src/pages/GraphPage.tsx` | Interactive graph visualization page. |
| `src/pages/SearchPage.tsx` | Entity search page. |
| `src/pages/NotebookPage.tsx` | Notebook/results page. |

---

## `.opencode/skills/`

OpenCode skill definitions for AI-assisted development. Includes skills for: async Python patterns, browser automation, database design, embedding strategies, FastAPI patterns, LLM app patterns, structured output, nosql, pydantic models, Python development/patterns/pro, RAG engineering, search, similarity search, vector databases, web scraping, YouTube transcripts, and video content extraction.
