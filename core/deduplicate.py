"""Deterministic daily-news grouping before LLM work."""

from difflib import SequenceMatcher
import re
import unicodedata


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def deduplicate_entries(entries: list[dict], threshold: float = 0.85) -> list[dict]:
    groups = []
    for entry in entries:
        title, url, category = (
            normalize_title(entry.get("title", "")),
            entry.get("url", ""),
            entry.get("category", ""),
        )
        matched = None
        for group in groups:
            representative = group["representative"]
            same_url = url and url == representative.get("url", "")
            similarity = SequenceMatcher(
                None, title, normalize_title(representative.get("title", ""))
            ).ratio()
            if same_url or (
                category == representative.get("category", "")
                and similarity >= threshold
            ):
                matched = group
                break
        if matched:
            matched["sources"].append(entry)
            if entry.get("datetime", entry.get("published_at", "")) > matched[
                "representative"
            ].get("datetime", matched["representative"].get("published_at", "")):
                matched["representative"] = entry
        else:
            groups.append({"representative": entry, "sources": [entry]})
    output = []
    for group in groups:
        item = dict(group["representative"])
        item["source_entries"] = group["sources"]
        item["source_urls"] = list(
            dict.fromkeys(x.get("url", "") for x in group["sources"] if x.get("url"))
        )
        item["source_entry_ids"] = [
            str(x.get("entry_id", x.get("id", ""))) for x in group["sources"]
        ]
        output.append(item)
    return output
