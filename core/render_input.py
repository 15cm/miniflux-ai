from jinja2 import Environment, BaseLoader
from markdownify import markdownify as md

DEFAULT_AGENT_INPUT = "{{ content }}"
DEFAULT_AI_NEWS_INPUT = "{{ entries | map(attribute='content') | join('\n') }}"


def _make_env():
    return Environment(loader=BaseLoader())


def render_agent_input(template_str: str, entry: dict) -> str:
    """Render Jinja input template for an agent using entry data as context.

    ``content`` is pre-markdownified before being passed to the template.
    Context fields match the miniflux entry structure (see agents.json).
    """
    context = {**entry, 'content': md(entry.get('content', ''))}
    return _make_env().from_string(template_str).render(**context)


def render_ai_news_input(template_str: str, entries: list) -> str:
    """Render Jinja input template for ai_news using entries list as context.

    Context: ``entries`` (list), ``total`` (int).
    """
    return _make_env().from_string(template_str).render(entries=entries, total=len(entries))
