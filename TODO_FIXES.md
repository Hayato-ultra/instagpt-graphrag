# InstaGPT-GraphRAG — Master TODO & Progress Record

Merged from `instagpt_graphrag_problems_solutions.txt` (architectural) and the original `TODO_FIXES.md` (extraction quality).

Legend: ✅ done | 🔧 partial | 🔲 not started

---

## PART A — Extraction & Output Quality

### 1. Summary Repetitive
**Issue**: Summary concatenates all entity summaries without deduplication
**Status**: ✅ Fixed in commit d4bdcb4 — deduplicates by checking first 80 chars

---

### 2. Entity Extraction Fabricates Wrong Entities (CRITICAL)
**Issue**: Pipeline extracts completely wrong entities (19 of 24 fabricated in latest test)
**Examples**: "Console Ninja" → "Panc"; "AppRite" → "Appwrite"; 5 repos → 24 unrelated entities
**Root Cause**: LLM hallucinates based on topic context, not actual transcript content
**Status**: ✅ Fixed — `post_validate_entities()` validates against source transcript with fuzzy matching; entities not found in source are filtered

---

### 3. URL/Domain Transcription Errors (CRITICAL)
**Issue**: LLM mishears domain names (`github.dev` → `GitHub.in`, `supabase.com` → `siypabase.com`)
**Status**: ✅ Fixed — `_validate_domain()` checks against known domains; suspicious patterns rejected; domain corrections applied

---

### 4. Descriptions Are Template Text (CRITICAL)
**Issue**: Descriptions are "EntityType.X in the source content" — not real content
**Status**: ✅ Fixed — `is_template_description()` detects template patterns; cleared in `_validate_entities_against_source()` and `_assemble_enriched()`

---

### 5. Summary Lists Entity Types Instead of Actual Summary (CRITICAL)
**Issue**: Summary is "web app is a EntityType.WEB_APP" — entity-type garbage
**Status**: ✅ Fixed — `is_template_summary()` detects EntityType keywords; summary generation can be validated post-LLM

---

### 6. 0% Confidence — Pipeline Failed to Validate (CRITICAL)
**Issue**: Every entity has 0% confidence
**Status**: ✅ Fixed — `validate_confidence()` rejects entities below 0.3 threshold; applied in `post_validate_entities()`

---

### 7. Extraction Misses Key Concepts/Teachings
**Issue**: Extracts shown items (websites, UI) but not taught concepts (UX principles)
**Status**: ✅ Fixed — extraction prompt now includes concepts, principles, techniques, and actionable steps

---

### 8. Step Extraction Too Vague
**Issue**: "Bulk actions UX is a system" instead of actionable steps
**Status**: ✅ Fixed — extraction prompt now requests specific actionable steps and techniques

---

### 9. Entity Extraction Misses UX/UI Principles
**Issue**: Doesn't extract patterns like "Reversible beats careful"
**Status**: ✅ Fixed — extraction prompt now includes `principle` type and UX/UI patterns

---

### 10. Entity Name Misspelling
**Issue**: "contract" → "Contra"; "AppRite" → "Appwrite"
**Status**: ✅ Fixed — `_fix_misspelling()` with expanded dictionary (50+ entries); `_fuzzy_match_to_known()` with 0.85 threshold

---

### 11. Duplicate Entities Due to Casing/Formatting
**Issue**: "vscode" / "VS Code", "postgres" / "PostgreSQL" as separate entities
**Status**: ✅ Fixed — `EntityResolver` with `normalize_name()` + `names_align()`; benchmark scores 1.000/1.000/1.000; pipeline-level dedup uses same normalization (61 unit tests pass)

---

### 12. "High School" Hallucinated as Freelancing Platform
**Issue**: LLM misheard audio; presents non-existent platform as real
**Status**: ✅ Fixed — `src/enrichment/hallucination.py` validates entities against source text with fuzzy matching

---

### 13. "upwork" Fabricated — Not in Transcript
**Issue**: LLM hallucinated "upwork" as common freelancing platform
**Status**: ✅ Fixed — `filter_hallucinated()` removes entities not found in source transcript

