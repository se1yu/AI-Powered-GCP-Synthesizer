"""Subscription persistence for personalized Cloud Comms email digests."""

from __future__ import annotations

import re
import uuid

from google.cloud import bigquery

from release_agent.config import SETTINGS
from release_agent.sources import get_bigquery_client

FREQUENCIES = {
    "Weekly": 7,
    "Every 2 weeks": 14,
    "Monthly": 30,
}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def save_subscription(
    first_name: str, email: str, industry: str, frequency: str
) -> dict[str, str | bool]:
    """Creates or updates one active subscription, keyed by email address."""
    first_name = first_name.strip()
    email = email.strip().lower()
    industry = industry.strip()
    if not first_name or not email or not industry or frequency not in FREQUENCIES:
        return {"ok": False, "message": "Please complete every field."}
    if not _EMAIL_RE.fullmatch(email):
        return {"ok": False, "message": "Enter a valid email address."}

    sql = f"""
        MERGE `{SETTINGS.subscribers_table_fqn}` T
        USING (
          SELECT @email AS email, @first_name AS first_name,
                 @industry AS industry, @frequency AS frequency,
                 @frequency_days AS frequency_days, @token AS unsubscribe_token
        ) S
        ON T.email = S.email
        WHEN MATCHED THEN UPDATE SET
          first_name = S.first_name, industry = S.industry,
          frequency = S.frequency, frequency_days = S.frequency_days,
          active = TRUE, updated_at = CURRENT_TIMESTAMP(),
          next_send_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (
          email, first_name, industry, frequency, frequency_days, active,
          created_at, updated_at, next_send_at, last_sent_at, unsubscribe_token
        ) VALUES (
          S.email, S.first_name, S.industry, S.frequency, S.frequency_days, TRUE,
          CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), NULL,
          S.unsubscribe_token
        )
    """
    params = [
        bigquery.ScalarQueryParameter("email", "STRING", email),
        bigquery.ScalarQueryParameter("first_name", "STRING", first_name),
        bigquery.ScalarQueryParameter("industry", "STRING", industry),
        bigquery.ScalarQueryParameter("frequency", "STRING", frequency),
        bigquery.ScalarQueryParameter("frequency_days", "INT64", FREQUENCIES[frequency]),
        bigquery.ScalarQueryParameter("token", "STRING", str(uuid.uuid4())),
    ]
    try:
        config = bigquery.QueryJobConfig(query_parameters=params)
        get_bigquery_client().query(sql, job_config=config).result()
    except Exception:
        return {
            "ok": False,
            "message": "We couldn't save your subscription right now. Please try again.",
        }
    return {
        "ok": True,
        "message": f"You're subscribed to a {frequency.lower()} digest.",
    }


def get_due_subscribers(limit: int = 500) -> list[dict]:
    """Returns active subscriptions whose next delivery time has arrived."""
    sql = f"""
        SELECT email, first_name, industry, frequency, frequency_days,
               unsubscribe_token
        FROM `{SETTINGS.subscribers_table_fqn}`
        WHERE active = TRUE AND next_send_at <= CURRENT_TIMESTAMP()
        ORDER BY next_send_at
        LIMIT @limit
    """
    config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    )
    rows = get_bigquery_client().query(sql, job_config=config).result()
    return [dict(row.items()) for row in rows]


def mark_subscription_sent(email: str, frequency_days: int) -> None:
    """Advances a subscription only after its email was accepted by SMTP."""
    sql = f"""
        UPDATE `{SETTINGS.subscribers_table_fqn}`
        SET last_sent_at = CURRENT_TIMESTAMP(),
            next_send_at = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL @days DAY),
            updated_at = CURRENT_TIMESTAMP()
        WHERE email = @email AND active = TRUE
    """
    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("email", "STRING", email),
            bigquery.ScalarQueryParameter("days", "INT64", frequency_days),
        ]
    )
    get_bigquery_client().query(sql, job_config=config).result()


def unsubscribe(token: str) -> bool:
    """Disables the subscription matching an opaque unsubscribe token."""
    if not token:
        return False
    sql = f"""
        UPDATE `{SETTINGS.subscribers_table_fqn}`
        SET active = FALSE, updated_at = CURRENT_TIMESTAMP()
        WHERE unsubscribe_token = @token AND active = TRUE
    """
    config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("token", "STRING", token)]
    )
    job = get_bigquery_client().query(sql, job_config=config)
    job.result()
    return bool(job.num_dml_affected_rows)
