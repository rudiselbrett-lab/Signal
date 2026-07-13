import pytest

from forge.adapters.http import UnsafeURLError, ensure_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data",
        "ftp://example.com/file",
        "http:///nohost",
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(UnsafeURLError):
        ensure_public_url(url)
