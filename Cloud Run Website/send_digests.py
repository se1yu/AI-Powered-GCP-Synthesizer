"""Send due personalized digests.

Run this as a daily Cloud Run Job. Each subscriber's ``next_send_at`` keeps
weekly, biweekly, and monthly deliveries on the schedule they selected.
"""

from __future__ import annotations

import html
import json
import logging
import os
import smtplib
from email.message import EmailMessage

from google import genai
from google.genai import types

from release_agent.config import SETTINGS
from release_agent.sources import fetch_service_health, get_recent_summary
from release_agent.subscriptions import get_due_subscribers, mark_subscription_sent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_digest(subscriber: dict) -> str:
    days = int(subscriber["frequency_days"])
    releases = get_recent_summary(days_back=days)
    incidents = fetch_service_health(active_only=True)
    evidence = json.dumps(
        {"release_activity": releases, "active_incidents": incidents},
        default=str,
    )
    prompt = f"""
Write a concise personalized Google Cloud update email for
{subscriber["first_name"]}, whose industry is {subscriber["industry"]}.
Cover the most relevant new releases and active outage incidents. Explain
briefly why the important items matter to that industry, but never invent
customer facts or claims beyond the evidence. Prioritize breaking changes,
security, deprecations, and incidents. If no incident is active, explicitly
say service health shows no active incident. Use short headings and bullets.
Do not add a subject line, greeting, sign-off, or unsupported recommendation.

Evidence:
{evidence}
"""
    client = genai.Client(
        vertexai=True,
        project=SETTINGS.project,
        location=SETTINGS.vertex_location,
    )
    response = client.models.generate_content(
        model=SETTINGS.model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    return response.text or "No notable Google Cloud updates were found for this period."


def _send_email(subscriber: dict, digest: str) -> None:
    host = os.environ["PULSE_SMTP_HOST"]
    port = int(os.environ.get("PULSE_SMTP_PORT", "587"))
    username = os.environ.get("PULSE_SMTP_USERNAME", "")
    password = os.environ.get("PULSE_SMTP_PASSWORD", "")
    sender = os.environ["PULSE_EMAIL_FROM"]
    app_url = os.environ.get("PULSE_APP_URL", "").rstrip("/")
    unsubscribe_url = (
        f"{app_url}/?nav=subscribe&unsubscribe={subscriber['unsubscribe_token']}"
        if app_url
        else ""
    )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = subscriber["email"]
    message["Subject"] = f"Cloud Comms: your {subscriber['frequency'].lower()} update"
    footer = f"\n\nUnsubscribe: {unsubscribe_url}" if unsubscribe_url else ""
    message.set_content(f"Hi {subscriber['first_name']},\n\n{digest}{footer}")
    html_footer = (
        "<p style='margin-top:24px;font-size:12px'>"
        f"<a href='{html.escape(unsubscribe_url, quote=True)}'>Unsubscribe</a></p>"
        if unsubscribe_url
        else ""
    )
    message.add_alternative(
        "<p>Hi " + html.escape(subscriber["first_name"]) + ",</p>"
        + "<div style='font-family:Arial,sans-serif;line-height:1.5;white-space:pre-wrap'>"
        + html.escape(digest)
        + "</div>"
        + html_footer,
        subtype="html",
    )

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


def main() -> None:
    sent = 0
    failed = 0
    for subscriber in get_due_subscribers():
        try:
            digest = _build_digest(subscriber)
            _send_email(subscriber, digest)
            mark_subscription_sent(subscriber["email"], int(subscriber["frequency_days"]))
            sent += 1
        except Exception:  # noqa: BLE001 - continue so one address cannot stop the batch
            failed += 1
            logger.exception("Digest failed for %s", subscriber["email"])
    logger.info("Digest run complete: %d sent, %d failed", sent, failed)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
