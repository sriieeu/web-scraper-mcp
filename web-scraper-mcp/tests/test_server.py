import json
import unittest
from unittest.mock import AsyncMock, patch

import server


HTML = """<!doctype html>
<html>
<head>
  <title>Example Title That Is Long Enough For Seo Quality Purposes</title>
  <meta name="description" content="This is a meta description used for testing SEO length constraints and extraction logic in the web scraper module for robust unit testing purposes."/>
  <link rel="canonical" href="https://example.com/canonical"/>
  <meta name="robots" content="index,follow"/>
  <meta property="og:title" content="OG Title"/>
  <meta property="og:description" content="OG Description"/>
  <meta property="og:type" content="website"/>
  <meta property="og:url" content="https://example.com/og-url"/>
  <meta property="og:image" content="https://example.com/og.png"/>
  <link rel="icon" href="/favicon.ico"/>
  <meta name="generator" content="TestCMS 1.0"/>
  <link rel="stylesheet" href="https://cdn.example.com/app.css"/>
  <link rel="stylesheet" href="/local.css"/>
  <script type="application/ld+json">{ "a": 1 }</script>
  <script src="https://cdn.example.com/react.production.min.js"></script>
  <script src="https://cdn.example.com/another.js"></script>
  <script src="/_next/static/chunk.js"></script>
  <script src="https://www.googletagmanager.com/gtm.js?id=GTM-TEST"></script>
  <script>window.dataLayer=[]; function gtag(){}</script>
  <script>console.log("noise");</script>
  <style>.hidden{display:none;}</style>
</head>
<body>
  <nav>
    <a href="/about">About Us</a>
    <a href="https://example.com/contact">Contact</a>
    <a href="https://other.com/x">Other</a>
    <a href="mailto:hello@example.com">Email</a>
    <a href="tel:+1-555-123-4567">Call</a>
    <a href="#section">Ignore</a>
  </nav>

  <h1>Main Heading</h1>
  <h2>Sub Heading</h2>
  <h3>Minor Heading</h3>

  <div class="address">123 Example St, Example City</div>
  <div class="tailwindcss tw-abc"></div>
  <i class="fa fa-font-awesome font-awesome"></i>
  <img src="/img1.jpg" alt="desc1"/>
  <img src="/img2.jpg"/>

  <p>Short paragraph.</p>
  <p>This is a long paragraph designed to exceed forty characters so the scraper keeps it when extracting page content for testing.</p>

  <ul>
    <li>First item</li>
    <li>Second item</li>
  </ul>

  <table>
    <tr><th>Col1</th><th>Col2</th></tr>
    <tr><td>A</td><td>B</td></tr>
  </table>

  <p>Extra content for more words in the body preview and word count computations.</p>
</body>
</html>
"""


class TestScrapeHelpers(unittest.TestCase):
    def test_clean_text_normalizes_whitespace(self):
        self.assertEqual(server.clean_text("a   b\nc\t  d"), "a b c d")


