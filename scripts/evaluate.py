#!/usr/bin/env python3
"""Evaluate pipeline output against golden dataset.

Usage:
    python scripts/evaluate.py [--golden-dir tests/fixtures/golden] [--output-dir outputs]

Compares pipeline-produced JSON outputs against expected entities/topics
and reports precision/recall for entity extraction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_golden(golden_dir: Path) -> List[Dict[str, Any]]:
    """Load all golden example JSON files."""
    examples = []
    for f in sorted(golden_dir.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
            data["_file"] = f.name
            examples.append(data)
    return examples


def evaluate_entity_extraction(
    expected: List[Dict[str, str]],
    actual: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Compute precision/recall/F1 for entity extraction.

    Matches by normalized name (case-insensitive).
    """
    expected_names = {e["name"].lower().strip() for e in expected}
    actual_names = {e.get("name", "").lower().strip() for e in actual}

    if not actual_names:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "expected": len(expected_names), "extracted": 0}

    if not expected_names:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "expected": 0, "extracted": len(actual_names)}

    true_positives = len(expected_names & actual_names)
    precision = true_positives / len(actual_names) if actual_names else 0.0
    recall = true_positives / len(expected_names) if expected_names else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "expected": len(expected_names),
        "extracted": len(actual_names),
        "true_positives": true_positives,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate pipeline against golden dataset")
    parser.add_argument("--golden-dir", default="tests/fixtures/golden", help="Golden dataset directory")
    parser.add_argument("--output-dir", default="outputs", help="Pipeline output directory")
    args = parser.parse_args()

    golden_dir = Path(args.golden_dir)
    output_dir = Path(args.output_dir)

    if not golden_dir.exists():
        print(f"Golden directory not found: {golden_dir}")
        return

    examples = load_golden(golden_dir)
    print(f"Loaded {len(examples)} golden examples\n")

    results = []
    for ex in examples:
        print(f"Evaluating: {ex.get('_file', 'unknown')}")
        print(f"  URL: {ex['url']}")
        print(f"  Expected entities: {len(ex.get('expected_entities', []))}")

        # Look for corresponding output file
        output_json = output_dir / f"{ex['url'].split('/')[-1]}.json"
        if output_json.exists():
            with open(output_json) as fh:
                output_data = json.load(fh)
            actual_entities = output_data.get("entities", [])
            metrics = evaluate_entity_extraction(ex.get("expected_entities", []), actual_entities)
            print(f"  Precision: {metrics['precision']}, Recall: {metrics['recall']}, F1: {metrics['f1']}")
            results.append(metrics)
        else:
            print(f"  No output found at {output_json}")
            results.append(None)

    # Summary
    valid = [r for r in results if r is not None]
    if valid:
        avg_f1 = sum(r["f1"] for r in valid) / len(valid)
        print(f"\nOverall avg F1: {avg_f1:.3f}")
    else:
        print("\nNo results to summarize")


if __name__ == "__main__":
    main()