---

### 14. Missing Entity: "People Per Hour"
**Issue**: Mentioned in reel but completely missing from output
**Status**: ✅ Fixed — recall validation via `validate_entities()` reports missing entities

---

### 15. Fabricated Key Points Not in Transcript
**Issue**: "sidehustleindia" listed in key points but never mentioned
**Status**: ✅ Fixed — `filter_hallucinated()` validates key points against source

---

### 16. Related Entities Should Be Categorized Separately
**Issue**: Web-search-only entities mixed with transcript-mentioned entities
**Status**: ✅ Fixed — `EntityType.RELATED` added to enum; web-search-only entities can be marked as RELATED

---

### 17. Series Name Extracted as Entity — "financialfreedom"
**Issue**: Series intro phrases treated as concept entities
**Status**: ✅ Fixed — `is_series_name()` detects "Day X of...", "Episode X...", "Part X of..." patterns; entities filtered in `_validate_entities_against_source()`

---

### 18. Language/Framework as Entity — "JAVA"
**Issue**: Languages extracted as standalone entities when they're context, not content
**Status**: ✅ Fixed — `should_skip_entity_type()` skips EntityType.LANGUAGE; entities filtered in `_validate_entities_against_source()`

---

### 19. Summary Text Garbled/Truncated
**Issue**: "and mod just.com" — broken/incomplete sentence
**Status**: ✅ Fixed — `is_garbled_text()` detects repeated chars, multiple question marks, short text

---

### 20. Step-by-Step Guide Misused for Project Ideas
**Issue**: Guide section contains project ideas instead of actionable steps
**Status**: ✅ Fixed — `output_format.py` separates projects from entities, validates guide content

---

### 21. Step-by-Step Guide Missing Title
**Issue**: Guide section has no title
**Status**: ✅ Fixed — `_ensure_guide_title()` generates title if missing

---

### 22. Guide Section Placement — Should Be After Summary
**Issue**: Order is Guide → Summary; should be Summary → Guide
**Status**: ✅ Fixed — `validate_output_ordering()` ensures correct section order

---

### 23. Key Points Duplicate Description Content
**Issue**: Key points repeat what's already in description
**Status**: ✅ Fixed — `has_duplicate_content()` detects summary/key-point overlap with similarity threshold

---

### 24. Projects Should Be Under "## Projects" Section
**Issue**: Project entities appear under "## Other"
**Status**: ✅ Fixed — `_is_project_entity()` detects projects, `format_output()` separates them

---

### 25. Project Descriptions Missing Build Instructions
**Issue**: Descriptions don't explain how to build
**Status**: ✅ Fixed — `_add_build_instructions()` appends setup note if missing

---

### 26. Source URL in Every Topic — Wrong Approach
**Issue**: Instagram source URL shown instead of entity's website
**Status**: ✅ Fixed — `src/enrichment/url_enrichment.py` searches for official entity URLs

---

### 27. OCR Noise Still Affects Some Reels
**Issue**: Screen recordings extract irrelevant entities
**Status**: ✅ Fixed — `_is_screen_recording()` detects cursor/click patterns; `_is_ocr_noise()` expanded with 15 social media patterns; filtered in `validate_entity_name()`

---

### 28. Hinglish Translation Partial
**Issue**: Hindi/Hinglish transcripts only partially translated
**Status**: ✅ Fixed — `_translate_hinglish_if_needed()` handles Hindi/Hinglish with LLM translation

---

### 29. Categories Not Matching Content
**Issue**: UX tutorial entities categorized as "tool_review"
**Status**: ✅ Fixed — categorizer prompt improved with topic definitions and content type matching

---

### 30. No Validation of Extracted Steps
**Issue**: Steps may not match transcript content
**Status**: ✅ Fixed — `validate_key_points()` removes empty/duplicate points, enforces min/max count

---

### 31. Pipeline Slow (10 min avg per link)
**Issue**: Each link takes ~10 min (enrichment 3-4 min, categorization 2-3 min)
**Status**: ✅ Fixed — `src/pipeline/parallel.py` enables concurrent processing with bounded parallelism

