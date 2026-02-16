# 🔗 link-extract

Extract structured data from any URL. No API keys, no logins, no browser automation.

An [OpenClaw](https://openclaw.ai) skill that turns links into structured JSON — recipes, articles, Instagram posts, products, and more.

## What It Does

| Source | Method | Output |
|--------|--------|--------|
| 📸 Instagram posts/reels | Embed endpoint (no login) | Caption, username, media type |
| 🍔 Recipe blogs | schema.org/Recipe JSON-LD | Ingredients, steps, nutrition, times |
| 🌐 Any web page | HTML meta + body parsing | Title, description, body text |

## Quick Start

```bash
# Instagram reel → structured caption
python3 scripts/extract.py "https://www.instagram.com/reel/ABC123/" --pretty

# Recipe blog → full recipe with ingredients
python3 scripts/extract.py "https://www.allrecipes.com/recipe/..." --pretty

# Any URL → best-effort extraction
python3 scripts/extract.py "https://example.com/article" --pretty
```

## Output Examples

**Instagram:**
```json
{
  "source": "instagram",
  "shortcode": "C7zLbdnplNy",
  "caption": "Smash Burger\nIngredients\n* Onion...",
  "username": "derekkchen",
  "media_type": "video"
}
```

**Recipe (schema.org):**
```json
{
  "source": "schema.org",
  "type": "recipe",
  "data": {
    "@type": "Recipe",
    "name": "Smash Burgers",
    "recipeIngredient": ["1 lb ground beef", "..."],
    "recipeInstructions": [...]
  }
}
```

## How It Works

1. **Instagram**: Uses the `/p/{shortcode}/embed/captioned/` endpoint which serves caption data in server-rendered HTML — no auth needed. Falls back to oEmbed API for metadata.
2. **Recipe sites**: Parses `application/ld+json` script tags for `schema.org/Recipe` structured data (used by most major recipe sites).
3. **Everything else**: Extracts title, meta description, og:image, and a cleaned body text for LLM processing.

## Use With OpenClaw

Drop the skill into your OpenClaw workspace:
```
~/.openclaw/workspace/skills/link-extract/
```

Then share any link in chat and ask to extract it.

## Use With Any LLM Agent

The script is standalone Python 3.10+ with **zero dependencies** (stdlib only). Pipe the JSON output into any LLM for further structuring:

```bash
python3 scripts/extract.py "https://instagram.com/reel/..." | your-llm-tool --prompt "Structure this as a recipe with macros"
```

## Requirements

- Python 3.10+
- No pip installs needed (stdlib only)

## Instagram Notes

- The embed endpoint is rate-limited by Instagram — if you get empty captions, wait a few minutes
- Private accounts won't work
- Works for both posts (`/p/`) and reels (`/reel/`)

## License

MIT
