"""Output format validator and fixer (TODO #20, #21, #22, #24, #25).

Ensures output has correct section ordering, titles, and project placement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class OutputFormat:
    """Structured output format for a video summary."""
    title: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    guide_title: str = ""
    guide_steps: list[str] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    source_url: str = ""


# Known project indicators
_PROJECT_INDICATORS = [
    re.compile(r"build\s+(a|your|the)\s+", re.IGNORECASE),
    re.compile(r"create\s+(a|your|the)\s+", re.IGNORECASE),
    re.compile(r"project\s*:", re.IGNORECASE),
    re.compile(r"app\s*:", re.IGNORECASE),
    re.compile(r"repository\s*:", re.IGNORECASE),
    re.compile(r"github\.com/", re.IGNORECASE),
]


def _is_project_entity(entity: dict) -> bool:
    """Check if an entity looks like a project (TODO #24)."""
    name = entity.get("name", "")
    desc = entity.get("description", "") or entity.get("context", "")
    etype = entity.get("type", "")

    # Check type
    if etype in ("web_app", "mobile_app"):
        return True

    # Check description for project indicators
    return any(p.search(desc) or p.search(name) for p in _PROJECT_INDICATORS)


def _has_guide_title(text: str) -> bool:
    """Check if text has a proper guide title (TODO #21)."""
    if not text:
        return False
    lines = text.strip().split("\n")
    for line in lines[:3]:
        line = line.strip()
        if line.startswith("#") or "step" in line.lower() or "guide" in line.lower():
            return True
    return False


def _ensure_guide_title(guide_steps: list[str], entity_name: str = "") -> str:
    """Generate a guide title if missing (TODO #21)."""
    if guide_steps and not _has_guide_title(guide_steps[0]):
        title = f"How to Use {entity_name}" if entity_name else "Step-by-Step Guide"
        return title
    return ""


def validate_output_ordering(
    summary: str,
    guide_section: str,
) -> tuple[str, str]:
    """Ensure summary comes before guide (TODO #22).

    Returns:
        (summary, guide_section) in correct order.
    """
    if not summary or not guide_section:
        return summary, guide_section

    # If guide appears before summary, swap them
    summary_pos = summary.lower().find("summary")
    guide_pos = guide_section.lower().find("step")

    if guide_pos >= 0 and summary_pos >= 0 and guide_pos < summary_pos:
        logger.debug("Swapping guide and summary sections")
        return guide_section, summary

    return summary, guide_section


def _add_build_instructions(entity: dict) -> dict:
    """Add build instructions to project descriptions if missing (TODO #25)."""
    desc = entity.get("description", "") or entity.get("context", "")

    if not desc:
        return entity

    # Check if build instructions already exist
    build_indicators = ["install", "npm", "clone", "setup", "run", "build", "deploy"]
    if any(ind in desc.lower() for ind in build_indicators):
        return entity

    # Add generic build note
    entity["description"] = desc.rstrip(".") + ". See repository for setup instructions."
    return entity


def format_output(
    entities: list[dict],
    summary: str = "",
    key_points: list[str] | None = None,
    source_url: str = "",
) -> OutputFormat:
    """Format output with correct structure (TODO #20-#25).

    - Summary before guide
    - Guide has title
    - Projects in separate section
    - Project descriptions have build instructions
    """
    output = OutputFormat()
    output.source_url = source_url
    output.summary = summary
    output.key_points = key_points or []

    # Separate projects from regular entities
    regular_entities = []
    for entity in entities:
        if _is_project_entity(entity):
            entity = _add_build_instructions(entity)
            output.projects.append(entity)
        else:
            regular_entities.append(entity)

    output.entities = regular_entities

    # Ensure guide has title if steps exist
    if output.guide_steps:
        title = _ensure_guide_title(output.guide_steps)
        if title:
            output.guide_title = title

    logger.debug(
        f"Formatted output: {len(output.entities)} entities, "
        f"{len(output.projects)} projects, "
        f"{len(output.key_points)} key points"
    )
    return output
