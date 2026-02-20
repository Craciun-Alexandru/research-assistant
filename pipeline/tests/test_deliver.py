"""Tests for arxiv_digest.deliver module."""

from unittest.mock import MagicMock, patch

from arxiv_digest.deliver import deliver_all

EMAIL_CONFIG = {
    "email": {
        "smtp_host": "smtp.test.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "from_address": "",
        "to_address": "",
    }
}


def test_deliver_all_returns_false_when_html_path_is_none(tmp_path):
    md = tmp_path / "digest.md"
    md.write_text("# Digest")
    assert deliver_all(md, None, EMAIL_CONFIG) is False


def test_deliver_all_returns_false_when_html_path_missing(tmp_path):
    md = tmp_path / "digest.md"
    md.write_text("# Digest")
    html = tmp_path / "digest.html"  # intentionally not created
    assert deliver_all(md, html, EMAIL_CONFIG) is False


def test_deliver_all_propagates_true_from_email(tmp_path):
    md = tmp_path / "digest.md"
    md.write_text("# Digest")
    html = tmp_path / "digest.html"
    html.write_text("<html></html>")
    mock_fn = MagicMock(return_value=True)
    mock_module = MagicMock(deliver_email_digest=mock_fn)
    with patch.dict("sys.modules", {"arxiv_digest.deliver_email": mock_module}):
        result = deliver_all(md, html, EMAIL_CONFIG)
    assert result is True
    mock_fn.assert_called_once_with(html, md, EMAIL_CONFIG["email"])


def test_deliver_all_propagates_false_from_email(tmp_path):
    md = tmp_path / "digest.md"
    md.write_text("# Digest")
    html = tmp_path / "digest.html"
    html.write_text("<html></html>")
    mock_fn = MagicMock(return_value=False)
    mock_module = MagicMock(deliver_email_digest=mock_fn)
    with patch.dict("sys.modules", {"arxiv_digest.deliver_email": mock_module}):
        result = deliver_all(md, html, EMAIL_CONFIG)
    assert result is False
