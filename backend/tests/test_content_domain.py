from forge.domain.content import canonicalize_url, content_fingerprint, estimate_reading_time


def test_canonicalize_strips_tracking_params_and_fragment():
    url = "HTTPS://Example.com/post/?utm_source=x&utm_medium=y&id=7&fbclid=abc#section-2"
    assert canonicalize_url(url) == "https://example.com/post?id=7"


def test_canonicalize_strips_default_ports_and_trailing_slash():
    assert canonicalize_url("http://example.com:80/a/") == "http://example.com/a"
    assert canonicalize_url("https://example.com:443/") == "https://example.com/"


def test_canonicalize_preserves_meaningful_query():
    assert (
        canonicalize_url("https://arxiv.org/abs/2401.1?v=2") == "https://arxiv.org/abs/2401.1?v=2"
    )


def test_fingerprint_ignores_whitespace_and_case():
    assert content_fingerprint("Hello   World\n") == content_fingerprint("hello world")
    assert content_fingerprint("hello world") != content_fingerprint("goodbye world")


def test_reading_time_rounds_up_with_minimum():
    assert estimate_reading_time(0) == 1
    assert estimate_reading_time(225) == 1
    assert estimate_reading_time(226) == 2
    assert estimate_reading_time(2250) == 10
