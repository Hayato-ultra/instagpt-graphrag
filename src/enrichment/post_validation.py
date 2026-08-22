"""Post-extraction validation and cleanup (TODO #2, #3, #6, #10, #27).

Filters hallucinated entities, fixes misspellings, validates confidence,
and cleans OCR noise.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from loguru import logger

# --- OCR Noise Patterns (TODO #27) ---
_OCR_NOISE_PATTERNS = [
    re.compile(
        r"(?:like|follow|share|comment|save|subscribe|watch)\s+(?:this|more|now)",
        re.IGNORECASE,
    ),
    re.compile(r"\d+[kKmM]?\s*(?:likes?|views?|followers?)", re.IGNORECASE),
    re.compile(
        r"(?:instagram|facebook|youtube)\s*(?:reel|video|post)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:tap|click)\s+(?:here|link|bio)", re.IGNORECASE),
    re.compile(r"(?:part|day)\s+\d+\s+(?:of|/\d+)", re.IGNORECASE),
    # Additional OCR noise patterns
    re.compile(r"(?:link\s+in\s+bio|follow\s+for\s+more)", re.IGNORECASE),
    re.compile(r"(?:check\s+out|visit)\s+(?:my|our|the)\s+(?:profile|page|link)", re.IGNORECASE),
    re.compile(r"(?:drop\s+a?\s*(?:follow|like|comment))", re.IGNORECASE),
    re.compile(r"(?:new\s+(?:video|reel|post)\s+every)", re.IGNORECASE),
    re.compile(r"(?:thanks?\s+for\s+(?:watching|following|liking))", re.IGNORECASE),
    re.compile(r"(?:dm\s+(?:me|us)\s+for)", re.IGNORECASE),
    re.compile(r"(?:comment\s+(?:below|your|any))", re.IGNORECASE),
    re.compile(r"(?:share\s+(?:this|with))", re.IGNORECASE),
    re.compile(r"(?:save\s+(?:this|for\s+later))", re.IGNORECASE),
    re.compile(r"(?:link\s+in\s+the\s+(?:bio|description|comments?))", re.IGNORECASE),
    re.compile(r"(?:follow\s+(?:me|us|@)\w*)", re.IGNORECASE),
]

# Screen recording detection patterns
_SCREEN_RECORDING_PATTERNS = [
    re.compile(r"(?:screen\s+recording|screencast|screen\s+capture)", re.IGNORECASE),
    re.compile(r"(?:cursor|mouse|click(?:ed|ing)?)\s+(?:on|at|over)", re.IGNORECASE),
    re.compile(r"(?:tab|window|browser)\s+(?:bar|tab|address)", re.IGNORECASE),
    re.compile(r"(?:url|address)\s+bar\s+(?:shows?|displays?|reads?)", re.IGNORECASE),
    re.compile(r"(?:type(?:ing)?|enter(?:ing)?)\s+(?:in|into)\s+(?:the|a|url|search)", re.IGNORECASE),
]

# --- Platform Names to Skip ---
_PLATFORM_NAMES = frozenset({
    "instagram", "facebook", "twitter", "youtube", "tiktok",
    "linkedin", "reddit", "pinterest", "snapchat", "whatsapp",
    "discord", "slack", "telegram", "signal", "wechat",
})

# --- Generic UI/Web Terms (not entities) ---
_GENERIC_UI_TERMS = frozenset({
    "website", "web app", "mobile app", "landing page", "dashboard",
    "interface", "ui", "ux", "animations", "css", "html", "code",
    "editor", "browser", "screen", "button", "form", "modal",
    "header", "footer", "sidebar", "menu", "navigation",
    "project", "tool", "framework", "library", "platform",
    "app", "application", "software", "service", "api",
})

# --- Known Misspellings (TODO #10) ---
_KNOWN_MISSPELLINGS = {
    "apprite": "appwrite",
    "appwite": "appwrite",
    "appright": "appwrite",
    "contra": "contract",
    "doker": "docker",
    "dockr": "docker",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "angualr": "angular",
    "nxtjs": "nextjs",
    "next.js": "nextjs",
    "tailwindcss": "tailwind",
    "postgrsql": "postgresql",
    "postgres": "postgresql",
    "mongdb": "mongodb",
    "mongo": "mongodb",
    "figma": "figma",
    "canva": "canva",
    "notion": "notion",
    "vercel": "vercel",
    "netlify": "netlify",
    "heroku": "heroku",
    "firebase": "firebase",
    "supabase": "supabase",
    "prisma": "prisma",
    "typeorm": "typeorm",
    "fastapi": "fastapi",
    "flask": "flask",
    "django": "django",
    "express": "express",
    "nodejs": "nodejs",
    "node.js": "nodejs",
    "typescript": "typescript",
    "javscript": "javascript",
    "javasript": "javascript",
    "python": "python",
    "rust": "rust",
    "golang": "go",
    "cplusplus": "cpp",
    "csharp": "csharp",
    "rubyonrails": "ruby on rails",
    "rails": "ruby on rails",
}

# --- URL/Domain Validation Patterns (TODO #3) ---
_DOMAIN_PATTERN = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
)
_SUSPICIOUS_DOMAIN_PATTERNS = [
    re.compile(r"\.(in|co\.in|org\.in)$", re.IGNORECASE),  # Common Indian typos
    re.compile(r"[0-9]+\.com$", re.IGNORECASE),  # Numeric domains
    re.compile(r"^[a-z]{2,}\d+\.com$", re.IGNORECASE),  # Random letter+number
]

# Known correct domains for common entities
_KNOWN_DOMAINS = {
    "github": "github.com",
    "gitlab": "gitlab.com",
    "bitbucket": "bitbucket.org",
    "vercel": "vercel.com",
    "netlify": "netlify.com",
    "heroku": "heroku.com",
    "firebase": "firebase.google.com",
    "supabase": "supabase.com",
    "appwrite": "appwrite.io",
    "figma": "figma.com",
    "canva": "canva.com",
    "notion": "notion.so",
    "linear": "linear.app",
    "posthog": "posthog.com",
    "mixpanel": "mixpanel.com",
    "amplitude": "amplitude.com",
    "segment": "segment.com",
    "algolia": "algolia.com",
    "elasticsearch": "elastic.co",
    "mongodb": "mongodb.com",
    "postgresql": "postgresql.org",
    "mysql": "mysql.com",
    "redis": "redis.io",
    "docker": "docker.com",
    "kubernetes": "kubernetes.io",
    "terraform": "terraform.io",
    "aws": "aws.amazon.com",
    "azure": "azure.microsoft.com",
    "gcp": "cloud.google.com",
}


def _is_ocr_noise(text: str) -> bool:
    """Detect OCR noise patterns (TODO #27)."""
    return any(pattern.search(text) for pattern in _OCR_NOISE_PATTERNS)


def _is_screen_recording(text: str) -> bool:
    """Detect screen recording entities that are not real apps (TODO #27)."""
    return any(pattern.search(text) for pattern in _SCREEN_RECORDING_PATTERNS)


def _fix_misspelling(name: str) -> str:
    """Fix known misspellings (TODO #10)."""
    normalized = name.lower().strip()
    if normalized in _KNOWN_MISSPELLINGS:
        return _KNOWN_MISSPELLINGS[normalized]
    return name


def _fuzzy_match_to_known(name: str, threshold: float = 0.85) -> str | None:
    """Find fuzzy match to known entities. Only matches if significantly different."""
    name_lower = name.lower()
    for known in _KNOWN_MISSPELLINGS.values():
        if name_lower == known:
            return None  # Already correct
        ratio = SequenceMatcher(None, name_lower, known).ratio()
        if ratio >= threshold and name_lower != known:
            return known
    return None


def _validate_domain(name: str) -> str | None:
    """Validate URL/domain transcription errors (TODO #3).

    Returns corrected domain or None if invalid.
    """
    # Check if name looks like a domain
    if not ("." in name and len(name) > 3):
        return name

    # Check against known domains
    name_lower = name.lower().replace(" ", "").replace("-", "")
    for entity, domain in _KNOWN_DOMAINS.items():
        domain_clean = domain.replace(".", "").replace("-", "")
        if name_lower == domain_clean or name_lower.startswith(domain_clean[:5]):
            return domain

    # Check for suspicious patterns
    if _DOMAIN_PATTERN.match(name):
        for pattern in _SUSPICIOUS_DOMAIN_PATTERNS:
            if pattern.search(name):
                logger.debug(f"Suspicious domain detected: {name}")
                return None

    return name


def validate_confidence(entity: dict, min_confidence: float = 0.3) -> bool:
    """Reject entities with too-low confidence (TODO #6)."""
    conf = entity.get("confidence", 0)
    if conf < min_confidence:
        logger.debug(f"Rejected low-confidence entity '{entity.get('name')}': {conf:.2f}")
        return False
    return True


def validate_entity_name(name: str) -> str | None:
    """Validate and clean entity name. Returns None if invalid.

    TODO #2: Filter hallucinated/fabricated entities.
    TODO #3: Fix URL/domain transcription errors.
    """
    if not name or len(name.strip()) < 2:
        return None

    name = name.strip()

    # Skip platform names
    if name.lower() in _PLATFORM_NAMES:
        return None

    # Skip generic terms
    if name.lower() in _GENERIC_UI_TERMS:
        return None

    # Skip numeric facts
    if re.match(r"^[\d]+[%+]?\s+\w", name):
        return None

    # Skip quantities
    if re.match(r"^\d+\+?\s+(animated|free|best|top|new|all|more|less)", name, re.IGNORECASE):
        return None

    # Skip OCR noise
    if _is_ocr_noise(name):
        return None

    # Skip screen recording entities
    if _is_screen_recording(name):
        return None

    # Validate domain/URL
    name = _validate_domain(name)
    if name is None:
        return None

    # Fix known misspellings
    name = _fix_misspelling(name)

    # Fuzzy match to known entities
    fuzzy_match = _fuzzy_match_to_known(name)
    if fuzzy_match:
        logger.debug(f"Fuzzy matched '{name}' → '{fuzzy_match}'")
        return fuzzy_match

    return name


def post_validate_entities(entities: list[dict], source_text: str = "") -> list[dict]:
    """Run all post-extraction validations.

    Args:
        entities: list of entity dicts.
        source_text: optional source transcript for validation.

    Returns:
        Validated and cleaned entities.
    """
    validated = []
    seen_names = set()

    for entity in entities:
        name = entity.get("name", "")

        # Validate name
        clean_name = validate_entity_name(name)
        if clean_name is None:
            logger.debug(f"Filtered invalid entity: '{name}'")
            continue

        # Dedup by normalized name
        name_key = clean_name.lower()
        if name_key in seen_names:
            logger.debug(f"Filtered duplicate entity: '{clean_name}'")
            continue
        seen_names.add(name_key)

        # Validate confidence
        if not validate_confidence(entity):
            continue

        # Source validation (TODO #2) - check if entity name appears in source
        if source_text:
            source_lower = source_text.lower()
            name_lower = clean_name.lower()

            # Entity name should appear in source (fuzzy check)
            if len(name_lower) > 3 and name_lower not in source_lower:
                # Check for partial matches (handles truncation)
                if not any(word in source_lower for word in name_lower.split() if len(word) > 3):
                    logger.debug(f"Entity '{clean_name}' not found in source text")
                    continue

        # Update entity with clean name
        entity = dict(entity)
        entity["name"] = clean_name
        validated.append(entity)

    logger.info(f"Post-validation: {len(entities)} → {len(validated)} entities")
    return validated
