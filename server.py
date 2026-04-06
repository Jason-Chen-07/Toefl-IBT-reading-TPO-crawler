import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = int(os.getenv("PORT", "8000"))
MAX_ARTICLES = 8
REQUEST_TIMEOUT = 12
USER_AGENT = "Intelligent-News-Browser/0.1"
DEFAULT_DAYS = 3

RSS_FEEDS = [
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "BBC Technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"name": "AP Top Stories", "url": "https://www.associatedpress.com/apf-rss/TopNews"},
    {"name": "AP Technology", "url": "https://www.associatedpress.com/apf-rss/Technology"},
    {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
    {"name": "NPR Business", "url": "https://feeds.npr.org/1006/rss.xml"},
    # Japanese sources
    {"name": "NHK World", "url": "https://www3.nhk.or.jp/rss/news/cat0.xml"},
    {"name": "Asahi", "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf"},
    # Chinese / Intl Chinese
    {"name": "BBC 中文", "url": "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml"},
    {"name": "FT 中文", "url": "https://www.ftchinese.com/rss/feed"},
    # Global & regional mainstream
    {"name": "The Guardian World", "url": "https://www.theguardian.com/world/rss"},
    {"name": "Al Jazeera All", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "CNN Top Stories", "url": "https://rss.cnn.com/rss/cnn_topstories.rss"},
    {"name": "CNBC World", "url": "https://www.cnbc.com/id/100727362/device/rss/rss.html"},
    {"name": "Reuters World", "url": "https://feeds.reuters.com/Reuters/worldNews"},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss"},
    {"name": "Financial Times Technology", "url": "https://www.ft.com/technology?format=rss"},
    {"name": "Politico Picks", "url": "https://www.politico.com/rss/politicopicks.xml"},
    {"name": "Foreign Affairs", "url": "https://www.foreignaffairs.com/rss.xml"},
    {"name": "DW All", "url": "https://rss.dw.com/rdf/rss-en-all"},
    {"name": "CBC Top Stories", "url": "https://www.cbc.ca/cmlink/rss-topstories"},
    {"name": "Euractiv", "url": "https://www.euractiv.com/feed/"},
    {"name": "SCMP Top", "url": "https://www.scmp.com/rss/91/feed"},
    {"name": "Straits Times World", "url": "https://www.straitstimes.com/news/world/rss.xml"},
    {"name": "Yonhap English", "url": "https://en.yna.co.kr/landing/rss?cts=001"},
    {"name": "The Hindu", "url": "https://www.thehindu.com/feeder/default.rss"},
    {"name": "Times of India", "url": "https://timesofindia.indiatimes.com/rss.cms"},
    {"name": "Der Spiegel International", "url": "https://www.spiegel.de/international/index.rss"},
    {"name": "El Pais English", "url": "https://english.elpais.com/rss/elpais/portada.xml"},
    {"name": "Financial Post", "url": "https://financialpost.com/feed/"},
    # Tech / analysis / venture voices
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "Ars Technica", "url": "http://feeds.arstechnica.com/arstechnica/index"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/"},
    {"name": "a16z Blog", "url": "https://a16z.com/feed/"},
    {"name": "Not Boring", "url": "https://www.notboring.co/feed"},
    {"name": "SemiAnalysis", "url": "https://semianalysis.substack.com/feed"},
    {"name": "War on the Rocks", "url": "https://warontherocks.com/feed/"},
    {"name": "Defense One", "url": "https://www.defenseone.com/rss/all/"},
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}

SOURCE_TYPES = {
    "official": {"keywords": ["ministry", "政府", "政府公报", "省政府", "白宫", "国务院", "官方", "警察", "police", "agency"], "weight": 3.0},
    "mainstream": {"keywords": ["bbc", "reuters", "ap", "npr", "asahi", "nikkei", "nhk", "ft", "financial times", "guardian", "cnn", "bloomberg", "al jazeera", "politico", "foreign affairs", "dw", "cbc", "euractiv", "scmp", "straits times", "yonhap", "hindu", "times of india", "spiegel", "el pais"], "weight": 2.2},
    "financial": {"keywords": ["wsj", "wall street journal", "bloomberg", "ft", "marketwatch", "cnbc", "financial post"], "weight": 2.0},
    "analyst": {"keywords": ["analysis", "analyst", "venture", "capital", "a16z", "investor", "semianalysis", "stratechery", "not boring", "mit technology review", "ars technica", "wired"], "weight": 1.6},
    "blog": {"keywords": ["blog", "substack", "medium", "warontherocks", "defense one", "not boring"], "weight": 1.0},
}

SOURCE_FALLBACK_WEIGHT = 1.0

@dataclass
class Article:
    source: str
    feed: str
    title: str
    link: str
    summary: str
    published: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "feed": self.feed,
            "title": self.title,
            "link": self.link,
            "summary": self.summary,
            "published": self.published.isoformat(),
        }


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def tokenize(value: str) -> list[str]:
    # Support English words and contiguous CJK characters (length>=2).
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]+|[\u4e00-\u9fff]{2,}", value.lower())
    return [
        token
        for token in tokens
        if (len(token) > 2 and token not in STOPWORDS)
    ]


