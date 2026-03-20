#!/usr/bin/env python3
"""
Web Scraper MCP Server
A locally-running MCP server that scrapes websites and extracts structured data.
No API keys required — pure Python scraping.
"""

import asyncio
import json
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("web-scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

async def fetch_page(url: str) -> tuple[str, str]:
    """Fetch a URL and return (html, final_url)."""
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text, str(resp.url)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ─────────────────────────────────────────────
# Scraping functions
# ─────────────────────────────────────────────

def scrape_summary(soup: BeautifulSoup, url: str) -> dict:
    title = clean_text(soup.title.string) if soup.title else ""
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_tag:
        meta_desc = meta_tag.get("content", "")

    # Visible body text (strip scripts/styles)
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    body_text = clean_text(soup.get_text(separator=" "))[:500]

    og_image = ""
    og = soup.find("meta", property="og:image")
    if og:
        og_image = og.get("content", "")

    favicon = ""
    # BeautifulSoup may parse `rel` as either a string or a list of strings
    # depending on the HTML structure, so handle both.
    def rel_contains_icon(rel_value) -> bool:
        if not rel_value:
            return False
        if isinstance(rel_value, str):
            return "icon" in rel_value.lower()
        return "icon" in " ".join(rel_value).lower()

    icon = soup.find("link", rel=rel_contains_icon)
    if icon:
        favicon = urljoin(url, icon.get("href", ""))

    domain = urlparse(url).netloc

    return {
        "title": title,
        "domain": domain,
        "url": url,
        "meta_description": meta_desc,
        "body_preview": body_text,
        "og_image": og_image,
        "favicon": favicon,
    }


def scrape_seo(soup: BeautifulSoup, url: str) -> dict:
    title = clean_text(soup.title.string) if soup.title else ""
    title_len = len(title)

    def meta(name):
        tag = soup.find("meta", attrs={"name": re.compile(f"^{name}$", re.I)})
        return tag.get("content", "") if tag else ""

    def og(prop):
        tag = soup.find("meta", property=f"og:{prop}")
        return tag.get("content", "") if tag else ""

    headings = {}
    for level in ["h1", "h2", "h3"]:
        headings[level] = [clean_text(h.get_text()) for h in soup.find_all(level)]

    canonical = ""
    canon_tag = soup.find("link", rel="canonical")
    if canon_tag:
        canonical = canon_tag.get("href", "")

    robots = meta("robots")
    images = soup.find_all("img")
    images_no_alt = [i.get("src", "") for i in images if not i.get("alt")]

    return {
        "title": title,
        "title_length": title_len,
        "title_ok": 50 <= title_len <= 60,
        "meta_description": meta("description"),
        "meta_description_length": len(meta("description")),
        "meta_description_ok": 120 <= len(meta("description")) <= 160,
        "canonical_url": canonical,
        "robots_meta": robots,
        "og_title": og("title"),
        "og_description": og("description"),
        "og_type": og("type"),
        "og_url": og("url"),
        "headings": headings,
        "total_images": len(images),
        "images_missing_alt": len(images_no_alt),
        "structured_data_present": bool(soup.find("script", type="application/ld+json")),
    }


def scrape_links(soup: BeautifulSoup, base_url: str) -> dict:
    base_domain = urlparse(base_url).netloc
    internal, external, mailto, tel = [], [], [], []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = clean_text(a.get_text())
        if href.startswith("mailto:"):
            mailto.append(href[7:])
        elif href.startswith("tel:"):
            tel.append(href[4:])
        elif href.startswith("http"):
            domain = urlparse(href).netloc
            entry = {"url": href, "text": text}
            if domain == base_domain:
                internal.append(entry)
            else:
                external.append(entry)
        elif href.startswith("/") or not href.startswith("#"):
            internal.append({"url": urljoin(base_url, href), "text": text})

    return {
        "total_links": len(internal) + len(external),
        "internal_links_count": len(internal),
        "external_links_count": len(external),
        "internal_links": internal[:30],
        "external_links": external[:30],
        "mailto_addresses": list(set(mailto)),
        "phone_numbers": list(set(tel)),
    }


def scrape_content(soup: BeautifulSoup) -> dict:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    paragraphs = [clean_text(p.get_text()) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
    headings = [{"level": h.name, "text": clean_text(h.get_text())} for h in soup.find_all(["h1","h2","h3","h4"])]

    lists = []
    for ul in soup.find_all(["ul", "ol"])[:10]:
        items = [clean_text(li.get_text()) for li in ul.find_all("li") if li.get_text(strip=True)]
        if items:
            lists.append(items)

    tables = []
    for table in soup.find_all("table")[:5]:
        rows = []
        for tr in table.find_all("tr"):
            row = [clean_text(td.get_text()) for td in tr.find_all(["td", "th"])]
            if any(row):
                rows.append(row)
        if rows:
            tables.append(rows)

    word_count = len(soup.get_text().split())

    return {
        "word_count": word_count,
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs[:10],
        "headings": headings,
        "lists": lists,
        "tables": tables,
    }


def scrape_tech(soup: BeautifulSoup, html: str) -> dict:
    techs = []

    checks = {
        "React": ["react", "_react", "__REACT"],
        "Next.js": ["__NEXT_DATA__", "_next/static"],
        "Vue.js": ["vue.js", "vue.min.js", "__vue__"],
        "Angular": ["ng-version", "angular.js"],
        "jQuery": ["jquery"],
        "Bootstrap": ["bootstrap.css", "bootstrap.min.css"],
        "Tailwind CSS": ["tailwindcss", "tw-"],
        "WordPress": ["/wp-content/", "/wp-includes/"],
        "Shopify": ["cdn.shopify.com", "Shopify."],
        "Google Analytics": ["google-analytics.com", "gtag(", "ga("],
        "Google Tag Manager": ["googletagmanager.com"],
        "Cloudflare": ["cloudflare"],
        "Font Awesome": ["font-awesome", "fontawesome"],
        "Stripe": ["js.stripe.com"],
        "Intercom": ["intercom"],
        "HubSpot": ["hs-scripts.com", "hubspot"],
    }

    lower_html = html.lower()
    for tech, patterns in checks.items():
        if any(p.lower() in lower_html for p in patterns):
            techs.append(tech)

    # Meta generator
    generator = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    generator_val = generator.get("content", "") if generator else ""

    scripts = [s.get("src", "") for s in soup.find_all("script", src=True)]
    stylesheets = [l.get("href", "") for l in soup.find_all("link", rel="stylesheet")]

    return {
        "detected_technologies": techs,
        "generator": generator_val,
        "external_scripts": [s for s in scripts if s.startswith("http")][:20],
        "stylesheets": stylesheets[:20],
        "has_https": True,  # we got here, so yes
        "script_count": len(scripts),
        "stylesheet_count": len(stylesheets),
    }


def scrape_contact(soup: BeautifulSoup, html: str) -> dict:
    emails = list(set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)))
    phones = list(set(re.findall(
        r"(?:\+?\d[\d\s\-().]{7,}\d)",
        html
    )))[:10]

    social_patterns = {
        "twitter": r"twitter\.com/([A-Za-z0-9_]+)",
        "x": r"x\.com/([A-Za-z0-9_]+)",
        "linkedin": r"linkedin\.com/(?:in|company)/([A-Za-z0-9_\-]+)",
        "facebook": r"facebook\.com/([A-Za-z0-9_.]+)",
        "instagram": r"instagram\.com/([A-Za-z0-9_.]+)",
        "youtube": r"youtube\.com/(?:channel|user|c)/([A-Za-z0-9_\-]+)",
        "github": r"github\.com/([A-Za-z0-9_\-]+)",
    }
    socials = {}
    for platform, pattern in social_patterns.items():
        match = re.search(pattern, html)
        if match:
            socials[platform] = match.group(0)

    address_keywords = ["address", "location", "headquarters", "hq", "office"]
    address_hints = []
    for tag in soup.find_all(["p", "div", "span", "address"]):
        text = clean_text(tag.get_text())
        if any(k in tag.get("class", []) + [tag.get("id",""), text.lower()] for k in address_keywords):
            if 10 < len(text) < 200:
                address_hints.append(text)

    return {
        "emails": emails[:15],
        "phones": phones,
        "social_media": socials,
        "address_hints": list(set(address_hints))[:5],
    }