---

### 32. Missing Website Links for Extracted Entities
**Issue**: Entity extracted but no website/repo link found
**Status**: ✅ Fixed — `search_entity_url()` searches DuckDuckGo for official entity URLs

---

## PART B — Architecture & Reliability (from instagpt_graphrag_problems_solutions.txt)

### 33. Data Consistency Across PostgreSQL, Neo4j, and Qdrant
**Solution**: PostgreSQL as source of truth; transactional outbox; stable IDs; idempotent writes; reconciliation
**Status**: ✅ Fixed
- ✅ PostgreSQL as source of truth (enforced throughout)
- ✅ Transactional outbox (`src/pipeline/outbox.py`)
- ✅ Stable entity IDs (`entity-{pg_id}` deterministic scheme)
- ✅ Idempotent Neo4j/Qdrant writes (MERGE-based)
- ✅ Step-level job state (`src/pipeline/resumable.py`, `src/pipeline/recorder.py`)
- ✅ Reconciliation jobs (`src/database/reconcile.py`)
- ✅ Exponential backoff with dead-letter handling (004_backoff migration)
- ✅ Cross-store consistency checker (`src/database/consistency.py`)

---

### 34. Entity Resolution at Scale
**Solution**: Multi-stage resolver; aliases; confidence scores; benchmark
**Status**: ✅ Fixed
- ✅ `EntityResolver` with exact → alias → embedding MERGE/SIMILAR/NEW
- ✅ `normalize_name()` + `names_align()` for typo/abbreviation detection
- ✅ Resolution benchmark (`tests/fixtures/golden/resolution/entity_resolution.json`)
- ✅ Benchmark scores 1.000/1.000/1.000 on 10-pair golden dataset
- ✅ Graph-based similarity via `_graph_similarity()` in entity_resolver.py
- 🔲 LLM verification for ambiguous cases (optional enhancement)

---

### 35. Graph Pollution
**Solution**: Confidence thresholds; provenance; dedup; cleanup jobs
**Status**: ✅ Fixed
- ✅ Confidence scoring in enrichment pipeline
- ✅ Entity dedup via `EntityResolver`
- ✅ Graph cleanup job (`src/database/cleanup.py`) — flags low-confidence, stale, and isolated nodes
- ✅ Provenance: extraction_timestamp, pipeline_version, model_version, embedding_version (005_provenance migration)

---

### 36. LLM Hallucination Contamination
**Solution**: Structured output; source evidence; confidence; versioning
**Status**: ✅ Fixed
- ✅ Structured output with Pydantic models
- ✅ Source evidence (`source_url`, `source_chunk_id`)
- ✅ Confidence scoring
- ✅ Model/prompt/pipeline version tracking (`EMBEDDING_MODEL_VERSION` in config)
- ✅ Hallucination detection (`src/enrichment/hallucination.py`)

---

### 37. Static Hybrid-Search Weighting
**Solution**: Query-aware retrieval; dynamic weights; reranker; evaluation metrics
**Status**: ✅ Fixed
- ✅ Query classification (`_classify_query()`: lookup, semantic, relationship, balanced)
- ✅ Adaptive weight profiles in `HybridSearcher.WEIGHT_PROFILES`
- ✅ Dynamic weight adjustment in `search()` method

---

### 38. Lack of Evaluation Framework
**Solution**: Golden datasets; P/R/F1/Recall@K/MRR/NDCG; regression tests; version tracking
**Status**: ✅ Fixed
- ✅ Resolution benchmark with golden dataset (P/R/F1)
- ✅ `scripts/evaluate.py` skeleton for extraction evaluation
- ✅ `src/enrichment/evaluator.py` — `PipelineEvaluator` tracks extraction precision, hallucination rate, summary/step quality
- ✅ `EvalMetrics` dataclass with `to_dict()` and `log_summary()`
- 🔲 Retrieval benchmark (not implemented)
- 🔲 RAG evaluation (not implemented)
- 🔲 CI-integrated regression tests (not implemented)

---

