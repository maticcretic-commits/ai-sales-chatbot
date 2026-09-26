"""Sales-bot test suite: no network, no API keys."""

import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chatbot.sales_bot import SalesBot, score_lead
from chatbot.lead_capture import validate_lead, save_lead
from chatbot.llm import enhance_reply


@pytest.fixture()
def bot():
    return SalesBot()


# ------------------------------------------------------- product matching
def test_product_matching_returns_right_product(bot):
    assert bot.match_product("do you have wireless earbuds?")["id"] == "earbuds-pro"
    assert bot.match_product("I want a fitness smartwatch")["id"] == "watch-fit"
    assert bot.match_product("need a bluetooth speaker for a party")["id"] == "speaker-boom"
    assert bot.match_product("fast charger dock please")["id"] == "charger-dock"


def test_product_matching_none_on_irrelevant(bot):
    assert bot.match_product("what is the weather today") is None
    assert bot.match_product("") is None


def test_recommendation_respects_budget(bot):
    pick = bot.recommend(budget=50)
    assert pick["price"] <= 50
    pick = bot.recommend(budget=50, need_text="smartwatch")
    assert pick["id"] == "watch-fit"  # need wins over budget


# ------------------------------------------------------ objection handling
def test_objection_handler_price(bot):
    reply = bot.handle_objection("that's too expensive for me")
    assert reply is not None
    assert "discount" in reply.lower() or "guarantee" in reply.lower()


def test_objection_handler_shipping(bot):
    reply = bot.handle_objection("how long does shipping take?")
    assert reply is not None
    assert "ship" in reply.lower()


def test_objection_handler_none(bot):
    assert bot.handle_objection("I love the design") is None


def test_objection_flows_through_respond(bot):
    reply = bot.respond("hi", session_id="obj1")
    assert "shopping for" in reply.lower()
    reply = bot.respond("too pricey", session_id="obj1")
    assert "discount" in reply.lower() or "guarantee" in reply.lower()


# ------------------------------------------------------------ lead scoring
def test_lead_scoring_hot_warm_cold():
    hot_score, hot_tier = score_lead(budget="high", timeline="now", need="yes")
    warm_score, warm_tier = score_lead(budget="medium", timeline="soon", need="maybe")
    cold_score, cold_tier = score_lead(budget="low", timeline="later", need="no")
    assert hot_tier == "hot" and warm_tier == "warm" and cold_tier == "cold"
    assert hot_score > warm_score > cold_score


def test_lead_scoring_bounds():
    score, _ = score_lead()
    assert 0 <= score <= 100
    score, _ = score_lead(budget="high", timeline="now", need="yes")
    assert score <= 100


# ---------------------------------------------------------- lead validation
def test_lead_validation_rejects_bad_contact():
    ok, errors = validate_lead("Aarav", "not-a-phone")
    assert not ok and errors
    ok, _ = validate_lead("A", "9876543210")
    assert not ok  # name too short
    ok, _ = validate_lead("", "user@example.com")
    assert not ok


def test_lead_validation_accepts_good_contact():
    ok, errors = validate_lead("Aarav Sharma", "98765 43210")
    assert ok, errors
    ok, errors = validate_lead("Aarav Sharma", "aarav@example.com")
    assert ok, errors


def test_save_lead_writes_csv(tmp_path, monkeypatch):
    path = str(tmp_path / "leads.csv")
    monkeypatch.setenv("LEADS_CSV", path)
    import importlib
    import chatbot.lead_capture as lc
    importlib.reload(lc)
    ok, record = lc.save_lead("Aarav", "9876543210", interest="AeroBuds Pro",
                              score=85, source="web", csv_path=path)
    assert ok
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["name"] == "Aarav"
    assert rows[0]["score"] == "85"


def test_save_lead_rejects_invalid():
    ok, errors = save_lead("Aarav", "bad-contact", csv_path="/tmp/should-not-exist.csv")
    assert not ok and errors


# ------------------------------------------------------ webhook payload
def test_whatsapp_webhook_payload():
    from app import app
    client = app.test_client()
    resp = client.post("/whatsapp", data={
        "From": "whatsapp:+15551234567",
        "Body": "Hi, I'm looking for earbuds",
        "ProfileName": "Test User",
    })
    assert resp.status_code == 200
    assert b"<Response>" in resp.data
    assert b"Message" in resp.data


def test_api_chat_endpoint():
    from app import app
    client = app.test_client()
    resp = client.post("/api/chat", json={"message": "Hi", "session_id": "t1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reply" in data and data["session_id"] == "t1"


def test_api_chat_contact_capture_saves_lead(tmp_path):
    from app import app
    import chatbot.lead_capture as lc
    path = str(tmp_path / "leads.csv")
    lc.LEADS_CSV = path
    try:
        client = app.test_client()
        client.post("/api/chat", json={"message": "hi", "session_id": "cap1"})
        client.post("/api/chat", json={"message": "earbuds under $100", "session_id": "cap1"})
        resp = client.post("/api/chat", json={"message": "Aarav, 9876543210", "session_id": "cap1"})
        data = resp.get_json()
        assert data["lead_saved"] is True
        assert os.path.exists(path)
    finally:
        lc.LEADS_CSV = os.environ.get("LEADS_CSV", "leads.csv")


# --------------------------------------------------------------- llm hook
def test_enhance_reply_rule_based_default():
    out = enhance_reply("hi", {"draft_reply": "Hello! How can I help you today?"})
    assert "Hello" in out  # no LLM configured -> deterministic pass-through


def test_conversation_state_machine(bot):
    r1 = bot.respond("hello", session_id="sm1")
    assert bot.sessions["sm1"]["state"] == "qualifying"
    r2 = bot.respond("I need a smartwatch under $150", session_id="sm1")
    assert bot.sessions["sm1"]["state"] == "recommending"
    assert "PulseFit" in r2
    r3 = bot.respond("connect me to a human", session_id="sm1")
    assert bot.sessions["sm1"]["state"] == "handoff"
    assert "specialist" in r3.lower()
