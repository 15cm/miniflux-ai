from jinja2 import Environment, BaseLoader

DEFAULT_AGENT_INPUT = "{{ content }}"
DEFAULT_AI_NEWS_INPUT = (
    '{\n'
    '{%- for category, group in entries | groupby("category") %}\n'
    '  "{{ category }}": {{ group | list | tojson }}{% if not loop.last %},{% endif %}\n'
    '{%- endfor %}\n'
    '}'
)


def _make_env():
    return Environment(loader=BaseLoader())


def render_agent_input(template_str: str, entry: dict) -> str:
    """Render Jinja input template for an agent using entry data as context.

    Context fields match the miniflux entry structure (see agents.json).
    """
    return _make_env().from_string(template_str).render(**entry)


def render_ai_news_input(template_str: str, entries: list) -> str:
    """Render Jinja input template for ai_news using entries list as context.

    Context: ``entries`` (list), ``total`` (int).
    Each entry has: datetime, category, title, content, url, tags.
    """
    return _make_env().from_string(template_str).render(entries=entries, total=len(entries))
