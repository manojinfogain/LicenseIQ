"""
Email notification service for LicenseIQ.
Uses Gmail SMTP with a Google Workspace App Password.

Setup (one-time):
1. Enable 2-Step Verification on the sender Google account.
2. Go to myaccount.google.com → Security → App passwords.
3. Create an app password and copy the 16-char key.
4. Set the following in your .env:
       EMAIL_ENABLED=true
       EMAIL_SENDER=licenseiq@yourdomain.com
       EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
       EMAIL_ADMIN=admin@yourdomain.com
"""

import logging
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _fmt_date(date_str: str | None) -> str | None:
    """Convert any ISO/date string to dd-mm-yy format."""
    if not date_str:
        return None
    try:
        # Handle both 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS' variants
        dt = datetime.fromisoformat(str(date_str).split("T")[0].split(" ")[0])
        return dt.strftime("%d-%m-%y")
    except (ValueError, AttributeError):
        return str(date_str)

# ─── Colour palette used in email templates ───────────────────────────────────
_C = {
    "black": "#111111",
    "lime": "#8DC63F",
    "red": "#D94040",
    "gray": "#6B6B6B",
    "border": "#E5E1D8",
    "bg": "#F5F2EC",
}


def _send(subject: str, html_body: str, recipients: list[str]) -> None:
    """Low-level SMTP send — runs in a daemon thread so it never blocks the API."""
    if not settings.email_enabled:
        logger.debug("[EMAIL] Skipped (EMAIL_ENABLED=false): %s", subject)
        return
    if not settings.email_sender or not settings.email_app_password:
        logger.warning("[EMAIL] EMAIL_SENDER or EMAIL_APP_PASSWORD not configured — skipping.")
        return

    # Deduplicate and filter empty addresses
    to_list = list({r.strip() for r in recipients if r and r.strip()})
    if not to_list:
        logger.warning("[EMAIL] No recipients — skipping: %s", subject)
        return

    def _worker():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"LicenseIQ <{settings.email_sender}>"
            msg["To"] = ", ".join(to_list)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.email_sender, settings.email_app_password)
                server.sendmail(settings.email_sender, to_list, msg.as_string())
            logger.info("[EMAIL] Sent '%s' to %s", subject, to_list)
        except Exception as exc:
            logger.error("[EMAIL] Failed to send '%s': %s", subject, exc)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ─── HTML wrapper ─────────────────────────────────────────────────────────────
def _wrap(title: str, body_html: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{font-family:Arial,sans-serif;background:{_C['bg']};margin:0;padding:0;}}
    .wrap {{max-width:560px;margin:32px auto;background:#fff;border-radius:10px;
            border:1px solid {_C['border']};overflow:hidden;}}
    .hdr {{background:{_C['black']};padding:18px 28px;display:flex;align-items:center;gap:12px;}}
    .hdr-logo {{color:{_C['lime']};font-size:22px;font-weight:800;letter-spacing:-0.5px;}}
    .hdr-sub {{color:#aaa;font-size:12px;margin-top:2px;}}
    .body {{padding:28px 28px 20px;}}
    h2 {{margin:0 0 16px;font-size:18px;color:{_C['black']};}}
    .card {{background:{_C['bg']};border:1px solid {_C['border']};border-radius:8px;
            padding:16px 18px;margin-bottom:16px;}}
    .row {{display:flex;gap:8px;margin-bottom:6px;font-size:13px;}}
    .lbl {{color:{_C['gray']};min-width:110px;font-weight:600;}}
    .val {{color:{_C['black']};}}
    .badge {{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;
             font-weight:700;text-transform:uppercase;letter-spacing:.5px;}}
    .badge-assign {{background:#d4f4b7;color:#2e6b00;}}
    .badge-revoke {{background:#fde8e8;color:#a00;}}
    .badge-executed {{background:#d4f4b7;color:#2e6b00;}}
    .footer {{background:{_C['bg']};padding:12px 28px;font-size:11px;color:{_C['gray']};
              border-top:1px solid {_C['border']};}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hdr">
      <div>
        <div class="hdr-logo">LicenseIQ</div>
        <div class="hdr-sub">License Management System</div>
      </div>
    </div>
    <div class="body">
      <h2>{title}</h2>
      {body_html}
    </div>
    <div class="footer">This is an automated notification from LicenseIQ. Do not reply to this email.</div>
  </div>
</body>
</html>
"""


# ─── Public notification functions ───────────────────────────────────────────
def notify_request_raised(
    *,
    request_type: str,           # "assign" or "revoke"
    employee_name: str,
    employee_email: str | None,
    platform_name: str,
    project_name: str | None,
    account_name: str | None,
    requester_name: str | None,
    requester_email: str | None,
    effective_date: str | None,
) -> None:
    action_label = "Assign" if request_type == "assign" else "Revoke"
    badge_cls = "badge-assign" if request_type == "assign" else "badge-revoke"
    subject = f"[LicenseIQ] License {action_label} Request — {employee_name} / {platform_name}"
    fmt_date = _fmt_date(effective_date)

    body = f"""
    <div class="card">
      <div class="row"><span class="lbl">Action</span>
        <span class="val"><span class="badge {badge_cls}">{action_label}</span></span></div>
      <div class="row"><span class="lbl">Employee</span><span class="val">{employee_name}</span></div>
      <div class="row"><span class="lbl">Platform</span><span class="val">{platform_name}</span></div>
      {'<div class="row"><span class="lbl">Project</span><span class="val">'+project_name+'</span></div>' if project_name else ''}
      {'<div class="row"><span class="lbl">Account</span><span class="val">'+account_name+'</span></div>' if account_name else ''}
      {'<div class="row"><span class="lbl">Raised By</span><span class="val">'+requester_name+'</span></div>' if requester_name else ''}
      {'<div class="row"><span class="lbl">Effective Date</span><span class="val">'+fmt_date+'</span></div>' if fmt_date else ''}
    </div>
    <p style="font-size:13px;color:{_C['gray']};">
      This request has been self-approved and is now in the <strong>Action Queue</strong>
      awaiting execution by the License Admin.
    </p>
    """

    recipients = [
      r for r in [settings.email_admin, employee_email] if r
    ]
    _send(subject, _wrap(f"New {action_label} Request Raised", body), recipients)


def notify_request_executed(
    *,
    action_type: str,            # "assign" or "revoke"
    employee_name: str,
    employee_email: str | None,
    platform_name: str,
    project_name: str | None,
    executed_by: str | None,
    requester_email: str | None,
) -> None:
    action_label = "Assigned" if action_type == "assign" else "Revoked"
    badge_cls = "badge-executed"
    subject = f"[LicenseIQ] License {action_label} — {employee_name} / {platform_name}"

    body = f"""
    <div class="card">
      <div class="row"><span class="lbl">Status</span>
        <span class="val"><span class="badge {badge_cls}">{action_label}</span></span></div>
      <div class="row"><span class="lbl">Employee</span><span class="val">{employee_name}</span></div>
      <div class="row"><span class="lbl">Platform</span><span class="val">{platform_name}</span></div>
      {'<div class="row"><span class="lbl">Project</span><span class="val">'+project_name+'</span></div>' if project_name else ''}
      {'<div class="row"><span class="lbl">Executed By</span><span class="val">'+executed_by+'</span></div>' if executed_by else ''}
    </div>
    <p style="font-size:13px;color:{_C['gray']};">
      The license action has been executed and the allocation records have been updated.
    </p>
    """

    recipients = [
      r for r in [settings.email_admin, employee_email] if r
    ]
    _send(subject, _wrap(f"License {action_label}", body), recipients)
