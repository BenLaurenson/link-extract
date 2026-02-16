#!/usr/bin/env python3
"""
link-extract: Extract structured data from any URL.
Supports Instagram (embed trick), recipe blogs (schema.org), and general web pages.
"""
import argparse
import json
import re
import sys
import html
from urllib.request import urlopen, Request
from urllib.parse import urlparse, quote

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Instagram serves full caption HTML to bots but rate-limits browser UAs
IG_USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def fetch(url: str, max_bytes: int = 500_000) -> str:
    """Fetch URL content as text."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return resp.read(max_bytes).decode("utf-8", errors="replace")


def _try_embed(shortcode: str) -> tuple[str, str]:
    """Try Instagram embed endpoint. Returns (raw_html, caption) or ("", "")."""
    import time
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
    for attempt in range(2):
        try:
            # Use bot UA — Instagram serves full caption HTML to crawlers
            req = Request(embed_url, headers={"User-Agent": IG_USER_AGENT, "Accept": "text/html"})
            with urlopen(req, timeout=15) as resp:
                raw = resp.read(1_000_000).decode("utf-8", errors="replace")
            caption = ""
            # Method 1: Caption div with CaptionUsername
            cap_start = raw.find('class="Caption"')
            if cap_start != -1:
                chunk = raw[cap_start:cap_start + 10000]
                a_end = chunk.find('</a>')
                if a_end != -1:
                    rest = chunk[a_end + 4:]
                    # Find end: CaptionComments div or closing </div>
                    import re as _re
                    end_match = _re.search(r'class="CaptionComments"|<div\s|<div>', rest)
                    if end_match:
                        caption = rest[:end_match.start()]
                    else:
                        # Last resort: take up to closing </div>
                        end_idx = rest.find('</div>')
                        caption = rest[:end_idx] if end_idx != -1 else rest[:5000]
            # Method 2: JSON in embed page
            if not caption:
                m = re.search(r'"edge_media_to_caption".*?"text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
                if m:
                    caption = m.group(1).encode().decode('unicode_escape')
            if not caption:
                m = re.search(r'"caption"\s*:\s*\{[^}]*"text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
                if m:
                    caption = m.group(1).encode().decode('unicode_escape')
            if caption:
                return raw, caption
            if attempt == 0:
                time.sleep(1)
        except Exception:
            if attempt == 0:
                time.sleep(1)
    return "", ""


def _try_oembed(url: str) -> dict:
    """Try Instagram oEmbed API for basic metadata."""
    oembed_url = f"https://api.instagram.com/oembed/?url={quote(url, safe='')}"
    try:
        raw = fetch(oembed_url, max_bytes=50_000)
        return json.loads(raw)
    except Exception:
        return {}


def extract_instagram(url: str) -> dict:
    """Extract Instagram post/reel content via multiple methods."""
    m = re.search(r'/(p|reel|reels)/([A-Za-z0-9_-]+)', url)
    if not m:
        raise ValueError(f"Could not find Instagram shortcode in: {url}")
    shortcode = m.group(2)
    result = {"source": "instagram", "shortcode": shortcode, "url": url}

    # Try embed endpoint first (best: full caption)
    raw, caption = _try_embed(shortcode)

    if caption:
        caption = re.sub(r'<br\s*/?>', '\n', caption)
        caption = re.sub(r'<[^>]+>', '', caption)
        caption = html.unescape(caption).strip()
        result["caption"] = caption

        # Extract username from embed
        user_match = re.search(r'class="CaptionUsername"[^>]*>([^<]+)<', raw)
        if not user_match:
            user_match = re.search(r'"username"\s*:\s*"([^"]*)"', raw)
        if user_match:
            result["username"] = user_match.group(1).strip()
    else:
        # Fallback: oEmbed (gives title/author but not full caption)
        oembed = _try_oembed(url)
        if oembed:
            result["title"] = oembed.get("title", "")
            result["username"] = oembed.get("author_name", "")
            result["thumbnail"] = oembed.get("thumbnail_url", "")
            result["caption"] = ""
            result["note"] = "Embed rate-limited. Caption unavailable — paste caption text manually for full extraction."
        else:
            result["caption"] = ""
            result["note"] = "Could not extract caption. Instagram may be rate-limiting. Try again later or paste caption text."

    # Media type
    if '/reel/' in url:
        result["media_type"] = "video"
    elif raw and '"is_video":true' in raw:
        result["media_type"] = "video"
    else:
        result["media_type"] = "image" if not '/reel/' in url else "video"

    # Thumbnail from embed
    if "thumbnail" not in result and raw:
        img_match = re.search(r'class="EmbeddedMediaImage"[^>]*src="([^"]+)"', raw)
        if img_match:
            result["thumbnail"] = html.unescape(img_match.group(1))

    return result


def extract_schema_org(page_html: str, url: str) -> dict | None:
    """Extract schema.org/Recipe or other structured data from HTML."""
    # Find all JSON-LD blocks
    blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page_html, re.DOTALL)
    for block in blocks:
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue

        # Handle @graph arrays
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "@graph" in data:
                items = data["@graph"]
            else:
                items = [data]

        for item in items:
            if isinstance(item, dict) and item.get("@type") in ("Recipe", ["Recipe"]):
                return {"source": "schema.org", "type": "recipe", "url": url, "data": item}
    return None


def extract_generic(url: str) -> dict:
    """Fetch and return raw page content for LLM processing."""
    page = fetch(url)

    result = {"source": "web", "url": url}

    # Try schema.org first
    schema = extract_schema_org(page, url)
    if schema:
        return schema

    # Extract title
    title_match = re.search(r'<title[^>]*>(.*?)</title>', page, re.DOTALL | re.IGNORECASE)
    if title_match:
        result["title"] = html.unescape(title_match.group(1)).strip()

    # Extract meta description
    desc_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', page, re.IGNORECASE)
    if desc_match:
        result["description"] = html.unescape(desc_match.group(1)).strip()

    # Extract og:image
    img_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"', page, re.IGNORECASE)
    if img_match:
        result["image"] = html.unescape(img_match.group(1))

    # Strip HTML for body text (crude but effective for LLM input)
    body_match = re.search(r'<body[^>]*>(.*)</body>', page, re.DOTALL | re.IGNORECASE)
    if body_match:
        text = body_match.group(1)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        # Truncate to ~5000 chars for LLM context
        result["body_text"] = text[:5000]

    return result


def detect_source(url: str) -> str:
    """Detect URL type."""
    domain = urlparse(url).netloc.lower()
    if "instagram.com" in domain or "instagr.am" in domain:
        return "instagram"
    return "web"


def main():
    parser = argparse.ArgumentParser(description="Extract structured data from URLs")
    parser.add_argument("url", help="URL to extract from")
    parser.add_argument("--type", choices=["auto", "instagram", "web"], default="auto",
                        help="Force extraction type")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    source = args.type if args.type != "auto" else detect_source(args.url)

    try:
        if source == "instagram":
            result = extract_instagram(args.url)
        else:
            result = extract_generic(args.url)

        indent = 2 if args.pretty else None
        print(json.dumps(result, indent=indent, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e), "url": args.url}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
