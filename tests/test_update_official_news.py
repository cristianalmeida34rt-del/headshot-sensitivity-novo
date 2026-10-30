import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from update_official_news import (  # noqa: E402
    NewsListingParser,
    NewsSyncError,
    bump_gradle_version,
    create_release_notes,
    parse_listing,
)


FIXTURE = """<!doctype html><html><body>
<ul class="news-list">
  <li id="1731" class="news-item news-elem">
    <a href="/pt/article/1731/" class="news-link">
      <span class="news-time">22/10/2026</span>
      <span class="news-category">Anúncios</span>
      <h4 class="news-title">Desvende O Oculto: Free Fire traz novidades assustadoras neste Halloween</h4>
    </a>
  </li>
</ul></body></html>"""


class OfficialNewsParserTests(unittest.TestCase):
    def test_parses_article_card_and_official_link(self):
        item = parse_listing(FIXTURE)[0]
        self.assertEqual(item["id"], 1731)
        self.assertEqual(item["date"], "22/10/2026")
        self.assertEqual(item["category"], "Anúncios")
        self.assertIn("Halloween", item["title"])
        self.assertEqual(item["url"], "https://ff.garena.com/pt/article/1731/")

    def test_rejects_non_official_article_url(self):
        fixture = FIXTURE.replace("/pt/article/1731/", "https://example.com/pt/article/1731/")
        with self.assertRaises(NewsSyncError):
            parse_listing(fixture)

    def test_rejects_invalid_listing_date(self):
        fixture = FIXTURE.replace("22/10/2026", "ontem")
        with self.assertRaises(NewsSyncError):
            parse_listing(fixture)

    def test_patch_version_increment_from_two_part_version(self):
        gradle = "versionCode 5\nversionName '2.1'\n"
        updated, code, name = bump_gradle_version(gradle)
        self.assertEqual((code, name), (6, "2.1.1"))
        self.assertIn("versionCode 6", updated)
        self.assertIn("versionName '2.1.1'", updated)

    def test_release_notes_link_only_to_official_item(self):
        notes = create_release_notes([{
            "title": "Novidade [oficial]",
            "url": "https://ff.garena.com/pt/article/1731/",
            "date": "22/10/2026",
        }], "2.1.1")
        self.assertIn("2.1.1", notes)
        self.assertIn("https://ff.garena.com/pt/article/1731/", notes)
        self.assertIn("não é necessário desinstalar", notes)


if __name__ == "__main__":
    unittest.main()