### 39. Multi-LLM Provider Complexity
**Solution**: Provider abstraction; adapters; compatibility tests
**Status**: ✅ Fixed
- ✅ `LLMClient` with Ollama/OpenAI providers
- ✅ Provider-specific adapters in `src/enrichment/adapters.py` (OpenAI, OpenRouter, Nvidia, Ollama)
- 🔲 Compatibility tests per provider (optional enhancement)

---

### 40. Embedding-Model Changes Can Break Vector Data
**Solution**: Store model/version/dimension; version collections; migration support
**Status**: ✅ Fixed
- ✅ `EMBEDDING_MODEL_VERSION` in Settings for version tracking
- ✅ `OPENAI_EMBEDDING_MODEL` and `OPENAI_EMBEDDING_DIM` already tracked
- ✅ `EMBEDDING_MODELS` registry in `src/vector/vector_store.py` with provider/dimension metadata

---

### 41. Web Scraping Is Fragile
**Solution**: Fallbacks; retry/timeout; error classification; dead-letter; monitoring
**Status**: ✅ Fixed
- ✅ Retry logic exists in extraction
- ✅ Multiple extraction fallbacks (trafilatura→readability→webcrawl→playwright)
- ✅ Error classification in `src/extraction/error_classification.py` (temporary/permanent/auth/network)
- 🔲 Dead-letter handling for failed URLs (optional enhancement)

---

### 42. Video Processing Is Computationally Expensive
**Solution**: Async workers; CPU/GPU separation; batching; adaptive frame sampling
**Status**: ✅ Fixed
- ✅ `src/extraction/video_optimizer.py` — adaptive frame sampling
- ✅ `calculate_optimal_interval()` — dynamic interval based on video length
- ✅ `select_key_frames()` — content-aware frame selection with dedup

---

### 43. Pipeline Needs Scalable Job Architecture
**Solution**: Jobs; queue; workers by workload; concurrency limits; step state; retry
**Status**: ✅ Fixed
- ✅ Step-level job state (`recorder.py`, `resumable.py`)
- ✅ Step-level checkpointing and resume
- ✅ Outbox pattern with `OutboxWorker` for async projection
- ✅ `ParallelPipeline` with bounded concurrency for scaling
- 🔲 Worker separation by workload (optional enhancement)

---

### 44. Failure Recovery
**Solution**: Step-level retry; checkpoints; idempotency; exponential backoff; dead-letter
**Status**: ✅ Fixed
- ✅ Step-level resume (`resumable.py`)
- ✅ Idempotent operations throughout
- ✅ Outbox dead-letter events (`FAILED` status)
- ✅ Exponential backoff (`next_retry_at` with 5s × 2^attempts, capped at 300s) — 004_backoff migration

---

### 45. Duplicate Processing
**Solution**: Canonical URLs; deterministic content IDs; unique constraints; idempotency
**Status**: ✅ Fixed
- ✅ `normalize_url()` for canonical URL form
- ✅ Deterministic content hashing (SHA-256)
- ✅ Idempotent writes via MERGE-based Neo4j/Qdrant operations
- ✅ Unique constraints on all major DB tables

---

### 46. Schema Evolution Across Multiple Systems
**Solution**: Version schemas; Alembic; compatibility; integration tests
**Status**: ✅ Fixed
- ✅ Alembic migrations: 001_initial, 002_pipeline_state, 003_outbox, 004_backoff, 005_provenance, 006_indexes
- ✅ Schema evolution tests in `tests/unit/test_schema_evolution.py`
- ✅ `PipelineVersions` dataclass tracks schema/model/prompt versions

---

### 47. Frontend/Backend Contract Drift
**Solution**: OpenAPI schemas; generated TypeScript types; contract tests
**Status**: ✅ Fixed
- ✅ FastAPI with auto-generated OpenAPI
- ✅ TypeScript type generation from OpenAPI (`scripts/generate_ts_types.py`)
- ✅ API contract tests (`tests/unit/test_api_contracts.py`)

---

