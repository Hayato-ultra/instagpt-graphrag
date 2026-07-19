import json
import re
import math
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq()


def _get_transcript_for_timestamp(
    timestamp: float, segments: list[dict]
) -> str:
    for seg in segments:
        if seg["start"] <= timestamp <= seg["end"]:
            return seg["text"]
    closest = min(segments, key=lambda s: abs(s["start"] - timestamp))
    return closest["text"]


def _extract_hashtags(text: str) -> list[str]:
    return re.findall(r"#(\w+)", text)


def _compute_density_score(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    unique_ratio = len(set(words)) / len(words)
    length_score = min(len(words) / 50, 1.0)
    return round(unique_ratio * 0.5 + length_score * 0.5, 2)


def _parse_json_safe(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from: {raw[:200]}")


PASS_1_PROMPT = """Analyze this transcript segment. Extract the CORE structure.

Return ONLY valid JSON:
{{
  "theme": "overall theme (string)",
  "topic": "main topic (string)",
  "sub_topics": ["sub topic 1", "sub topic 2"],
  "category": "one of: financial_advice, tech_tutorial, motivation, health, education, lifestyle, business, entertainment, other",
  "sentiment": "one of: positive, negative, neutral, mixed",
  "confidence": 0.0 to 1.0,
  "full_description": "2-3 sentence summary"
}}

Transcript: "{transcript}" """


PASS_2_PROMPT = """Analyze this transcript segment. Extract DETAILED knowledge.

Return ONLY valid JSON:
{{
  "steps_or_details": ["step 1", "step 2"],
  "not_to_do": ["thing to avoid 1"],
  "competitor_comparison": "comparison if any, else empty string",
  "advantages_disadvantages": {{"pros": ["pro 1"], "cons": ["con 1"]}},
  "mentioned_resources": [
    {{"name": "name", "type": "website or app or tool or course", "url": "url or empty", "confidence": 0.0 to 1.0}}
  ],
  "key_entities": ["entity 1", "entity 2"],
  "key_quotes": ["notable quote 1"],
  "action_items": ["actionable takeaway 1"]
}}

Transcript: "{transcript}" """


FULL_PASS_1_PROMPT = """Analyze this COMPLETE video transcript. Extract the CORE structure.

Return ONLY valid JSON:
{{
  "theme": "overall theme",
  "topic": "main topic",
  "sub_topics": ["sub topic 1", "sub topic 2", "sub topic 3"],
  "category": "one of: financial_advice, tech_tutorial, motivation, health, education, lifestyle, business, entertainment, other",
  "overall_sentiment": "positive, negative, neutral, or mixed",
  "confidence": 0.0 to 1.0,
  "full_description": "comprehensive 3-5 sentence description",
  "content_length_seconds": estimated video length in seconds
}}

Full Transcript:
{full_transcript} """


FULL_PASS_2_PROMPT = """Analyze this COMPLETE video transcript. Extract DETAILED knowledge.

Return ONLY valid JSON:
{{
  "steps_or_details": ["step 1", "step 2", "step 3"],
  "not_to_do": ["thing to avoid 1"],
  "competitor_comparison": "comparison info if any",
  "advantages_disadvantages": {{"pros": ["pro 1"], "cons": ["con 1"]}},
  "mentioned_resources": [
    {{"name": "name", "type": "website or app or tool", "url": "url or empty", "confidence": 0.0 to 1.0}}
  ],
  "key_entities": ["entity 1", "entity 2"],
  "key_quotes": ["notable quote 1", "notable quote 2"],
  "action_items": ["actionable takeaway 1", "takeaway 2"],
  "target_audience": "who is this content for",
  "difficulty_level": "beginner, intermediate, or advanced"
}}

Full Transcript:
{full_transcript} """


FULL_PASS_3_PROMPT = """Based on this transcript, identify KEY MOMENTS and generate HASHTAGS.

Return ONLY valid JSON:
{{
  "key_moments": [
    {{"timestamp_hint": "approximate time or segment number", "description": "what happens", "importance": "high, medium, or low"}}
  ],
  "generated_hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
  "seo_keywords": ["keyword1", "keyword2", "keyword3"],
  "engagement_hooks": ["hook 1", "hook 2"]
}}

Full Transcript:
{full_transcript} """


def _llm_call(prompt: str, max_tokens: int = 1000, retries: int = 2) -> dict:
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return _parse_json_safe(response.choices[0].message.content.strip())
        except Exception as e:
            if attempt < retries:
                print(f"    [retry {attempt + 1}] {e}")
            else:
                return {}


def analyze_segment(transcript: str, timestamp: float) -> dict:
    p1 = _llm_call(PASS_1_PROMPT.format(transcript=transcript), max_tokens=500)
    p2 = _llm_call(PASS_2_PROMPT.format(transcript=transcript), max_tokens=1000)

    hashtags = _extract_hashtags(transcript)
    density = _compute_density_score(transcript)

    merged = {
        "timestamp": timestamp,
        "transcript": transcript,
        "density_score": density,
        "hashtags_in_text": hashtags,
    }
    merged.update(p1)
    merged.update(p2)

    defaults = {
        "theme": "Unknown", "topic": "Unknown", "sub_topics": [],
        "category": "unknown", "sentiment": "neutral", "confidence": 0.5,
        "full_description": "", "steps_or_details": [], "not_to_do": [],
        "competitor_comparison": "", "advantages_disadvantages": {"pros": [], "cons": []},
        "mentioned_resources": [], "key_entities": [], "key_quotes": [], "action_items": [],
    }
    for k, v in defaults.items():
        merged.setdefault(k, v)

    return merged


def analyze_full_transcript(transcript_segments: list[dict]) -> dict:
    full_transcript = " ".join([s["text"] for s in transcript_segments])

    print("    Pass 1/3: Core structure...")
    p1 = _llm_call(FULL_PASS_1_PROMPT.format(full_transcript=full_transcript), max_tokens=800)

    print("    Pass 2/3: Detailed knowledge...")
    p2 = _llm_call(FULL_PASS_2_PROMPT.format(full_transcript=full_transcript), max_tokens=1200)

    print("    Pass 3/3: Key moments & hashtags...")
    p3 = _llm_call(FULL_PASS_3_PROMPT.format(full_transcript=full_transcript), max_tokens=1000)

    hashtags = _extract_hashtags(full_transcript)
    avg_density = sum(_compute_density_score(s["text"]) for s in transcript_segments) / max(len(transcript_segments), 1)

    merged = {
        "hashtags_in_text": hashtags,
        "avg_density_score": round(avg_density, 2),
    }
    merged.update(p1)
    merged.update(p2)
    merged.update(p3)

    defaults = {
        "theme": "Unknown", "topic": "Unknown", "sub_topics": [],
        "category": "unknown", "overall_sentiment": "neutral", "confidence": 0.5,
        "full_description": "", "steps_or_details": [], "not_to_do": [],
        "competitor_comparison": "", "advantages_disadvantages": {"pros": [], "cons": []},
        "mentioned_resources": [], "key_entities": [], "key_quotes": [], "action_items": [],
        "key_moments": [], "generated_hashtags": [], "seo_keywords": [], "engagement_hooks": [],
        "target_audience": "", "difficulty_level": "beginner",
    }
    for k, v in defaults.items():
        merged.setdefault(k, v)

    return merged


def align_and_analyze(
    keyframes: list[dict],
    transcript_segments: list[dict],
) -> dict:
    print("  Analyzing individual segments (multi-pass)...")
    segment_results = []
    for i, kf in enumerate(keyframes):
        ts = kf["timestamp"]
        transcript = _get_transcript_for_timestamp(ts, transcript_segments)
        print(f"    Segment {i+1}/{len(keyframes)} @ {ts}s...")
        analysis = analyze_segment(transcript=transcript, timestamp=ts)
        segment_results.append(analysis)

    print("  Analyzing full transcript (3-pass)...")
    full_analysis = analyze_full_transcript(transcript_segments)

    key_moments = sorted(
        segment_results, key=lambda x: x.get("density_score", 0), reverse=True
    )[:5]
    full_analysis["top_key_moments"] = [
        {"timestamp": m["timestamp"], "topic": m.get("topic", ""), "score": m.get("density_score", 0)}
        for m in key_moments
    ]

    return {
        "full_analysis": full_analysis,
        "segments": segment_results,
    }
