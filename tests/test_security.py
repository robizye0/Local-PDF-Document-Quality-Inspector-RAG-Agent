import time

from backend.security import RateLimiter, api_key_is_valid


def test_api_key_is_optional_for_local_development():
    assert api_key_is_valid(configured_key="", supplied_key=None)


def test_configured_api_key_requires_exact_match():
    assert api_key_is_valid("demo-key", "demo-key")
    assert not api_key_is_valid("demo-key", "wrong")
    assert not api_key_is_valid("demo-key", None)


def test_rate_limiter_rejects_only_after_limit():
    clock = iter([100.0, 100.1, 100.2, 161.0])
    limiter = RateLimiter(limit=2, window_seconds=60, clock=lambda: next(clock))

    assert limiter.allow("client")
    assert limiter.allow("client")
    assert not limiter.allow("client")
    assert limiter.allow("client")
