---
name: link-extract
description: Extract structured data from any URL — recipes, articles, products, travel content, Instagram posts/reels. Use when a user shares a link and wants the content extracted, summarized, or structured. Handles Instagram (embed trick, no login), recipe blogs (schema.org/Recipe JSON-LD), and general web pages. Returns structured JSON for further processing.
---

# link-extract

Extract structured content from URLs into typed JSON. No API keys, no logins, no browser automation.

## Supported Sources

| Source | Method | What You Get |
|--------|--------|-------------|
| Instagram posts/reels | `/embed/captioned/` endpoint | Caption text, username, media type, thumbnail |
| Recipe blogs | `schema.org/Recipe` JSON-LD | Ingredients, instructions, nutrition, times, yield |
| General web pages | HTML parsing + meta tags | Title, description, body text, og:image |

## Usage

### Quick Extract

```bash
python3 scripts/extract.py <URL> [--pretty] [--type auto|instagram|web]
```

Returns JSON to stdout. Pipe to `jq` or process in your agent.

### Examples

```bash
# Instagram reel → caption + metadata
python3 scripts/extract.py "https://www.instagram.com/reel/C7zLbdnplNy/" --pretty

# Recipe blog → structured recipe with ingredients, steps, nutrition
python3 scripts/extract.py "https://example.com/smash-burger-recipe" --pretty

# Any URL → best-effort structured extraction
python3 scripts/extract.py "https://example.com/article" --pretty
```

### Output Schemas

**Instagram** (`source: "instagram"`):
```json
{
  "source": "instagram",
  "shortcode": "C7zLbdnplNy",
  "url": "...",
  "caption": "Full caption text...",
  "username": "derekkchen",
  "media_type": "video",
  "thumbnail": "https://..."
}
```

**Recipe** (`source: "schema.org"`, `type: "recipe"`):
```json
{
  "source": "schema.org",
  "type": "recipe",
  "url": "...",
  "data": { "@type": "Recipe", "name": "...", "recipeIngredient": [...], ... }
}
```

**Generic** (`source: "web"`):
```json
{
  "source": "web",
  "url": "...",
  "title": "...",
  "description": "...",
  "body_text": "First 5000 chars..."
}
```

## Agent Workflow

1. Run `extract.py` on the URL
2. Check `source` field to determine content type
3. For Instagram: caption contains the content — use LLM to structure it (recipe, travel tips, product review, etc.)
4. For schema.org recipes: data is already structured — use directly
5. For generic pages: use `body_text` + `title` as LLM context to extract what the user needs

### Structuring with LLM

After extraction, ask the LLM to structure the raw content into whatever format is needed:

- **Recipe**: ingredients list, macros, steps, servings
- **Travel/Holiday**: destinations, dates, costs, packing list
- **Product**: name, price, specs, pros/cons
- **Article**: summary, key points, quotes

The script handles the hard part (fetching content without auth). The LLM handles the smart part (understanding and structuring it).

## Instagram Notes

- Uses the `/p/{shortcode}/embed/captioned/` endpoint — serves caption in server-rendered HTML
- No login or API key required
- Works for both posts and reels (reels use `/reel/` URLs but same shortcode format)
- Rate limits apply — don't hammer it
- Private accounts won't work

## Dependencies

Python 3.10+ standard library only. No pip installs needed.
