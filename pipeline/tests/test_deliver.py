"""Tests for arxiv_digest.deliver email building and sending."""

import smtplib
from unittest.mock import MagicMock, patch

from arxiv_digest.deliver import build_email, send_email

# ── build_email ──────────────────────────────────────────────────────


def test_build_email_mime_structure():
    msg = build_email(
        html_content="<h1>Hello</h1>",
        text_content="Hello",
        from_address="sender@example.com",
        to_address="recipient@example.com",
        subject="Test Subject",
    )
    assert msg.get_content_type() == "multipart/alternative"
    parts = msg.get_payload()
    assert len(parts) == 2
    assert parts[0].get_content_type() == "text/plain"
    assert parts[1].get_content_type() == "text/html"


def test_build_email_headers():
    msg = build_email(
        html_content="<p>body</p>",
        text_content="body",
        from_address="from@example.com",
        to_address="to@example.com",
        subject="arXiv Digest — 2026-02-19",
    )
    assert msg["From"] == "from@example.com"
    assert msg["To"] == "to@example.com"
    assert msg["Subject"] == "arXiv Digest — 2026-02-19"


def test_build_email_content():
    msg = build_email(
        html_content="<h1>Digest</h1>",
        text_content="# Digest",
        from_address="a@b.com",
        to_address="c@d.com",
        subject="Test",
    )
    parts = msg.get_payload()
    assert "# Digest" in parts[0].get_payload()
    assert "<h1>Digest</h1>" in parts[1].get_payload()


# ── send_email ───────────────────────────────────────────────────────


def test_send_email_success():
    msg = build_email("<p>hi</p>", "hi", "a@b.com", "c@d.com", "Test")

    mock_smtp = MagicMock()
    with patch("arxiv_digest.deliver.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        result = send_email(msg, "smtp.example.com", 587, "user", "pass")

    assert result is True
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("user", "pass")
    mock_smtp.sendmail.assert_called_once()


def test_send_email_auth_failure():
    msg = build_email("<p>hi</p>", "hi", "a@b.com", "c@d.com", "Test")

    mock_smtp = MagicMock()
    mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")

    with patch("arxiv_digest.deliver.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        result = send_email(msg, "smtp.example.com", 587, "user", "wrong")

    assert result is False


def test_send_email_connection_failure():
    msg = build_email("<p>hi</p>", "hi", "a@b.com", "c@d.com", "Test")

    with patch("arxiv_digest.deliver.smtplib.SMTP") as smtp_cls:
        smtp_cls.side_effect = ConnectionRefusedError("Connection refused")
        result = send_email(msg, "smtp.example.com", 587, "user", "pass")

    assert result is False