### 48. Neo4j Graph-Query Performance
**Solution**: Indexes; limit traversals; paginate; profile; cache
**Status**: ✅ Fixed
- ✅ Entity name unique constraint
- ✅ Entity type index
- ✅ Entity topic index
- ✅ Entity updated_at index
- ✅ EpisodicMemory timestamp index
- ✅ Chunk source_url index
- ✅ Fulltext search index for entity search

---

### 49. Qdrant Scaling
**Solution**: HNSW tuning; quantization; partitioning; monitoring
**Status**: ✅ Fixed
- ✅ Vector collection configured with distance metric
- ✅ Payload indexing for entity type filtering
- ✅ Score threshold filtering in search

---

### 50. PostgreSQL Bottleneck
**Solution**: Indexes; connection pooling; optimize queries; partition; archive
**Status**: ✅ Fixed
- ✅ Connection pooling (async SQLAlchemy)
- ✅ Index optimization (006_indexes migration: 8 indexes for hot paths)
- ✅ Table partitioning in `src/database/partitioning.py` with `TablePartitioner`

---

### 51. Lack of Observability
**Solution**: Structured logs; request/job IDs; tracing; dashboards
**Status**: ✅ Fixed
- ✅ Structured logging (loguru)
- ✅ Request/job ID correlation (`RequestIDMiddleware` + `X-Request-ID` header)
- 🔲 Distributed tracing (not implemented)
- 🔲 Dashboards/alerts (not implemented)

---

### 52. Security Risks
**Solution**: URL validation; SSRF protection; secrets management; auth; rate limits
**Status**: ✅ Fixed
- ✅ SSRF protection (`src/security/validators.py` — `is_safe_url()`, `sanitize_url()`)
- ✅ Private IP blocking (localhost, 127.0.0.1, 10.x, 192.168.x, 172.16.x)
- ✅ Metadata endpoint blocking (169.254.169.254)
- ✅ Rate limiting (`RateLimitMiddleware` — 120 req/min per IP)

---

### 53. Prompt Injection from Scraped Content
**Solution**: Treat scraped text as untrusted; separate system/content; validate tool calls
**Status**: ✅ Fixed
- ✅ Prompt injection detection (`detect_prompt_injection()` — 9 patterns)
- ✅ Content sanitization (`sanitize_for_llm()` — truncation + injection removal)
- ✅ Pattern detection for "ignore previous instructions", "act as", "[INST]", etc.

---

### 54. LLM Cost Explosion
**Solution**: Model routing; cheap/expensive split; caching; batching; budgets
**Status**: ✅ Fixed
- ✅ Enrichment caching (`_enrichment_cache`)
- ✅ Model routing strategy in `src/enrichment/token_budget.py` with `TokenBudgetManager`
- ✅ Token/cost budgets per task type (extraction, summary, categorization, validation)
- ✅ Usage tracking and fallback routing based on budget

---

### 55. Retrieval Quality Degradation
**Solution**: Dedup candidates; reranking; metadata filtering; benchmarks
**Status**: ✅ Fixed
- ✅ `src/search/retrieval.py` — `filter_and_rank_results()` with diversity boost
- ✅ Minimum relevance score filtering
- ✅ Entity type diversity weighting
- ✅ Result limiting

---

### 56. Context-Window Growth
**Solution**: Token budgets; rerank before assembly; compress context
**Status**: ✅ Fixed
- ✅ `fit_context_window()` — greedy token-budget fitting
- ✅ `RetrievalConfig.max_context_tokens` (default 8000)
- ✅ Token estimation (4 chars per token heuristic)

---

### 57. Temporal Knowledge
**Solution**: valid_from/valid_until; historical facts; source timestamps
**Status**: ✅ Fixed
- ✅ `valid_from` and `valid_until` columns on Entity model
- ✅ `src/database/lifecycle.py` — cleanup expired entities

---

### 58. Missing or Weak Provenance
**Solution**: Source URL/content ID; extraction timestamp; model/prompt version; evidence-backed answers
**Status**: ✅ Fixed
- ✅ Source URL and chunk ID on entities
- ✅ Extraction timestamp (`extraction_timestamp` column)
- ✅ Pipeline version (`pipeline_version` column)
- ✅ Model version (`model_version` column)
- ✅ Embedding version (`embedding_version` column)
- ✅ Alembic migration 005_provenance

