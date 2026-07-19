import re
import unicodedata
from difflib import SequenceMatcher


def normalize_entity(name: str) -> str:
    name = name.strip().lower()
    name = unicodedata.normalize("NFKD", name)
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def entities_are_similar(a: str, b: str, threshold: float = 0.8) -> bool:
    na = normalize_entity(a)
    nb = normalize_entity(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def deduplicate_entities(entities: list[str], threshold: float = 0.8) -> list[str]:
    if not entities:
        return []
    normalized = {}
    for e in entities:
        n = normalize_entity(e)
        matched = False
        for existing_n in normalized:
            if entities_are_similar(n, existing_n, threshold):
                if len(e) > len(normalized[existing_n]):
                    normalized[existing_n] = e
                matched = True
                break
        if not matched:
            normalized[n] = e
    return list(normalized.values())
