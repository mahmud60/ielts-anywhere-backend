import logging
import requests as _req
from app.core.config import settings

logger = logging.getLogger(__name__)

_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f9fafb;padding:32px;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e5e7eb;">
    <h2 style="margin:0 0 8px;color:#111827;">{title}</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">{subtitle}</p>
    {body}
    <p style="color:#9ca3af;font-size:12px;margin-top:32px;border-top:1px solid #f3f4f6;padding-top:16px;">
      IELTS Anywhere · <a href="https://ieltsanywhere.app" style="color:#0ea5e9;">ieltsanywhere.app</a>
    </p>
  </div>
</body>
</html>
"""


def _render(title: str, subtitle: str, body: str) -> str:
    return _TEMPLATE.format(title=title, subtitle=subtitle, body=body)


def send_email_sync(to: str, subject: str, html: str) -> None:
    """Synchronous send — called from Celery tasks."""
    if not settings.RESEND_API_KEY:
        logger.info("[EMAIL STUB] to=%s subject=%s", to, subject)
        return
    try:
        _req.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": settings.FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
    except Exception:
        logger.exception("Email send failed to %s", to)


def build_test_complete_email(
    user_name: str,
    overall_band: float | None,
    module_bands: dict,
    session_id: str,
) -> tuple[str, str]:
    """Returns (subject, html) for a completed-test notification."""
    band_str = f"{overall_band:.1f}" if overall_band else "—"
    subject = f"Your IELTS test result: Band {band_str}"

    rows = "".join(
        f'<tr><td style="padding:6px 0;color:#374151;text-transform:capitalize;">{mod}</td>'
        f'<td style="padding:6px 0;font-weight:700;color:#0ea5e9;font-family:monospace;">'
        f'{score:.1f}</td></tr>'
        for mod, score in module_bands.items()
        if score is not None
    )

    body = f"""
    <div style="background:#f0f9ff;border-radius:8px;padding:16px 20px;margin-bottom:20px;">
      <div style="font-size:13px;color:#0369a1;margin-bottom:4px;">Overall Band Score</div>
      <div style="font-size:40px;font-weight:700;color:#0ea5e9;font-family:monospace;">{band_str}</div>
    </div>
    <table style="width:100%;border-collapse:collapse;">
      {rows}
    </table>
    <a href="https://ieltsanywhere.app/test/{session_id}"
       style="display:inline-block;margin-top:20px;padding:10px 22px;background:#0ea5e9;
              color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
      View full results
    </a>
    """

    html = _render(
        title="Your test is complete!",
        subtitle="Here are your IELTS band scores.",
        body=body,
    )
    return subject, html


def build_subscription_email(user_name: str, tier: str) -> tuple[str, str]:
    subject = "Welcome to IELTS Anywhere Pro!"
    body = """
    <p style="color:#374151;font-size:15px;line-height:1.7;">
      Your Pro subscription is now active. You now have access to:
    </p>
    <ul style="color:#374151;font-size:14px;line-height:2;">
      <li>Unlimited full IELTS practice tests</li>
      <li>AI-powered improvement tips per module</li>
      <li>Weakness detection and personalised coaching</li>
      <li>Vocabulary and grammar practice exercises</li>
      <li>Progress tracking with band score charts</li>
    </ul>
    <a href="https://ieltsanywhere.app/dashboard"
       style="display:inline-block;margin-top:16px;padding:10px 22px;background:#0ea5e9;
              color:#fff;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
      Go to dashboard
    </a>
    """
    html = _render(
        title=f"Welcome to Pro, {user_name or 'there'}!",
        subtitle="Your subscription is active.",
        body=body,
    )
    return subject, html
