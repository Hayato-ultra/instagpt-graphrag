"""Generate TypeScript types from Pydantic models (TODO #47).

Usage: python -m scripts.generate_ts_types
Output: src/types/generated.ts
"""
import sys
from pathlib import Path
from typing import get_type_hints
import datetime


# Map Python types to TypeScript
TYPE_MAP = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "list": "Array<any>",
    "dict": "Record<string, any>",
    "datetime": "string",
    "date": "string",
    "bytes": "string",
    "any": "any",
    "None": "void",
}


def python_type_to_ts(tp) -> str:
    """Convert a Python type annotation to TypeScript type string."""
    name = getattr(tp, "__name__", None) or getattr(tp, "_name", None) or str(tp)

    if name in TYPE_MAP:
        return TYPE_MAP[name]

    # Handle list[X]
    if name == "list" or (hasattr(tp, "__origin__") and tp.__origin__ is list):
        args = getattr(tp, "__args__", None)
        if args:
            inner = python_type_to_ts(args[0])
            return f"Array<{inner}>"
        return "Array<any>"

    # Handle dict[K, V]
    if name == "dict" or (hasattr(tp, "__origin__") and tp.__origin__ is dict):
        return "Record<string, any>"

    # Handle Optional[X] → X | null
    if name == "Optional" or (hasattr(tp, "__origin__") and str(tp.__origin__) == "typing.Union"):
        args = getattr(tp, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            ts_types = " | ".join(python_type_to_ts(a) for a in non_none)
            return f"({ts_types}) | null"
        return "null"

    # Handle enums
    if hasattr(tp, "__members__"):
        return "string"

    return "any"


def generate_interface(class_name: str, fields: dict) -> str:
    """Generate a TypeScript interface from class fields."""
    lines = [f"export interface {class_name} {{"]
    for field_name, field_type in fields.items():
        ts_type = python_type_to_ts(field_type)
        # Make optional fields have ?
        lines.append(f"  {field_name}: {ts_type};")
    lines.append("}")
    return "\n".join(lines)


def main():
    from src.config.models import (
        ExtractedContent,
        DocumentChunk,
        EnrichedEntity,
        ExtractedRelationship,
        CategorizedItem,
        ProcessingResult,
    )

    models = [
        ("ExtractedContent", ExtractedContent),
        ("DocumentChunk", DocumentChunk),
        ("EnrichedEntity", EnrichedEntity),
        ("ExtractedRelationship", ExtractedRelationship),
        ("CategorizedItem", CategorizedItem),
        ("ProcessingResult", ProcessingResult),
    ]

    interfaces = []
    for class_name, model_cls in models:
        hints = get_type_hints(model_cls)
        interfaces.append(generate_interface(class_name, hints))

    ts_content = (
        "// Auto-generated from Pydantic models — DO NOT EDIT\n"
        "// Run: python -m scripts.generate_ts_types\n\n"
        + "\n\n".join(interfaces)
        + "\n"
    )

    output_path = Path("src/types/generated.ts")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ts_content)
    count = len(interfaces)
    print(f"Generated {count} interfaces -> {output_path}")


if __name__ == "__main__":
    main()
