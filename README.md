# AI Sales Chatbot

An AI sales chatbot for websites + WhatsApp: product Q&A, smart recommendations,
objection handling, lead capture with scoring, and human handoff.

**The problem it solves:** most businesses lose website visitors who browse but never
talk to sales. A static site can't qualify a visitor, answer "is this too expensive?",
or capture a phone number at 2 AM. This bot is a 24/7 sales rep: it greets visitors,
matches them to the right product, handles price/shipping objections, scores the lead,
and hands hot leads to a human closer — on the website or over WhatsApp.

> Note: this is a **sales** bot (qualify → recommend → close). It is deliberately
> different from a FAQ/support bot, which answers questions about products people
> already own.

## Features

- 🛍️ **Product catalog matching** — keyword + density scoring maps free text to the right product
- 🎯 **Recommendations** — picks the best fit for budget + stated need
- 🛡️ **Objection handling** — price, shipping, warranty/returns responses that keep the sale alive
- 🔥 **Lead scoring** — budget × timeline × need signals → hot / warm / cold tiers (0–100)
- 📋 **Lead capture** — validates name + phone/email, stores to CSV, optional CRM webhook POST
- 🧑‍💼 **Human handoff** — detects "talk to a human" intent and routes to a specialist
- 💬 **WhatsApp** — Twilio webhook reusing the same engine (`POST /whatsapp`)
- 🔌 **LLM hook** — optional reply polishing via any OpenAI-compatible API (rule-based by default, no key needed)
- 🧩 **Embeddable widget** — vanilla JS chat UI, no build step

## Conversation flow

```
Visitor ──► greeting ──► qualifying ──► recommending ──► capturing ──► done
                │              │                │              │
                │              ▼                ▼              ▼
                │         objection ──────► handoff ──► specialist notified
                │         (price/shipping/    │
                └────────► warranty)          └── contact captured → CSV + webhook
```

State is tracked per `session_id`, so web and WhatsApp conversations stay independent.

## Quickstart (demo)

```bash
pip install -r requirements.txt
python app.py
# open http://localhost:5000
```

Try: `Hi` → `I need wireless earbuds under $100` → `That's too expensive`
→ `Aarav, 9876543210` (lead captured + scored).

## WhatsApp setup (Twilio)

1. `pip install -r requirements.txt` and expose the app publicly (e.g. `ngrok http 5000`).
2. In the Twilio Console → Messaging → WhatsApp sandbox, set the webhook to
   `https://YOUR-URL/whatsapp` (POST).
3. Message the sandbox number — the same sales engine replies, and captured
   leads are tagged `source=whatsapp` in `leads.csv`.

## Configuration (env vars)

| Variable | Purpose |
|---|---|
| `LEADS_CSV` | Path for the leads CSV (default `leads.csv`) |
| `LEAD_WEBHOOK_URL` | Optional CRM endpoint — every lead is POSTed as JSON |
| `LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL` | Optional OpenAI-compatible endpoint for reply polishing |

No keys are stored in code. The bot works fully offline with the rule-based engine.

## API

- `GET /` — chat widget demo page
- `POST /api/chat` — `{"message": "...", "session_id": "..."}` → `{"reply": "...", "session_id": "...", "lead_saved": bool}`
- `GET /api/products` — product catalog as JSON
- `POST /whatsapp` — Twilio WhatsApp webhook (TwiML response)

## Tech stack

Python · Flask · Twilio (WhatsApp) · vanilla JS widget · pytest

## Run the tests

```bash
python -m pytest tests/ -q
```

## Project layout

```
app.py                 Flask app: demo page + /api/chat + /whatsapp
chatbot/
  sales_bot.py         SalesBot: matching, recommendations, objections, scoring, state machine
  lead_capture.py      lead validation, CSV storage, CRM webhook
  llm.py               optional LLM reply-enhancement hook
  whatsapp.py          Twilio WhatsApp webhook (reuses SalesBot)
templates/index.html   embeddable chat widget demo
static/style.css       widget styles
tests/test_bot.py      pytest suite (no network, no keys)
```

## License

MIT — use it in client projects freely.
