import json
from datetime import datetime
import markdown
from feedgen.feed import FeedGenerator
from common.config import Config
from core.storage import SummaryStore
from myapp import app

config = Config()


@app.route("/rss/ai-news", methods=["GET"])
def miniflux_ai_news():
    fg = FeedGenerator()
    fg.id("https://ai-news.miniflux")
    fg.title("֎Newsᴬᴵ for you")
    fg.subtitle("Powered by miniflux-ai")
    fg.author({"name": "miniflux-ai"})
    fg.link(href="https://ai-news.miniflux", rel="self")
    reports = SummaryStore(config.storage.path).latest_daily_reports(
        config.storage.report_retention_count
    )
    if not reports and not config.ai_news_batching.enabled:
        try:
            with open("ai_news.json", encoding="utf8") as file:
                legacy = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            legacy = ""
        if legacy:
            reports = [
                {
                    "id": "legacy",
                    "title": "Newsᴬᴵ for you",
                    "content_markdown": legacy,
                    "created_at": datetime.now().isoformat(),
                }
            ]
    if not reports:
        welcome = fg.add_entry()
        welcome.id("https://ai-news.miniflux")
        welcome.link(href="https://ai-news.miniflux")
        welcome.title("Welcome to Newsᴬᴵ")
        welcome.description(markdown.markdown("Welcome to Newsᴬᴵ"))
    for report in reports:
        entry = fg.add_entry()
        entry.id("https://ai-news.miniflux/reports/" + report["id"])
        entry.link(href="https://ai-news.miniflux/reports/" + report["id"])
        entry.title(report["title"])
        entry.description(markdown.markdown(report["content_markdown"]))
        entry.pubDate(report["created_at"])
    return fg.rss_str(pretty=True)
