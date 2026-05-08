import pytest
from unittest.mock import patch, MagicMock
from app.services.email import (
    _render, send_email_sync, build_test_complete_email, build_subscription_email
)
from app.core.config import settings

def test_render():
    html = _render("Title", "Subtitle", "<p>Body</p>")
    assert "Title" in html
    assert "Subtitle" in html
    assert "<p>Body</p>" in html
    assert "IELTS Anywhere" in html

@patch("app.services.email._req.post")
def test_send_email_sync(mock_post):
    with patch.object(settings, "RESEND_API_KEY", "test_key"):
        send_email_sync("to@example.com", "Subject", "<p>Html</p>")
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["to"] == ["to@example.com"]
        assert kwargs["json"]["subject"] == "Subject"

def test_send_email_sync_no_key():
    with patch.object(settings, "RESEND_API_KEY", None):
        with patch("app.services.email.logger.info") as mock_logger:
            send_email_sync("to@example.com", "Subject", "<p>Html</p>")
            assert mock_logger.called
            assert "[EMAIL STUB]" in mock_logger.call_args[0][0]

def test_build_test_complete_email():
    module_bands = {"reading": 7.5, "listening": 8.0}
    subject, html = build_test_complete_email("John", 7.5, module_bands, "session_123")
    assert "7.5" in subject
    assert "Your test is complete!" in html
    assert "reading" in html
    assert "7.5" in html
    assert "listening" in html
    assert "8.0" in html
    assert "session_123" in html

def test_build_subscription_email():
    subject, html = build_subscription_email("John", "pro")
    assert "Welcome to IELTS Anywhere Pro!" in subject
    assert "Welcome to Pro, John!" in html
    assert "dashboard" in html
