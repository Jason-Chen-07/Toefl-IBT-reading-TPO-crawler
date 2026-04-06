# Intelligent News Browser

An AI-assisted news comparison engine that pulls coverage from multiple media sources, highlights consensus information, flags conflicting claims, and helps readers understand an event faster.

## What This Version Does

This repository now includes a lightweight full-stack prototype:

- Fetches live RSS articles from multiple news feeds
- Filters articles by a topic or keyword
- Compares retrieved coverage with a heuristic pipeline
- Optionally upgrades the comparison with OpenAI analysis
- Renders the result in a browser UI with consensus, conflicts, source cards, and a timeline

## Stack

- Backend: Python standard library only
- Frontend: HTML, CSS, vanilla JavaScript
- AI integration: OpenAI Responses API via `OPENAI_API_KEY`

The current implementation avoids external Python packages so the project can start running with minimal setup.

## Files

- `server.py`: static file server, RSS ingestion, heuristic comparison, optional OpenAI analysis
- `index.html`: page layout
- `styles.css`: responsive UI
- `app.js`: frontend fetch and rendering logic

## Run Locally

```bash
cd /Users/chensfolder/Intelligent-News-Browser
python3 server.py
```

Then open `http://127.0.0.1:8000`.

## Optional OpenAI Setup

If you want AI comparison enabled, export an API key before starting the server:

```bash
export OPENAI_API_KEY="your_api_key_here"
python3 server.py
```

Optional model override:

```bash
export OPENAI_MODEL="gpt-5"
```

Without `OPENAI_API_KEY`, the app still works and falls back to heuristic analysis.

## API Endpoints

- `GET /api/health`: health check
- `GET /api/search?q=semiconductor&mode=auto`

### Modes

- `auto`: use OpenAI if configured, otherwise heuristic fallback
- `heuristic`: RSS + local comparison only
- `openai`: require OpenAI analysis, but still falls back with an error note if the request fails

## Current Feed Sources (excerpt)

BBC World · BBC Technology · AP Top Stories · AP Technology · NPR World · NPR Business · NHK World · Asahi · BBC 中文 · FT 中文 · The Guardian World · Al Jazeera · CNN Top Stories · CNBC World · Reuters World · Nikkei Asia · FT Technology · Politico Picks · Foreign Affairs · TechCrunch · Ars Technica · Wired · MIT Technology Review · VentureBeat · a16z Blog · Not Boring · SemiAnalysis · War on the Rocks · Defense One

You can add more by editing `RSS_FEEDS` in `server.py`.

## Important Notes

- RSS feeds vary in quality and summary length, so heuristic output will sometimes be broad.
- Different publishers may throttle or change feed formats over time.
- OpenAI mode depends on live network access and a valid API key.

## Suggested Next Steps

1. Add article deduplication beyond URL matching.
2. Introduce claim extraction per article instead of title-and-summary heuristics.
3. Add source filters and side-by-side article diff views.
4. Persist previous comparisons so users can revisit evolving stories.
5. Move feed configuration into a separate JSON or admin UI.
