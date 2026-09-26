"""Lead capture: validate, store to CSV, optionally POST to a webhook."""

import csv
import os
import re
from datetime import datetime, timezone

LEADS_CSV = os.environ.get("LEADS_CSV", "leads.csv")
LEAD_WEBHOOK_URL = os.environ.get("LEAD_WEBHOOK_URL", "")  # optional

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s\-]{7,16}$")


def validate_lead(name, contact, interest="", score=0):
    """Return (ok, errors). contact must be a valid email or phone number."""
    errors = []
    if not name or len(name.strip()) < 2:
        errors.append("name must be at least 2 characters")
    contact = (contact or "").strip()
    digits = re.sub(r"\D", "", contact)
    is_email = bool(EMAIL_RE.match(contact))
    is_phone = bool(PHONE_RE.match(contact)) and 7 <= len(digits) <= 15
    if not (is_email or is_phone):
        errors.append("contact must be a valid email or phone number")
    try:
        score = int(score)
    except (TypeError, ValueError):
        errors.append("score must be a number")
    return (len(errors) == 0), errors


def build_lead_record(name, contact, interest="", score=0, source="web"):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name.strip(),
        "contact": contact.strip(),
        "interest": interest.strip(),
        "score": int(score),
        "source": source,
    }


def save_lead(name, contact, interest="", score=0, source="web", csv_path=None):
    """Validate and append a lead to CSV; POST to webhook if configured.

    Returns (ok, result) where result is the lead record or a list of errors.
    The webhook is best-effort: a failed POST never blocks the save.
    """
    ok, errors = validate_lead(name, contact, interest, score)
    if not ok:
        return False, errors
    record = build_lead_record(name, contact, interest, score, source)
    path = csv_path or LEADS_CSV
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(record.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(record)
    if LEAD_WEBHOOK_URL:
        post_to_webhook(record, LEAD_WEBHOOK_URL)
    return True, record


def post_to_webhook(record, url):
    """POST the lead JSON to a CRM/webhook URL. Returns True on 2xx."""
    import requests

    try:
        resp = requests.post(url, json=record, timeout=10)
        return 200 <= resp.status_code < 300
    except Exception:
        return False