def split_sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+|;\s+|，(?=[^，]{15,})", value)
    return [normalize_text(part) for part in parts if len(normalize_text(part)) > 24]


def translate_query(query: str) -> str:
    if all(ord(ch) < 128 for ch in query):
        return query

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return query

    body = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5"),
        "input": [
            {
                "role": "system",
                "content": "Translate the user topic to concise English for news search. Return only the translated phrase, no quotes.",
            },
            {"role": "user", "content": query},
        ],
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = extract_response_text(payload).strip()
        return translated or query
    except Exception:  # noqa: BLE001
        return query


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)

    cleaned = value.strip()
    try:
        parsed = parsedate_to_datetime(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        pass

    iso_candidate = cleaned.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return datetime.now(UTC)


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def get_child_text(parent: ET.Element, names: list[str]) -> str:
    expected = {name.split(":")[-1] for name in names}
    for child in list(parent):
        if local_name(child.tag) in expected:
            if child.text and normalize_text(child.text):
                return normalize_text(child.text)
            nested_text = normalize_text(" ".join(text.strip() for text in child.itertext() if text.strip()))
            if nested_text:
                return nested_text
    return ""


def parse_feed(feed: dict[str, str]) -> list[Article]:
    request = Request(
        feed["url"],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        payload = response.read()

    root = ET.fromstring(payload)
    articles: list[Article] = []

    if root.tag.endswith("rss"):
        items = root.findall("./channel/item")
        for item in items[:12]:
            title = get_child_text(item, ["title"])
            link = get_child_text(item, ["link"])
            summary = strip_html(get_child_text(item, ["description", "content:encoded"]))
            published = parse_datetime(get_child_text(item, ["pubDate"]))
            if title and link:
                articles.append(
                    Article(
                        source=feed["name"],
                        feed=feed["url"],
                        title=title,
                        link=link,
                        summary=summary,
                        published=published,
                    )
                )
    else:
        entries = [child for child in list(root) if local_name(child.tag) == "entry"]
        for entry in entries[:12]:
            title = get_child_text(entry, ["atom:title"])
            link = ""
            for link_node in list(entry):
                if local_name(link_node.tag) != "link":
                    continue
                href = link_node.attrib.get("href")
                rel = link_node.attrib.get("rel", "alternate")
                if href and rel == "alternate":
                    link = href
                    break
            summary = strip_html(
                get_child_text(entry, ["atom:summary", "atom:content", "summary", "content"])
            )
            published = parse_datetime(
                get_child_text(entry, ["atom:updated", "atom:published", "updated", "published"])
            )
            if title and link:
                articles.append(
                    Article(
                        source=feed["name"],
                        feed=feed["url"],
                        title=title,
                        link=link,
                        summary=summary,
                        published=published,
                    )
                )

    return articles


def score_article(article: Article, query_terms: list[str]) -> int:
    haystack = f"{article.title} {article.summary}".lower()
    if not query_terms:
        return 1
    return sum(3 if term in article.title.lower() else 1 for term in query_terms if term in haystack)


def fetch_articles(query: str, days: int) -> tuple[list[Article], list[str]]:
    query_terms = tokenize(query)
    cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
    matched_articles: list[Article] = []
    all_articles: list[Article] = []
    errors: list[str] = []
    seen: set[str] = set()

    with ThreadPoolExecutor(max_workers=min(6, len(RSS_FEEDS))) as executor:
        futures = {executor.submit(parse_feed, feed): feed for feed in RSS_FEEDS}
        for future in as_completed(futures):
            feed = futures[future]
            try:
                for article in future.result():
                    key = article.link or article.title
                    if key in seen:
                        continue
                    seen.add(key)
                    if article.published < cutoff:
                        continue
                    all_articles.append(article)
                    if query_terms and score_article(article, query_terms) == 0:
                        continue
                    matched_articles.append(article)
            except (URLError, HTTPError, TimeoutError, ET.ParseError) as exc:
                errors.append(f"{feed['name']}: {exc}")

    scored_all = sorted(
        all_articles,
        key=lambda article: (score_article(article, query_terms), article.published),
        reverse=True,
    )
    matched_articles.sort(
        key=lambda article: (score_article(article, query_terms), article.published),
        reverse=True,
    )

    if matched_articles:
        return matched_articles[:MAX_ARTICLES], errors

    if query_terms and scored_all:
        errors.append("No exact topic matches were found, so the app fell back to the latest broader coverage.")
    return scored_all[:MAX_ARTICLES], errors


def trim_phrase(value: str, limit: int = 120) -> str:
    clean = normalize_text(value)
    return clean if len(clean) <= limit else f"{clean[: limit - 1].rstrip()}…"


def infer_topic(query: str, articles: list[Article]) -> str:
    if query:
        return query
    all_tokens: list[str] = []
    for article in articles:
        all_tokens.extend(tokenize(article.title))
    counts: dict[str, int] = {}
    for token in all_tokens:
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return " / ".join(token for token, _count in ranked[:3]) or "current headlines"


def build_consensus(query: str, articles: list[Article]) -> list[str]:
    if not articles:
        return ["No matching coverage was found across the configured RSS feeds yet."]

    bullets = [f"Compared {len(articles)} articles from {len({article.source for article in articles})} sources about {infer_topic(query, articles)}."]

    phrase_hits: dict[str, dict[str, Any]] = {}
    for index, article in enumerate(articles):
        candidates = set(split_sentences(f"{article.title}. {article.summary}"))
        for candidate in candidates:
            tokens = tokenize(candidate)
            if len(tokens) < 4:
                continue
            signature = " ".join(sorted(set(tokens[:8])))
            bucket = phrase_hits.setdefault(signature, {"count": 0, "phrase": candidate})
            bucket["count"] += 1
            if len(candidate) < len(bucket["phrase"]):
                bucket["phrase"] = candidate

    ranked = sorted(
        (value for value in phrase_hits.values() if value["count"] >= 2),
        key=lambda value: (value["count"], len(value["phrase"])),
        reverse=True,
    )

    for item in ranked[:3]:
        bullets.append(f"{item['count']} sources mention: {trim_phrase(item['phrase'])}")

    if len(bullets) < 3:
        top_keywords = {}
        for article in articles:
            for token in tokenize(f"{article.title} {article.summary}"):
                top_keywords[token] = top_keywords.get(token, 0) + 1
        repeated = [token for token, count in sorted(top_keywords.items(), key=lambda item: item[1], reverse=True) if count >= 2][:5]
        if repeated:
            bullets.append(f"Repeated coverage themes include {', '.join(repeated)}.")

    return bullets[:4]


def build_conflicts(articles: list[Article]) -> list[str]:
    conflicts: list[str] = []
    joined = " ".join(f"{article.title} {article.summary}" for article in articles)

    numbers = sorted({match.group(0) for match in re.finditer(r"\b\d[\d,.]*%?\b", joined)})
    if len(numbers) >= 3:
        conflicts.append(f"Coverage includes differing figures or measurements: {', '.join(numbers[:6])}.")

    official_sources = sum(
        1 for article in articles if re.search(r"\bofficial|minister|police|company said|spokesperson\b", article.summary, re.I)
    )
    anonymous_sources = sum(1 for article in articles if re.search(r"\bsources say|anonymous|analyst|witness\b", article.summary, re.I))
    if official_sources and anonymous_sources:
        conflicts.append("Some reports lean on official statements while others rely on analysts, witnesses, or unnamed sources.")

    if len({article.source for article in articles}) >= 3:
        conflicts.append("Outlets are framing the same event from different angles, so the emphasis may differ even where the core facts overlap.")

    return conflicts[:3]


def guess_source_type(source_name: str) -> str:
    lower = source_name.lower()
    for type_name, config in SOURCE_TYPES.items():
        if any(keyword in lower for keyword in config["keywords"]):
            return type_name
    return "mainstream"


def extract_claims(articles: list[Article]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for article in articles:
        sentences = split_sentences(f"{article.title}. {article.summary}")
        for sentence in sentences:
            tokens = tokenize(sentence)
            if len(tokens) < 4:
                continue
            claims.append(
                {
                    "text": sentence,
                    "tokens": set(tokens),
                    "source": article.source,
                    "source_type": guess_source_type(article.source),
                    "link": article.link,
                    "published": article.published,
                }
            )
    return claims


def cluster_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for claim in claims:
        matched = None
        for cluster in clusters:
            inter = len(cluster["tokens"] & claim["tokens"])
            union = len(cluster["tokens"] | claim["tokens"])
            similarity = inter / union if union else 0
            if similarity >= 0.48:
                matched = cluster
                break
        if matched:
            matched["tokens"] |= claim["tokens"]
            matched["sources"].append(
                {
                    "name": claim["source"],
                    "type": claim["source_type"],
                    "link": claim["link"],
                    "published": claim["published"].isoformat(),
                }
            )
            if len(claim["text"]) < len(matched["text"]):
                matched["text"] = claim["text"]
        else:
            clusters.append(
                {
                    "text": claim["text"],
                    "tokens": set(claim["tokens"]),
                    "sources": [
                        {
                            "name": claim["source"],
                            "type": claim["source_type"],
                            "link": claim["link"],
                            "published": claim["published"].isoformat(),
                        }
                    ],
                }
            )
    return clusters


def score_cluster(cluster: dict[str, Any]) -> tuple[str, float]:
    unique_sources = {src["name"] for src in cluster["sources"]}
    type_counts: dict[str, int] = {}
    score = 0.0
    for src in cluster["sources"]:
        type_counts[src["type"]] = type_counts.get(src["type"], 0) + 1
        weight = SOURCE_TYPES.get(src["type"], {}).get("weight", SOURCE_FALLBACK_WEIGHT)
        score += weight

    # Level rules
    official = type_counts.get("official", 0)
    mainstream = type_counts.get("mainstream", 0)
    financial = type_counts.get("financial", 0)
    total = len(unique_sources)

    level = "red"
    if total >= 4 and (official or mainstream >= 1):
        level = "green_strong"
    elif total >= 2 and (official or mainstream >= 1):
        level = "green_light"
    elif total >= 2:
        level = "yellow"
    elif total >= 1 and (official or mainstream or financial):
        level = "yellow"
    else:
        level = "red"

    return level, score


def build_claims(articles: list[Article]) -> list[dict[str, Any]]:
    raw_claims = extract_claims(articles)
    clusters = cluster_claims(raw_claims)

    enriched: list[dict[str, Any]] = []
    for cluster in clusters:
        level, score = score_cluster(cluster)
        enriched.append(
            {
                "text": trim_phrase(cluster["text"], 220),
                "level": level,
                "levelDisplay": "strong consensus" if level == "green_strong" else "consensus" if level == "green_light" else "caution" if level == "yellow" else "unverified",
                "support": len({src["name"] for src in cluster["sources"]}),
                "sources": sorted(cluster["sources"], key=lambda s: s["published"], reverse=True)[:6],
                "score": score,
            }
        )

    enriched.sort(key=lambda c: (c["level"] == "green", c["support"], c["score"]), reverse=True)
    return enriched[:10]


def build_brief(articles: list[Article], consensus: list[str], conflicts: list[str]) -> list[dict[str, str]]:
    brief: list[dict[str, str]] = []
    if articles:
        brief.append(
            {
                "type": "meta",
                "text": f"Analyzed {len(articles)} articles from {len({a.source for a in articles})} sources.",
            }
        )
    for item in consensus:
        brief.append({"type": "consensus", "text": item})
    for item in conflicts:
        brief.append({"type": "conflict", "text": item})

    # Add a couple of unique angles from article titles to surface diversity.
    for article in articles[:2]:
        brief.append({"type": "unique", "text": f"Angle from {article.source}: {trim_phrase(article.title, 160)}"})

    return brief[:8]


def build_timeline(articles: list[Article]) -> list[dict[str, str]]:
    ordered = sorted(articles, key=lambda article: article.published)
    return [
        {
            "time": article.published.strftime("%Y-%m-%d %H:%M UTC"),
            "detail": f"{article.source}: {trim_phrase(article.title, 150)}",
        }
        for article in ordered[:6]
    ]


def heuristic_analysis(query: str, articles: list[Article]) -> dict[str, Any]:
    topic = infer_topic(query, articles)
    conflicts = build_conflicts(articles)
    consensus = build_consensus(query, articles)
    claims = build_claims(articles)
    return {
        "overview": {
            "title": f"Coverage snapshot for {topic}",
            "summary": f"Pulled {len(articles)} matching articles and compared their headlines and summaries to surface overlap and disagreement.",
            "confidence": "Heuristic analysis",
            "coverageWindow": (
                f"{min(article.published for article in articles).strftime('%Y-%m-%d %H:%M UTC')} to "
                f"{max(article.published for article in articles).strftime('%Y-%m-%d %H:%M UTC')}"
                if articles
                else "No coverage window available"
            ),
        },
        "consensus": consensus,
        "conflicts": conflicts or ["No strong conflicts were detected automatically; this usually means the feed summaries are thin or still converging."],
        "claims": claims,
        "brief": build_brief(articles, consensus, conflicts or []),
        "timeline": build_timeline(articles),
    }


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"]:
        return payload["output_text"]

    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def parse_json_maybe_wrapped(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def openai_analysis(query: str, articles: list[Article]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    snippets = [
        {
            "source": article.source,
            "published": article.published.isoformat(),
            "title": article.title,
            "summary": article.summary,
            "link": article.link,
        }
        for article in articles
    ]

    body = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5"),
        "store": False,
        "input": [
            {
                "role": "developer",
                "content": (
                    "You are a careful news comparison analyst. Compare the provided article snippets and return only valid JSON. "
                    "Do not include markdown fences. Use this schema exactly: "
                    '{"overview":{"title":"","summary":"","confidence":"","coverageWindow":""},"consensus":[""],"conflicts":[""],"timeline":[{"time":"","detail":""}]}. '
                    "Consensus should focus on facts multiple sources support. Conflicts should only list meaningful disagreement, uncertainty, or attribution gaps."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query": query,
                        "articles": snippets,
                    }
                ),
            },
        ],
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))

    output_text = extract_response_text(payload)
    parsed = parse_json_maybe_wrapped(output_text)

    parsed.setdefault("consensus", [])
    parsed.setdefault("conflicts", [])
    parsed.setdefault("timeline", [])
    parsed.setdefault("claims", [])
    parsed.setdefault(
        "overview",
        {
            "title": f"Coverage snapshot for {infer_topic(query, articles)}",
            "summary": "OpenAI returned a partial analysis.",
            "confidence": "AI analysis",
            "coverageWindow": "",
        },
    )
    return parsed


def build_response(query: str, mode: str, days: int) -> dict[str, Any]:
    translated = translate_query(query)
    combined_query = " ".join({q for q in [query.strip(), translated.strip()] if q})
    articles, errors = fetch_articles(combined_query, days)
    if not articles:
        return {
            "query": query,
            "modeRequested": mode,
            "modeUsed": "none",
            "errors": errors or ["No articles matched the current query."],
            "articles": [],
            "analysis": heuristic_analysis(query, []),
        }

    analysis_mode = "heuristic"
    analysis = heuristic_analysis(query, articles)

    if mode in {"auto", "openai"}:
        try:
            analysis = openai_analysis(query, articles)
            analysis_mode = "openai"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"OpenAI analysis unavailable: {exc}")
            if mode == "openai":
                analysis["overview"]["summary"] += " AI mode failed, so the result below is the heuristic fallback."

    # Always attach locally computed claims so they are available even in AI mode.
    analysis["claims"] = analysis.get("claims") or build_claims(articles)
    analysis["brief"] = analysis.get("brief") or build_brief(articles, analysis.get("consensus", []), analysis.get("conflicts", []))
    return {
        "query": query,
        "modeRequested": mode,
        "modeUsed": analysis_mode,
        "errors": errors,
        "articles": [article.to_dict() for article in articles],
        "analysis": analysis,
    }


class NewsRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"status": "ok"})
            return

        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            query = params.get("q", ["technology"])[0].strip()
            mode = params.get("mode", ["auto"])[0].strip().lower()
            if mode not in {"auto", "heuristic", "openai"}:
                mode = "auto"
            days = params.get("days", [str(DEFAULT_DAYS)])[0]
            try:
                days_int = max(1, min(30, int(days)))
            except ValueError:
                days_int = DEFAULT_DAYS

            try:
                payload = build_response(query, mode, days_int)
                self.send_json(payload)
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": str(exc)}, status=500)
            return

        if parsed.path == "/":
            self.path = "/index.html"

        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), NewsRequestHandler)
    except PermissionError:
        # Fallback: pick an ephemeral port automatically.
        server = ThreadingHTTPServer((HOST, 0), NewsRequestHandler)
        print("Requested port not permitted; falling back to an available port.")
    except OSError:
        # If in use, also fall back to an available port.
        server = ThreadingHTTPServer((HOST, 0), NewsRequestHandler)
        print("Requested port unavailable; falling back to an available port.")

    actual_port = server.server_address[1]
    print(f"Serving Intelligent News Browser at http://{HOST}:{actual_port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
