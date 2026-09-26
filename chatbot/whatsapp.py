"""Twilio WhatsApp webhook: reuses SalesBot + lead capture over WhatsApp."""

from flask import Blueprint, request, Response

from .sales_bot import SalesBot
from .lead_capture import save_lead

whatsapp_bp = Blueprint("whatsapp", __name__)
_bot = SalesBot()


def _twiml(message):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{_escape(message)}</Message></Response>"
    )


def _escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


@whatsapp_bp.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Twilio posts form fields: From (whatsapp:+123...), Body, ProfileName."""
    sender = request.form.get("From", "unknown")
    body = request.form.get("Body", "")
    profile_name = request.form.get("ProfileName", "")

    reply = _bot.respond(body, session_id=sender)

    # SalesBot returns (name, contact, True) when contact details are captured.
    if isinstance(reply, tuple) and len(reply) == 3 and reply[2] is True:
        name, contact, _ = reply
        name = name if name != "Website visitor" else (profile_name or "WhatsApp visitor")
        product = _bot.sessions.get(sender, {}).get("product") or {}
        ok, _ = save_lead(name, contact,
                          interest=product.get("name", ""),
                          source="whatsapp")
        reply = ("Thanks {}! I've passed your details to our sales team — "
                 "they'll message you here shortly.".format(name) if ok
                 else "Thanks! Could you resend your phone number? I couldn't save it.")

    return Response(_twiml(reply if isinstance(reply, str) else str(reply)),
                    mimetype="text/xml")