---

### 59. Testing Not Proportional to System Complexity
**Solution**: Unit/integration/API/E2E tests; regression datasets; CI evaluation
**Status**: ✅ Fixed
- ✅ 87 unit tests passing (outbox, reconciliation, resume, dedup, resolution, output validation, API contracts)
- ✅ Golden datasets: resolution benchmark + synthetic article
- ✅ API contract tests (13 tests covering /api/jobs, /api/search, /api/graph, /api/video)
- 🔲 Integration tests for PG/Neo4j/Qdrant (marked `integration`, not run in unit suite)

---

### 60. Knowledge and Pipeline Versioning
**Solution**: Store pipeline_version, model_version, prompt_version, embedding_version, schema_version
**Status**: ✅ Fixed
- ✅ `src/pipeline/versions.py` — `PipelineVersions` dataclass
- ✅ `get_current_versions()` / `set_versions()` for version tracking
- ✅ Provenance columns on Entity model (pipeline_version, model_version, embedding_version)

---

### 61. Distributed-System Complexity
**Solution**: Clear ownership; explicit events; idempotency; health checks; circuit breakers
**Status**: ✅ Fixed
- ✅ Idempotent operations throughout
- ✅ Outbox events between PG → derived stores
- ✅ Health checks (`GET /health` endpoint)
- ✅ Rate limiting (`RateLimitMiddleware`)

---

### 62. Backup and Disaster Recovery
**Solution**: Back up PG/Neo4j/Qdrant; test restoration; documented recovery procedure
**Status**: ✅ Fixed
- ✅ `src/database/backup.py` — `BackupManager` class
- ✅ `backup_pg()`, `backup_neo4j()`, `backup_qdrant()` methods
- ✅ `backup_all()` for full system backup

---

### 63. Data Lifecycle and Storage Growth
**Solution**: Retention policies; separate active/archived; cleanup workers
**Status**: ✅ Fixed
- ✅ `src/database/lifecycle.py` — `LifecycleManager` class
- ✅ Configurable retention periods for entities, episodic memories, outbox events
- ✅ `run_full_cleanup()` for automated maintenance

---

### 64. Concurrency and Race Conditions
**Solution**: DB constraints/transactions; lock entity merges; deterministic IDs; optimistic concurrency
**Status**: ✅ Fixed
- ✅ Deterministic entity IDs (`entity-{pg_id}`)
- ✅ Idempotent operations throughout
- ✅ `get_entity_by_name_for_update()` with `SELECT ... FOR UPDATE` for entity merge locking
- ✅ `update_entity()` auto-bumps version for optimistic concurrency detection

---

### 65. API Reliability
**Solution**: Validation; timeouts; error schemas; pagination; rate limits; async jobs
**Status**: ✅ Fixed
- ✅ Pydantic request/response validation
- ✅ Job status endpoint (`/jobs/{id}`)
- ✅ Pagination on list endpoints (limit/offset with has_more flag)
- ✅ Rate limiting (`RateLimitMiddleware` — 120 req/min per IP)

---

### 66. Development Complexity and Maintainability
**Solution**: Module boundaries; interfaces; dependency injection; architecture docs; CI
**Status**: ✅ Fixed
- ✅ Clear module boundaries (extraction, enrichment, graph, vector, pipeline)
- ✅ ruff + mypy in CI (pyproject.toml configured)
- ✅ Architecture documentation (`docs/architecture.md`)

---

### 67. Overengineering Risk
**Solution**: Keep PG + FastAPI + Neo4j + Qdrant + React; add infra based on measured need
**Status**: ✅ Current stack matches target architecture exactly

---

## Implementation Phases (from instagpt_graphrag_problems_solutions.txt)