class TestScrapers(unittest.TestCase):
    def setUp(self):
        self.base_url = "https://example.com/page"
        self.soup = server.get_soup(HTML)

    def test_scrape_summary_extracts_title_meta_domain_and_previews(self):
        result = server.scrape_summary(self.soup, self.base_url)

        self.assertEqual(result["domain"], "example.com")
        self.assertEqual(result["title"], "Example Title That Is Long Enough For Seo Quality Purposes")
        self.assertIn("meta description used for testing SEO length constraints", result["meta_description"])
        self.assertTrue(result["body_preview"])
        self.assertNotIn("console.log", result["body_preview"])

        # Relative icon should be absolutized against the provided URL.
        self.assertEqual(result["favicon"], "https://example.com/favicon.ico")

        self.assertEqual(result["og_image"], "https://example.com/og.png")
        self.assertEqual(result["url"], self.base_url)

    def test_scrape_seo_computes_lengths_flags_and_structure(self):
        result = server.scrape_seo(self.soup, self.base_url)

        self.assertEqual(result["canonical_url"], "https://example.com/canonical")
        self.assertEqual(result["robots_meta"], "index,follow")
        self.assertEqual(result["title_length"], len(result["title"]))
        self.assertTrue(result["title_ok"])
        self.assertTrue(result["meta_description_ok"])

        self.assertTrue(result["structured_data_present"])

        self.assertIn("Main Heading", result["headings"]["h1"])
        self.assertEqual(result["total_images"], 2)
        self.assertEqual(result["images_missing_alt"], 1)

    def test_scrape_links_categorizes_internal_external_mailto_tel(self):
        result = server.scrape_links(self.soup, self.base_url)

        self.assertEqual(result["internal_links_count"], 2)  # /about and https://example.com/contact
        self.assertEqual(result["external_links_count"], 1)  # https://other.com/x
        self.assertEqual(result["total_links"], 3)

        internal_urls = {x["url"] for x in result["internal_links"]}
        self.assertIn("https://example.com/about", internal_urls)
        self.assertIn("https://example.com/contact", internal_urls)

        external_urls = {x["url"] for x in result["external_links"]}
        self.assertEqual(external_urls, {"https://other.com/x"})

        self.assertEqual(set(result["mailto_addresses"]), {"hello@example.com"})
        self.assertEqual(set(result["phone_numbers"]), {"+1-555-123-4567"})

    def test_scrape_content_extracts_paragraphs_headings_lists_tables_and_word_count(self):
        # scrape_content mutates soup by decompose()ing tags; use a fresh soup here.
        soup = server.get_soup(HTML)
        result = server.scrape_content(soup)

        self.assertGreaterEqual(result["word_count"], 1)
        self.assertGreaterEqual(result["paragraph_count"], 2)
        self.assertEqual(result["headings"][0]["level"], "h1")
        self.assertEqual(result["headings"][0]["text"], "Main Heading")

        self.assertEqual(result["lists"][0], ["First item", "Second item"])

        self.assertGreaterEqual(len(result["tables"]), 1)
        # First row should contain headers.
        self.assertEqual(result["tables"][0][0], ["Col1", "Col2"])

        # Ensure the long paragraph passes the > 40 char filter.
        self.assertTrue(
            any(
                "exceed forty characters" in p
                for p in result["paragraphs"]
            )
        )

    def test_scrape_tech_detects_frameworks_analytics_and_counts(self):
        result = server.scrape_tech(self.soup, HTML)

        self.assertIn("React", result["detected_technologies"])
        self.assertIn("Google Analytics", result["detected_technologies"])
        self.assertIn("Google Tag Manager", result["detected_technologies"])
        self.assertIn("Tailwind CSS", result["detected_technologies"])
        self.assertIn("Font Awesome", result["detected_technologies"])

        self.assertEqual(result["generator"], "TestCMS 1.0")
        self.assertEqual(result["has_https"], True)
        # Counts only <script src="..."> tags (not inline scripts / JSON-LD).
        self.assertEqual(result["script_count"], 4)
        # Stylesheets: 2 total (one http(s), one relative)
        self.assertEqual(result["stylesheet_count"], 2)

    def test_scrape_contact_extracts_emails_phones_social_and_address_hints(self):
        result = server.scrape_contact(self.soup, HTML)

        self.assertEqual(set(result["emails"]), {"hello@example.com"})
        self.assertEqual(set(result["phones"]), {"+1-555-123-4567"})

        # This fixture does not include social profiles in the URL,
        # so only address_hints should be populated.
        self.assertTrue(result["address_hints"])
        self.assertTrue(any("123 Example St" in x for x in result["address_hints"]))


class TestCallTool(unittest.IsolatedAsyncioTestCase):
    async def test_call_tool_success_dispatches_and_returns_json(self):
        async def fake_fetch_page(url: str):
            # call_tool should normalize "example.com/page" -> "https://example.com/page"
            self.assertEqual(url, "https://example.com/page")
            return HTML, "https://example.com/final"

        with patch.object(server, "fetch_page", new=AsyncMock(side_effect=fake_fetch_page)) as mocked:
            res = await server.call_tool(name="scrape_summary", arguments={"url": "example.com/page"})
            self.assertEqual(len(res), 1)

            data = json.loads(res[0].text)
            self.assertEqual(data["domain"], "example.com")
            self.assertIn("title", data)

            mocked.assert_awaited_once()

    async def test_call_tool_returns_error_on_fetch_failure(self):
        with patch.object(server, "fetch_page", new=AsyncMock(side_effect=Exception("boom"))):
            res = await server.call_tool(name="scrape_summary", arguments={"url": "https://example.com"})
            self.assertEqual(len(res), 1)
            data = json.loads(res[0].text)
            self.assertIn("error", data)

    async def test_call_tool_unknown_tool_returns_error(self):
        async def fake_fetch_page(url: str):
            return HTML, "https://example.com/final"

        with patch.object(server, "fetch_page", new=AsyncMock(side_effect=fake_fetch_page)):
            res = await server.call_tool(name="nonexistent_tool", arguments={"url": "https://example.com"})
            self.assertEqual(len(res), 1)
            data = json.loads(res[0].text)
            self.assertIn("error", data)

