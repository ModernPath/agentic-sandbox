import pytest

from sandbox_blocks.fetch import extract_text, fetch_page, validate_url


def resolver_for(address):
    return lambda host: [address]


def test_validate_rejects_non_http_schemes():  # T15 part 1
    with pytest.raises(ValueError, match="http"):
        validate_url("file:///etc/passwd", resolver=resolver_for("8.8.8.8"))


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://10.0.0.5/",
    "http://[::1]/",
    "http://169.254.169.254/latest/meta-data",
])
def test_validate_rejects_literal_non_public_addresses(url):  # T15 part 2
    with pytest.raises(ValueError):
        validate_url(url, resolver=resolver_for("127.0.0.1"))


def test_validate_rejects_host_that_resolves_to_private_address():  # T15 part 3
    with pytest.raises(ValueError, match="public"):
        validate_url("https://internal.example/page", resolver=resolver_for("192.168.1.1"))


def test_validate_accepts_public_host():  # T16
    url = validate_url("https://news.example/story?id=1", resolver=resolver_for("93.184.216.34"))
    assert url == "https://news.example/story?id=1"


def test_extract_text_removes_scripts_and_styles_and_keeps_title():  # T17
    html = """<html><head><title> Big  News </title><style>p{color:red}</style></head>
    <body><script>var secret=1;</script><h1>Headline</h1>
    <p>First   paragraph.</p><noscript>enable js</noscript><p>Second.</p></body></html>"""
    title, text = extract_text(html, max_chars=1000)
    assert title == "Big News"
    assert "secret" not in text and "color" not in text and "enable js" not in text
    assert "Headline" in text and "First paragraph." in text and "Second." in text


def test_extract_text_is_capped_at_max_chars():  # T18
    html = "<p>" + ("word " * 5000) + "</p>"
    _, text = extract_text(html, max_chars=200)
    assert len(text) <= 200


def test_fetch_page_truncates_large_body_without_error():  # T19
    body = ("<html><title>T</title><body>" + "x" * 50000 + "</body></html>").encode()
    seen = {}

    def reader(url, timeout, max_bytes):
        seen["max_bytes"] = max_bytes
        return body[:max_bytes]

    page = fetch_page("https://news.example/a", max_chars=500, reader=reader,
                      resolver=resolver_for("93.184.216.34"))
    assert page.title == "T"
    assert len(page.text) <= 500
    assert seen["max_bytes"] == 500 * 4
