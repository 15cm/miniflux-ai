"""Deterministic Markdown renderer for structured daily reports."""

from common.config import OutputConfig


def _lines(items):
    return [f"- {item}" for item in items if isinstance(item, str) and item.strip()]


def _source_links(urls, limit):
    return ", ".join(
        f"[Source {index + 1}]({url})"
        for index, url in enumerate(list(dict.fromkeys(urls))[:limit])
    )


def render_daily_news(report: dict, config: OutputConfig) -> str:
    parts = []
    overview = report.get("overview", [])
    if config.include_overview and overview:
        parts.extend(
            [
                "## Today at a glance",
                "",
                *_lines(overview[: config.overview_max_sentences]),
            ]
        )
    sections = report.get("sections", [])
    rendered_sections = []
    for section in sections[: config.max_sections]:
        title, items = section.get("title"), section.get("items", [])
        if not isinstance(title, str) or not items:
            continue
        block = [f"### {title}"]
        for item in items[: config.max_items_per_section]:
            if not isinstance(item, dict) or not item.get("headline"):
                continue
            block.extend(["", f"#### {item['headline']}", ""])
            if item.get("summary"):
                block.append(f"- {item['summary']}")
            if item.get("why_it_matters"):
                block.append(f"- **Why it matters:** {item['why_it_matters']}")
            links = _source_links(
                item.get("source_urls", []), config.max_sources_per_item
            )
            if links and config.include_sources:
                block.append(f"- **Sources:** {links}")
        if len(block) > 1:
            rendered_sections.append(block)
    if rendered_sections:
        parts.extend(["", "## Top developments"])
        for section in rendered_sections:
            parts.extend(["", *section])
    opinions = report.get("opinions", {})
    if (
        config.include_opinions
        and isinstance(opinions, dict)
        and (opinions.get("consensus") or opinions.get("disagreements"))
    ):
        parts.extend(["", "## Opinions and debate"])
        if opinions.get("consensus"):
            parts.extend(["", "### Consensus", "", *_lines(opinions["consensus"])])
        if opinions.get("disagreements"):
            parts.extend(
                ["", "### Disagreements", "", *_lines(opinions["disagreements"])]
            )
    if config.include_watchlist and report.get("watchlist"):
        parts.extend(["", "## Watch next", "", *_lines(report["watchlist"])])
    return "\n".join(parts).strip() + "\n"
