# Web Scraper MCP Server

> A locally-running MCP (Model Context Protocol) server that scrapes any website and returns clean, structured data — directly inside Claude Desktop.
No API keys. No cloud. No browser automation. Pure Python.

Overview

This project implements a local MCP server in Python that exposes 7 website scraping tools to Claude Desktop. Once connected, you simply give Claude a URL and it automatically chooses the right tool to extract the data you need — no setup per site, no API keys, no configuration.

Communication happens over **stdio** (standard input/output), which is the standard MCP transport for local servers. Claude Desktop starts and manages the process automatically.

---

## Features

| Capability | Details |
|---|---|
| Site summary | Title, domain, meta description, OG image, favicon |
| SEO analysis | Title/description length audit, headings structure, canonical URL, robots meta, alt-text coverage |
| Link extraction | Internal links, external links, mailto addresses, tel links |
| Content extraction | Paragraphs, headings, bullet lists, tables, word count |
| Tech stack detection | 15+ frameworks and services detected via HTML fingerprinting |
| Contact info | Emails, phone numbers, social media profiles, address hints |
| Full report | All of the above combined in a single call |

---

## Requirements

- Python **3.10** or higher
- pip
- Claude Desktop (download from [claude.ai/download](https://claude.ai/download))

---
 Installation
 
 Step 1 — Unzip the project

Extract the downloaded zip to a permanent location. Avoid temporary folders like `Downloads` — Claude Desktop needs the path to stay stable.

```
# Good locations
macOS:   /Users/yourname/Projects/web-scraper-mcp/
Windows: C:\Users\yourname\Projects\web-scraper-mcp\
```

Step 2 — Install Python dependencies

Open a terminal, navigate to the project folder, and run:

```bash
pip install -r requirements.txt
```

On macOS/Linux you may need:

```bash
pip3 install -r requirements.txt
```

This installs: `mcp`, `httpx`, `beautifulsoup4`, `lxml`.

Step 3 — Verify it works

```bash
python server.py
```

If it starts without errors, the server is ready. Press `Ctrl+C` to stop — Claude Desktop will manage starting it automatically once connected.

---

Connecting to Claude Desktop

Step 1 — Locate the config file

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

If the file does not exist, create it as an empty JSON file.

Step 2 — Add the server config

Open the file in any text editor and paste the block below, replacing the path with the actual location of `server.py` on your machine.

**macOS / Linux:**
```json
{
  "mcpServers": {
    "web-scraper": {
      "command": "python3",
      "args": ["/Users/yourname/Projects/web-scraper-mcp/server.py"]
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "web-scraper": {
      "command": "python",
      "args": ["C:\\Users\\yourname\\Projects\\web-scraper-mcp\\server.py"]
    }
  }
}
```

> ⚠️ On Windows use double backslashes `\\` in the path, or forward slashes `/` — both work.

Step 3 — Restart Claude Desktop

Fully quit Claude Desktop and reopen it. On macOS, quit from the menu bar icon — not just the window.

Step 4 — Confirm the connection

Look for the **hammer icon 🔨** in the bottom-left of the chat input. Click it — you should see all 7 scraper tools listed. If you see them, the server is live.

---

Available Tools

### `scrape_summary`
Returns a quick overview of any website.

```json
{
  "title": "Stripe: Financial Infrastructure for the Internet",
  "domain": "stripe.com",
  "url": "https://stripe.com",
  "meta_description": "Millions of businesses of all sizes use Stripe...",
  "body_preview": "...",
  "og_image": "https://stripe.com/img/og.png",
  "favicon": "https://stripe.com/favicon.ico"
}
```

---

### `scrape_seo`
Analyses on-page SEO signals with pass/fail flags.

```json
{
  "title": "Stripe: Financial Infrastructure...",
  "title_length": 47,
  "title_ok": true,
  "meta_description": "...",
  "meta_description_length": 145,
  "meta_description_ok": true,
  "canonical_url": "https://stripe.com/",
  "robots_meta": "index, follow",
  "og_title": "Stripe",
  "headings": { "h1": ["..."], "h2": ["..."], "h3": ["..."] },
  "total_images": 34,
  "images_missing_alt": 3,
  "structured_data_present": true
}
```

---

### `scrape_links`
Extracts every link on the page, grouped by type.

```json
{
  "total_links": 87,
  "internal_links_count": 54,
  "external_links_count": 33,
  "internal_links": [{ "url": "...", "text": "..." }],
  "external_links": [{ "url": "...", "text": "..." }],
  "mailto_addresses": ["support@stripe.com"],
  "phone_numbers": []
}
```

---

### `scrape_content`
Pulls the readable text content from the page.

```json
{
  "word_count": 1240,
  "paragraph_count": 18,
  "paragraphs": ["...", "..."],
  "headings": [{ "level": "h1", "text": "..." }],
  "lists": [["item 1", "item 2"]],
  "tables": [[["col1", "col2"], ["val1", "val2"]]]
}
```

---

### `scrape_tech_stack`
Detects technologies by fingerprinting HTML, scripts, and stylesheets. Covers: React, Next.js, Vue.js, Angular, jQuery, Bootstrap, Tailwind CSS, WordPress, Shopify, Google Analytics, Google Tag Manager, Cloudflare, Font Awesome, Stripe, Intercom, HubSpot, and more.

```json
{
  "detected_technologies": ["React", "Next.js", "Google Tag Manager"],
  "generator": "",
  "external_scripts": ["https://..."],
  "stylesheets": ["https://..."],
  "script_count": 12,
  "stylesheet_count": 3
}
```

---

### `scrape_contact`
Finds contact information anywhere in the page source.

```json
{
  "emails": ["hello@company.com", "support@company.com"],
  "phones": ["+1-800-555-0199"],
  "social_media": {
    "twitter": "twitter.com/company",
    "linkedin": "linkedin.com/company/acme",
    "github": "github.com/acme"
  },
  "address_hints": ["123 Main St, San Francisco, CA 94105"]
}
```

---

### `scrape_full`
Runs all 6 tools at once and returns a complete structured report. Use this when you want everything about a site in a single prompt.

---

## Example Prompts

```
Summarise https://vercel.com
What is https://linear.app about?
Check the SEO of https://github.com
What tech stack does https://shopify.com use?
Find contact details on https://mozilla.org
Extract all links from https://news.ycombinator.com
Get the main content from https://docs.python.org
Do a full scrape of https://notion.so
Give me a complete report on https://stripe.com
```

Claude automatically selects the correct tool based on your wording. The only required input is a URL.




 How It Works

```
You type a URL into Claude Desktop
         │
         ▼
   Claude LLM decides which tool to call
         │
         ▼
   MCP Server (server.py) — running locally on your machine
         │
         ├─ httpx fetches the page (real HTTP request, browser User-Agent)
         ├─ BeautifulSoup + lxml parse the HTML into a DOM tree
         ├─ Tool-specific extractor runs (regex / DOM traversal / string matching)
         │
         ▼
   Structured JSON returned to Claude → Claude presents it to you
```

No headless browser, no Playwright, no external APIs — just HTTP and HTML parsing.




## Limitations

- **JavaScript-rendered sites (SPAs):** Sites that load all content via React/Vue/Angular after page load will return limited data. The scraper reads raw HTML only — it does not execute JavaScript.
- **Login-protected pages:** Pages behind authentication cannot be accessed.
- **Bot-protected sites:** Sites using Cloudflare Bot Management, reCAPTCHA, or similar tools may block requests.
- **Dynamic content:** Data loaded via AJAX or fetch calls after initial page load is not captured.
