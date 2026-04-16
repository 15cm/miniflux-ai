import importlib.util
import unittest
import os

# Load render_input directly to avoid triggering core/__init__.py
# which imports heavy dependencies not needed for these unit tests.
_render_input_path = os.path.join(os.path.dirname(__file__), '..', 'core', 'render_input.py')
_spec = importlib.util.spec_from_file_location('render_input', _render_input_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
render_agent_input = _mod.render_agent_input
render_ai_news_input = _mod.render_ai_news_input
DEFAULT_AGENT_INPUT = _mod.DEFAULT_AGENT_INPUT
DEFAULT_AI_NEWS_INPUT = _mod.DEFAULT_AI_NEWS_INPUT


SAMPLE_ENTRY = {
    "id": 1790,
    "title": "Entry Title",
    "url": "http://example.org/article.html",
    "author": "Author Name",
    "content": "<p>Hello <strong>world</strong></p>",
    "published_at": 1736200000,
    "status": "unread",
    "starred": True,
    "tags": ["tag1", "tag2"],
}

SAMPLE_ENTRIES = [
    {
        "datetime": "2024-01-01T00:00:00",
        "category": "Tech",
        "title": "Article One",
        "content": "Summary of article one.",
        "url": "https://example.org/1",
    },
    {
        "datetime": "2024-01-01T01:00:00",
        "category": "Science",
        "title": "Article Two",
        "content": "Summary of article two.",
        "url": "https://example.org/2",
    },
]


class TestRenderAgentInput(unittest.TestCase):

    def test_default_template_markdownifies_content(self):
        """Default template renders markdownified content."""
        result = render_agent_input(DEFAULT_AGENT_INPUT, SAMPLE_ENTRY)
        self.assertIn("Hello", result)
        self.assertIn("world", result)
        self.assertNotIn("<p>", result)
        self.assertNotIn("<strong>", result)

    def test_custom_template_renders_fields(self):
        """Custom template can access entry fields."""
        result = render_agent_input("Title: {{ title }}\nURL: {{ url }}", SAMPLE_ENTRY)
        self.assertEqual(result, "Title: Entry Title\nURL: http://example.org/article.html")

    def test_content_pre_markdownified_in_template(self):
        """content is already markdownified when accessed in template."""
        result = render_agent_input("{{ content }}", SAMPLE_ENTRY)
        self.assertIn("Hello", result)
        self.assertNotIn("<p>", result)
        self.assertNotIn("<strong>", result)

    def test_template_with_all_fields(self):
        """Template can access author, tags, etc."""
        result = render_agent_input("Author: {{ author }}, Tags: {{ tags | join(', ') }}", SAMPLE_ENTRY)
        self.assertEqual(result, "Author: Author Name, Tags: tag1, tag2")

    def test_empty_content(self):
        """Entry with no content → empty string from default template."""
        result = render_agent_input(DEFAULT_AGENT_INPUT, {})
        self.assertEqual(result, "")


class TestRenderAiNewsInput(unittest.TestCase):

    def test_default_joins_content_with_newlines(self):
        """Default template produces newline-joined content of all entries."""
        result = render_ai_news_input(DEFAULT_AI_NEWS_INPUT, SAMPLE_ENTRIES)
        self.assertEqual(result, "Summary of article one.\nSummary of article two.")

    def test_custom_template_iterates_entries(self):
        """Custom template can loop over entries."""
        tmpl = "{% for e in entries %}{{ e.title }}: {{ e.content }}\n{% endfor %}"
        result = render_ai_news_input(tmpl, SAMPLE_ENTRIES)
        self.assertIn("Article One: Summary of article one.", result)
        self.assertIn("Article Two: Summary of article two.", result)

    def test_total_variable_available(self):
        """Template can access total count."""
        result = render_ai_news_input("Total: {{ total }}", SAMPLE_ENTRIES)
        self.assertEqual(result, "Total: 2")

    def test_empty_entries_list(self):
        """Default template with empty entries → empty string."""
        result = render_ai_news_input(DEFAULT_AI_NEWS_INPUT, [])
        self.assertEqual(result, "")

    def test_template_access_entry_fields(self):
        """Template can access category, url, etc."""
        result = render_ai_news_input("{{ entries[0].category }}", SAMPLE_ENTRIES)
        self.assertEqual(result, "Tech")


class TestDefaultConstants(unittest.TestCase):

    def test_default_agent_input_renders_content(self):
        """DEFAULT_AGENT_INPUT renders markdownified content."""
        result = render_agent_input(DEFAULT_AGENT_INPUT, SAMPLE_ENTRY)
        self.assertIn("Hello", result)
        self.assertNotIn("<p>", result)

    def test_default_ai_news_input_joins_content(self):
        """DEFAULT_AI_NEWS_INPUT joins entry content with newlines."""
        result = render_ai_news_input(DEFAULT_AI_NEWS_INPUT, SAMPLE_ENTRIES)
        self.assertEqual(result, "Summary of article one.\nSummary of article two.")


if __name__ == '__main__':
    unittest.main()
