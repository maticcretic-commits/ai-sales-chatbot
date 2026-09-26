"""Flask entry point: widget demo page + chat API + WhatsApp webhook."""

import uuid

from flask import Flask, jsonify, render_template, request

from chatbot.sales_bot import SalesBot, score_lead
from chatbot.lead_capture import save_lead
from chatbot.llm import enhance_reply
from chatbot.whatsapp import whatsapp_bp

app = Flask(__name__)
app.register_blueprint(whatsapp_bp)

bot = SalesBot()
USE_LLM_ENHANCEMENT = False  # flip on once LLM_API_URL/LLM_API_KEY are set


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    if not message:
        return jsonify({"reply": "Send me a message to get started!", "session_id": session_id})

    reply = bot.respond(message, session_id=session_id)
    lead_saved = False

    if isinstance(reply, tuple) and len(reply) == 3 and reply[2] is True:
        name, contact, _ = reply
        session = bot.sessions.get(session_id, {})
        product = session.get("product") or {}
        score, tier = score_lead(budget="medium" if session.get("budget") else None,
                                 timeline="soon", need="yes")
        ok, record = save_lead(name, contact, interest=product.get("name", ""),
                               score=score, source="web")
        lead_saved = ok
        reply = (f"Thanks {record['name'] if ok else name}! Our sales team will reach out "
                 f"shortly at {contact}. You're marked as a **{tier}** lead — expect a quick call.")

    if isinstance(reply, str) and USE_LLM_ENHANCEMENT:
        session = bot.sessions.get(session_id, {})
        reply = enhance_reply(message, {"draft_reply": reply,
                                        "product": session.get("product"),
                                        "state": session.get("state")})

    return jsonify({"reply": reply, "session_id": session_id, "lead_saved": lead_saved})


@app.route("/api/products")
def products():
    return jsonify(bot.products)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
