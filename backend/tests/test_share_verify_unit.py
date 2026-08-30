"""Unit tests for share post verification — no live API required."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DB_NAME", "test_database")

from share_verify import (  # noqa: E402
    fixture_text,
    is_crawler_ua,
    normalize_post_url,
    post_matches,
    validate_platform_url,
    verify_post,
)


def test_template_match():
    assert post_matches("yo — Check out Acme in freshboard.lol", "Acme")
    assert post_matches("CHECK OUT ACME IN FRESHBOARD.LOL", "Acme")
    assert not post_matches("Check out Acme on twitter", "Acme")
    assert not post_matches("love freshboard.lol", "Acme")


def test_reject_compose_urls():
    for url, target in (
        ("https://twitter.com/intent/tweet?text=hi", "x"),
        ("https://www.linkedin.com/sharing/share-offsite/?url=https://freshboard.lol", "linkedin"),
        ("https://reddit.com/submit?url=https://freshboard.lol", "reddit"),
        ("https://www.facebook.com/sharer/sharer.php?u=https://freshboard.lol", "facebook"),
    ):
        try:
            validate_platform_url(target, url)
            raise AssertionError(f"should reject {url}")
        except ValueError:
            pass


def test_accept_real_post_shapes():
    assert "x.com/i/status/123" in normalize_post_url("https://twitter.com/jane/status/123?s=20")
    validate_platform_url("x", "https://x.com/jane/status/1888123456789012345")
    validate_platform_url("reddit", "https://www.reddit.com/r/startups/comments/abc123/hello/")
    validate_platform_url("linkedin", "https://www.linkedin.com/posts/jane_check-out-activity-123-AbC")
    validate_platform_url("facebook", "https://www.facebook.com/share/p/abc123/")


def test_fixture_verify():
    url = "http://localhost/api/dev/share-fixture?company=Acme&u=1"
    assert "freshboard.lol" in fixture_text(url)
    assert verify_post("x", url, "Acme")


def test_fixture_blank_fails():
    url = "http://localhost/api/dev/share-fixture?company=Acme&blank=1"
    try:
        verify_post("x", url, "Acme")
        raise AssertionError("blank fixture should fail")
    except ValueError:
        pass


def test_crawler_ua():
    assert is_crawler_ua("WhatsApp/10.2.0")
    assert is_crawler_ua("facebookexternalhit/1.1")
    assert not is_crawler_ua("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)")
    assert not is_crawler_ua("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 WhatsApp/2.24.10")


if __name__ == "__main__":
    test_template_match()
    test_reject_compose_urls()
    test_accept_real_post_shapes()
    test_fixture_verify()
    test_fixture_blank_fails()
    test_crawler_ua()
    print("share_verify unit tests passed")