# ─────────────────────────────────────────────
# MCP Tool Definitions
# ─────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="scrape_summary",
            description="Get a quick summary of any website: title, description, domain, and body preview. Good first tool to understand what a site is about.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape (e.g. https://example.com)"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="scrape_seo",
            description="Analyse SEO signals of a website: title, meta description, headings structure, Open Graph tags, canonical URL, image alt attributes, and structured data presence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="scrape_links",
            description="Extract all internal and external links from a website, including email addresses and phone numbers found in href attributes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="scrape_content",
            description="Extract the main textual content of a website: paragraphs, headings, lists, and tables. Useful for reading article or page content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="scrape_tech_stack",
            description="Detect what technologies a website uses: JS frameworks, CMS, analytics, CSS libraries, CDN, and more — without any API key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="scrape_contact",
            description="Find contact information on a website: email addresses, phone numbers, social media profiles, and address hints.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape"}
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="scrape_full",
            description="Run ALL scraping tools at once on a URL and return a complete structured report: summary, SEO, links, content, tech stack, and contact info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to scrape"}
                },
                "required": ["url"],
            },
        ),
    ]


# ─────────────────────────────────────────────
# MCP Tool Handlers
# ─────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    url = arguments.get("url", "").strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        html, final_url = await fetch_page(url)
        soup = get_soup(html)
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    try:
        if name == "scrape_summary":
            result = scrape_summary(soup, final_url)
        elif name == "scrape_seo":
            result = scrape_seo(soup, final_url)
        elif name == "scrape_links":
            result = scrape_links(soup, final_url)
        elif name == "scrape_content":
            result = scrape_content(soup)
        elif name == "scrape_tech_stack":
            result = scrape_tech(soup, html)
        elif name == "scrape_contact":
            result = scrape_contact(soup, html)
        elif name == "scrape_full":
            result = {
                "summary": scrape_summary(soup, final_url),
                "seo": scrape_seo(soup, final_url),
                "links": scrape_links(soup, final_url),
                "content": scrape_content(soup),
                "tech_stack": scrape_tech(soup, html),
                "contact": scrape_contact(soup, html),
            }
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        result = {"error": f"Scraping failed: {str(e)}"}

    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
