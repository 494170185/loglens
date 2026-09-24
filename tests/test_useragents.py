"""M26 — user-agent parsing."""

from __future__ import annotations

from loglens.useragents import enrich_fields_with_ua, parse_user_agent

CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
SAFARI_IOS = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


class TestFamilies:
    def test_chrome(self):
        info = parse_user_agent(CHROME)
        assert info.family == "Chrome"
        assert info.version == "128"
        assert info.os_name == "Windows"
        assert not info.is_bot

    def test_firefox_linux(self):
        info = parse_user_agent(FIREFOX)
        assert info.family == "Firefox"
        assert info.version == "129"
        assert info.os_name == "Linux"

    def test_safari_ios(self):
        info = parse_user_agent(SAFARI_IOS)
        assert info.family == "Safari"
        assert info.os_name == "iOS"
        assert info.device == "phone"

    def test_edge_before_chrome(self):
        ua = CHROME.replace("Chrome/128", "Chrome/128 Edge/127")
        assert parse_user_agent(ua).family == "Edge"

    def test_curl_is_bot(self):
        info = parse_user_agent("curl/8.5.0")
        assert info.family == "curl"
        assert info.version == "8.5.0"
        assert info.is_bot

    def test_wget_is_bot(self):
        assert parse_user_agent("Wget/1.21").is_bot

    def test_python_requests(self):
        info = parse_user_agent("python-requests/2.31.0")
        assert info.family == "Python"
        assert info.is_bot

    def test_googlebot(self):
        info = parse_user_agent(GOOGLEBOT)
        assert info.is_bot

    def test_empty_and_none(self):
        for value in ("", None):
            info = parse_user_agent(value)
            assert info.family == "unknown"
            assert not info.is_bot


class TestDevices:
    def test_android_phone(self):
        ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/128 Mobile Safari/537.36"
        info = parse_user_agent(ua)
        assert info.device == "phone"
        assert info.os_name == "Android"

    def test_ipad_tablet(self):
        ua = "Mozilla/5.0 (iPad; CPU OS 17_4) AppleWebKit/605.1.15 Version/17.4 Safari/604.1"
        info = parse_user_agent(ua)
        assert info.device == "tablet"


class TestEnrich:
    def test_fields_enriched(self):
        out = enrich_fields_with_ua({"agent": CHROME, "status": 200})
        assert out["ua_family"] == "Chrome"
        assert out["ua_bot"] is False
        assert out["status"] == 200

    def test_no_agent_untouched(self):
        fields = {"status": 200}
        assert enrich_fields_with_ua(fields) is fields

    def test_as_dict_keys(self):
        d = parse_user_agent(CHROME).as_dict()
        assert set(d) == {"ua_family", "ua_version", "ua_os", "ua_device", "ua_bot"}
