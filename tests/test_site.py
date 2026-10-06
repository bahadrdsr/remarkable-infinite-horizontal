import json
from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.meta = {}
        self.canonical = ""
        self.json_ld = []
        self.in_json_ld = False
        self.current_script = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            key = values.get("name") or values.get("property")
            if key:
                self.meta[key] = values.get("content", "")
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href", "")
        elif tag == "script" and values.get("type") == "application/ld+json":
            self.in_json_ld = True
            self.current_script = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_json_ld:
            self.json_ld.append(json.loads("".join(self.current_script)))
            self.in_json_ld = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_json_ld:
            self.current_script.append(data)


class SiteTests(unittest.TestCase):
    def test_search_metadata_and_structured_data(self):
        parser = MetadataParser()
        parser.feed((ROOT / "site/index.html").read_text())
        self.assertIn("Infinite Canvas", parser.title)
        self.assertIn("reMarkable Paper Pure", parser.title)
        self.assertGreater(len(parser.meta["description"]), 80)
        self.assertEqual(
            parser.canonical,
            "https://bahadrdsr.github.io/remarkable-infinite-horizontal/",
        )
        types = {item["@type"] for item in parser.json_ld}
        self.assertEqual(types, {"SoftwareApplication", "FAQPage"})
        faq = next(item for item in parser.json_ld if item["@type"] == "FAQPage")
        self.assertGreaterEqual(len(faq["mainEntity"]), 4)

    def test_readme_contains_plain_language_search_terms(self):
        readme = (ROOT / "README.md").read_text()
        for phrase in (
            "Infinite Canvas for reMarkable Paper Pure",
            "reMarkable mod",
            "Beginner Windows installation",
            "Does reMarkable Paper Pure have an infinite canvas?",
        ):
            self.assertIn(phrase, readme)

    def test_robots_and_sitemap_use_the_pages_url(self):
        url = "https://bahadrdsr.github.io/remarkable-infinite-horizontal/"
        self.assertIn(url + "sitemap.xml", (ROOT / "site/robots.txt").read_text())
        self.assertIn(url, (ROOT / "site/sitemap.xml").read_text())


if __name__ == "__main__":
    unittest.main()
