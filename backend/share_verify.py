"""Verify that a share is a real public post, not just a compose-dialog click.

Social intent URLs never tell us whether someone published. The only reliable
no-OAuth check is: require the live post URL, fetch it, and confirm the body
mentions the company and freshboard.lol.
"""
from __future__ import annotations

import os
import re
from html import unescape
from typing import Optional
from urllib.parse import parse_qs, urlparse, urlunparse

SHARE_TARGETS = ("x", "linkedin", "reddit", "facebook", "whatsapp")
POST_TARGETS = ("x", "linkedin", "reddit", "facebook")
CRAWLER_HINTS = (
    "whatsapp", "facebookexternalhit", "facebot", "twitterbot",
    "linkedinbot", "slackbot", "telegrambot", "discordbot",
    "preview", "embed", "crawler", "spider", "bot",
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PLATFORM_HOSTS = {
    "x": ("twitter.com", "x.com", "mobile.twitter.com", "mobile.x.com"),
    "linkedin": ("linkedin.com", "www.linkedin.com"),
    "reddit": ("reddit.com", "www.reddit.com", "old.reddit.com", "m.reddit.com"),
    "facebook": (
        "facebook.com", "www.facebook.com", "m.facebook.com",
        "web.facebook.com", "fb.watch",
    ),
}

# Compose / sharer URLs — opening these is not a post.
REJECT_PATH = {
    "x": ("/intent/", "/compose/", "/i/flow/"),
    "linkedin": ("/sharing/share-offsite", "/uas/login", "/login"),
    "reddit": ("/submit",),
    "facebook": ("/sharer/", "/dialog/share", "/share.php"),
}

REQUIRE_PATH = {
    "x": re.compile(r"/status(?:es)?/\d+", re.I),
    "linkedin": re.compile(r"/posts/|/feed/update/|/pulse/", re.I),
    "reddit": re.compile(r"/comments/[a-z0-9]+", re.I),
    "facebook": re.compile(
        r"/posts/|/permalink|/reel/|/share/p/|/share/r/|/photo|/watch/|/story\.php|/stories/",
        re.I,
    ),
}

_TWEET_ID = re.compile(r"/status(?:es)?/(\d+)", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_META_RE = re.compile(
    r"""<meta\s+[^>]*?(?:property|name)\s*=\s*['"]([^'"]+)['"][^>]*?content\s*=\s*['"]([^'"]*)['"][^>]*?/?>""",
    re.I,
)
_META_RE_ALT = re.compile(
    r"""<meta\s+[^>]*?content\s*=\s*['"]([^'"]*)['"][^>]*?(?:property|name)\s*=\s*['"]([^'"]+)['"][^>]*?/?>""",
    re.I,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.I | re.S)


def test_fixtures_enabled() -> bool:
    return (
        os.environ.get("SHARE_TEST_FIXTURES") == "1"
        or os.environ.get("DB_NAME", "") == "test_database"
    )


def fixture_html(company: str = "", token: str = "", blank: bool = False) -> str:
    body = "this post has nothing useful" if blank else f"Check out {company} in freshboard.lol {token}".strip()
    return (
        "<!doctype html><html><head>"
        f"<title>{body}</title>"
        f"<meta property='og:description' content='{body}'>"
        f"</head><body>{body}</body></html>"
    )


def fixture_text(url: str) -> Optional[str]:
    """In-process text for /dev/share-fixture URLs so tests don't self-HTTP."""
    if not test_fixtures_enabled():
        return None
    parsed = urlparse(url)
    if "/dev/share-fixture" not in parsed.path:
        return None
    qs = parse_qs(parsed.query)
    if (qs.get("blank") or ["0"])[0] == "1":
        return "this post has nothing useful"
    company = (qs.get("company") or [""])[0]
    token = (qs.get("token") or [""])[0]
    return f"Check out {company} in freshboard.lol {token}".strip()


def normalize_post_url(url: str) -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    query = ""
    qs = parse_qs(parsed.query)
    if host.endswith("facebook.com") and "permalink.php" in path:
        keep = []
        if "story_fbid" in qs:
            keep.append(f"story_fbid={qs['story_fbid'][0]}")
        if "id" in qs:
            keep.append(f"id={qs['id'][0]}")
        query = "&".join(keep)
    tweet = _TWEET_ID.search(path)
    if tweet and (host.endswith("twitter.com") or host.endswith("x.com") or host == "x.com"):
        host = "x.com"
        path = f"/i/status/{tweet.group(1)}"
    scheme = "https"
    return urlunparse((scheme, host, path, "", query, "")).lower()


def validate_platform_url(target: str, url: str) -> str:
    """Return a normalized post URL or raise ValueError."""
    raw = (url or "").strip()
    if not re.match(r"^https?://", raw, re.I):
        raise ValueError("Paste the full public post URL, starting with https://")
    if fixture_text(raw) is not None:
        return normalize_post_url(raw)

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    hosts = tuple(h.removeprefix("www.") for h in PLATFORM_HOSTS.get(target, ()))
    if host not in hosts and not any(host.endswith("." + h) for h in hosts):
        raise ValueError(f"That URL is not a {target} post")

    path_q = parsed.path + ("?" + parsed.query if parsed.query else "")
    for frag in REJECT_PATH.get(target, ()):
        if frag.lower() in path_q.lower():
            raise ValueError("That's a share dialog, not a published post. Paste the live post link.")

    req = REQUIRE_PATH.get(target)
    if req and not req.search(path_q):
        raise ValueError("Paste the URL of the published post, not a profile or homepage.")

    return normalize_post_url(raw)


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def post_matches(text: str, company: str) -> bool:
    blob = unescape(text or "")
    low = blob.lower()
    if "freshboard.lol" not in low:
        return False
    name = _norm_name(company)
    if not name:
        return False
    if len(name) < 3:
        return re.search(rf"\b{re.escape(company.strip())}\b", blob, re.I) is not None
    return name in _norm_name(blob)


def _get(url: str, **kwargs):
    import requests
    headers = {"User-Agent": _UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
    headers.update(kwargs.pop("headers", {}))
    return requests.get(url, timeout=8, headers=headers, allow_redirects=True, **kwargs)


def _html_text(html: str) -> str:
    if not html:
        return ""
    meta = {}
    for m in _META_RE.finditer(html):
        meta.setdefault(m.group(1).lower(), m.group(2))
    for m in _META_RE_ALT.finditer(html):
        meta.setdefault(m.group(2).lower(), m.group(1))
    title = ""
    tm = _TITLE_RE.search(html)
    if tm:
        title = tm.group(1)
    body = _TAG_RE.sub(" ", html[:60000])
    parts = [
        meta.get("og:title", ""),
        meta.get("og:description", ""),
        meta.get("twitter:title", ""),
        meta.get("twitter:description", ""),
        meta.get("description", ""),
        title,
        body,
    ]
    return _WS_RE.sub(" ", unescape(" ".join(parts)))


def _extract_x(url: str) -> str:
    tid = None
    m = _TWEET_ID.search(url)
    if m:
        tid = m.group(1)
    chunks = []
    try:
        r = _get("https://publish.twitter.com/oembed", params={"url": url, "omit_script": "true"})
        if r.status_code < 400:
            data = r.json()
            chunks.append(data.get("html") or "")
            chunks.append(data.get("author_name") or "")
    except Exception:
        pass
    if tid:
        for fx in (
            f"https://api.fxtwitter.com/status/{tid}",
            f"https://api.vxtwitter.com/status/{tid}",
        ):
            try:
                r = _get(fx)
                if r.status_code < 400:
                    data = r.json()
                    tweet = data.get("tweet") or data
                    chunks.append(tweet.get("text") or tweet.get("raw_text") or "")
                    chunks.append(str(tweet.get("author") or ""))
                    if chunks:
                        break
            except Exception:
                continue
    text = _WS_RE.sub(" ", unescape(" ".join(chunks)))
    if not text.strip():
        raise ValueError("Couldn't read that post. Make sure it's public on X.")
    return text


def _extract_reddit(url: str) -> str:
    parsed = urlparse(url)
    json_url = urlunparse(("https", parsed.netloc, parsed.path.rstrip("/") + ".json", "", "", ""))
    try:
        r = _get(json_url, headers={"User-Agent": "FreshBoard.lol/1.0 (share verify)"})
        if r.status_code >= 400:
            raise ValueError("Couldn't read that Reddit post. Make sure it's public.")
        data = r.json()
        post = data[0]["data"]["children"][0]["data"]
        return f"{post.get('title') or ''} {post.get('selftext') or ''} {post.get('url') or ''}"
    except ValueError:
        raise
    except Exception:
        raise ValueError("Couldn't read that Reddit post. Make sure it's public.")


def _extract_html(url: str, platform: str) -> str:
    try:
        r = _get(url)
    except Exception:
        raise ValueError(f"Couldn't reach that {platform} post.")
    if r.status_code >= 400:
        raise ValueError(f"Couldn't read that {platform} post. Make sure it's public.")
    text = _html_text(r.text)
    if not text.strip():
        raise ValueError(f"Couldn't read that {platform} post. Make sure it's public.")
    return text


def extract_post_text(target: str, url: str) -> str:
    fx = fixture_text(url)
    if fx is not None:
        return fx
    if target == "x":
        return _extract_x(url)
    if target == "reddit":
        return _extract_reddit(url)
    return _extract_html(url, target)


def is_crawler_ua(ua: str) -> bool:
    """Link-preview bots only. WhatsApp's in-app browser sends Mozilla and must count."""
    low = (ua or "").lower()
    if "mozilla" in low:
        return False
    return any(h in low for h in CRAWLER_HINTS)


def verify_post(target: str, post_url: str, company: str) -> str:
    """Validate + fetch. Returns normalized URL. Raises ValueError if not a real matching post."""
    norm = validate_platform_url(target, post_url)
    text = extract_post_text(target, post_url)
    if not post_matches(text, company):
        raise ValueError(
            "That post doesn't mention this company and freshboard.lol. "
            "Keep the template line in the published post."
        )
    return norm
