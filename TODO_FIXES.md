# Known Issues & Fixes Required

## 1. Summary Repetitive (FIXED)
**Issue**: Summary concatenates all entity summaries without deduplication
**Example**: "This entity solves the problem of managing team members..." repeated 3 times
**Fix**: Deduplicate by checking first 80 chars of each summary
**Status**: ✅ Fixed in commit d4bdcb4

---

## 2. Extraction Misses Key Concepts/Teachings
**Issue**: Pipeline extracts what's SHOWN (websites, UI elements) but not what's TAUGHT (UX principles, patterns)
**Example**: Transcript teaches "Select all 247 rows, not just visible ones" but extraction only gets "Bulk actions UX" and 3 websites
**Root Cause**: 
- LLM prompt focuses on extracting named entities (tools, frameworks, platforms)
- Doesn't extract CONCEPTS, PRINCIPLES, or PATTERNS
- Step extraction is too vague ("Bulk actions UX is a system")
**Fix Required**:
- Add concept/principle extraction to `_llm_extract_entities()`
- Improve step extraction to capture specific implementation details
- Extract "rules" or "best practices" from tutorial content

---

## 3. Step Extraction Too Vague
**Issue**: Steps are generic, not actionable
**Current**: "Bulk actions UX is a system"
**Expected**: "Header checkbox has 3 states: checked, empty, partial" or "Select all should select ALL 247 rows, not just visible 6"
**Fix Required**:
- Improve step extraction prompt to capture specific implementation details
- Extract numbered steps, rules, or principles
- Capture "do this" / "don't do that" patterns

---

## 4. Entity Extraction Misses UX/UI Principles
**Issue**: Doesn't extract design patterns or principles
**Example Missing**:
- "Reversible beats careful" (undo > confirmation modal)
- "Selection lives in app state, not DOM"
- "Echo the count inside the button"
**Fix Required**:
- Add pattern/principle detection
- Extract quotes or rules from tutorial content
- Capture "best practices" as entities

---

## 5. OCR Noise Still Affects Some Reels
**Issue**: Some reels with heavy screen recordings still extract irrelevant entities
**Example**: Reels showing multiple tools in background get those tools as entities
**Status**: Partially fixed with caption-only validation
**Fix Required**: Better OCR noise filtering for screen recordings

---

## 6. Hinglish Translation Partial
**Issue**: Hindi/Hinglish transcripts only partially translated
**Example**: "DbMR1StzoTi" has Hinglish content, translation incomplete
**Fix Required**: Improve translation dictionary and fallback logic

---

## 7. Description Quality Inconsistent
**Issue**: Some entities get generic descriptions ("EntityType.TOOL in the source content")
**Root Cause**: Ollama returns inconsistent JSON formats
**Status**: Partially fixed with multi-format handling
**Fix Required**: Better prompt engineering for description generation

---

## 8. Pipeline Slow (10 min avg per link)
**Issue**: Each link takes ~10 minutes to process
**Breakdown**:
- Extraction: ~30s
- Embedding: ~5s
- Enrichment (LLM calls): ~3-4 min
- Categorization: ~2-3 min
- Output: ~1 min
- Graph update: ~10s
**Fix Required**:
- Batch LLM calls where possible
- Reduce categorization time
- Cache repeated entities

---

## 9. Categories Not Matching Content
**Issue**: Some entities get wrong categories
**Example**: UX tutorial entities categorized as "tool_review" instead of "tutorial"
**Fix Required**: Improve categorization prompt

---

## 10. No Validation of Extracted Steps
**Issue**: Steps may not match actual transcript content
**Example**: Step says "Install X" but transcript doesn't mention installation
**Fix Required**: Validate steps against transcript text

---

## Priority Order:
1. **#2 - Extract key concepts/teachings** (HIGH - core quality issue)
2. **#3 - Improve step extraction** (HIGH - makes output actionable)
3. **#4 - Extract UX/UI principles** (HIGH - captures actual value)
4. **#7 - Fix description quality** (MEDIUM - affects readability)
5. **#9 - Fix categorization** (MEDIUM - affects organization)
6. **#8 - Speed optimization** (LOW - can be improved later)
7. **#5 - OCR noise** (LOW - partially fixed)
8. **#6 - Hinglish translation** (LOW - edge case)
9. **#10 - Step validation** (LOW - quality check)
10. **#1 - Summary dedup** (DONE)