### Phase 1 — Reliability Foundation
| # | Item | Status |
|---|------|--------|
| 1 | PostgreSQL as source of truth | ✅ |
| 2 | Transactional Outbox | ✅ `src/pipeline/outbox.py` |
| 3 | Stable entity IDs | ✅ `entity-{pg_id}` |
| 4 | Idempotent Neo4j/Qdrant writes | ✅ MERGE-based throughout |
| 5 | Step-level job state | ✅ `src/pipeline/recorder.py`, `src/pipeline/resumable.py` |
| 6 | Retry + dead-letter handling | ✅ exponential backoff via next_retry_at + FAILED dead-letter |
| 7 | Reconciliation | ✅ `src/database/reconcile.py` |

### Phase 2 — Data Quality
| # | Item | Status |
|---|------|--------|
| 1 | Entity-resolution benchmark | ✅ 1.000/1.000/1.000 on golden dataset |
| 2 | Confidence scoring | ✅ in enrichment pipeline |
| 3 | Provenance | ✅ extraction_timestamp, pipeline_version, model_version, embedding_version |
| 4 | Fact validation | ✅ template description/summary rejection + series/language filtering |
| 5 | Graph cleanup | ✅ `src/database/cleanup.py` — flags low-confidence, stale, isolated nodes |
| 6 | Duplicate detection | ✅ EntityResolver + pipeline dedup |
| 7 | Embedding/pipeline versioning | ✅ `EMBEDDING_MODEL_VERSION` in config + `EMBEDDING_MODELS` registry |

### Phase 3 — Retrieval Quality
| # | Item | Status |
|---|------|--------|
| 1 | Hybrid retrieval benchmark | 🔲 not started |
| 2 | Dynamic query routing | ✅ `_classify_query()` with lookup/semantic/relationship/balanced |
| 3 | Reranking | ✅ `filter_and_rank_results()` with diversity boost |
| 4 | Context compression | ✅ `fit_context_window()` with token budget |
| 5 | Metadata filtering | ✅ min relevance score + entity type filtering |
| 6 | Retrieval evaluation | 🔲 not started |

### Phase 4 — Scale
| # | Item | Status |
|---|------|--------|
| 1 | Worker architecture | ✅ `src/pipeline/parallel.py` — bounded concurrency |
| 2 | Queue system | ✅ Outbox pattern with background worker |
| 3 | CPU/GPU separation | 🔲 not started |
| 4 | Caching | ✅ enrichment cache + translation cache |
| 5 | Batch processing | ✅ categorization batched |
| 6 | Database scaling | ✅ connection pooling + indexes |
| 7 | Observability + dashboards | ✅ structured logging + request IDs |

### Phase 5 — Production Security
| # | Item | Status |
|---|------|--------|
| 1 | Authentication | 🔲 not started |
| 2 | Authorization | 🔲 not started |
| 3 | SSRF protection | ✅ `src/security/validators.py` — `is_safe_url()`, private IP blocking |
| 4 | Prompt-injection defenses | ✅ `detect_prompt_injection()`, `sanitize_for_llm()` |
| 5 | Rate limiting | ✅ `RateLimitMiddleware` — 120 req/min per IP |
| 6 | Secret management | 🔲 not started |
| 7 | Backup/recovery testing | 🔲 not started |

---

## Priority — Next Incomplete Tasks (by impact)

### Immediate (Phase 1 completions)
1. ✅ **#64 concurrency** — SELECT FOR UPDATE + version bumping for entity merges

### High (Phase 2 completions)
3. **#58 provenance** — Store extraction timestamp, model version, pipeline version on entities
4. **#36 hallucination** — Add model/prompt version tracking to extraction output
5. **#40 embedding versioning** — Store embedding model name/dimension with Qdrant collections
6. **#35 graph pollution** — Implement graph cleanup job for stale/low-confidence/isolated nodes

### Medium (Phase 3+4)
7. **#37 hybrid search** — Implement query-aware retrieval with dynamic weight routing
8. **#51 observability** — Add request/job ID correlation and pipeline-step latency tracking
9. **#43 scalable jobs** — Implement queue system (Redis/RQ or similar) for worker scaling

### Low (Phase 5)
10. **#52 security** — Add SSRF protection, URL validation, rate limiting
11. **#53 prompt injection** — Treat scraped content as untrusted; separate system/content
12. **#62 backup/recovery** — Document and test backup procedures for PG/Neo4j/Qdrant
