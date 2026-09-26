"""Core sales conversation engine.

SalesBot is a rule-based sales assistant: it matches visitor messages to a
product catalog, recommends the best fit, handles common buying objections,
scores lead quality, and drives the conversation toward either a lead capture
or a human handoff.

Unlike a support/FAQ bot (which answers questions about things the customer
already owns), this bot is SALES-first: qualify -> recommend -> overcome
objections -> capture the lead -> hand off to a human closer.
"""

import re

# ---------------------------------------------------------------------------
# Demo product catalog. Swap this for a real catalog (DB/CSV/API) in production.
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        "id": "earbuds-pro",
        "name": "AeroBuds Pro",
        "price": 79,
        "currency": "USD",
        "keywords": ["earbuds", "buds", "headphones", "earphones", "audio", "music", "wireless"],
        "blurb": "Wireless noise-cancelling earbuds, 36h battery, IPX5 water resistant.",
    },
    {
        "id": "watch-fit",
        "name": "PulseFit Smartwatch",
        "price": 129,
        "currency": "USD",
        "keywords": ["watch", "smartwatch", "fitness", "tracker", "health", "steps", "heart"],
        "blurb": "Fitness smartwatch with heart-rate + sleep tracking, 10-day battery.",
    },
    {
        "id": "speaker-boom",
        "name": "BoomBox Speaker",
        "price": 59,
        "currency": "USD",
        "keywords": ["speaker", "bluetooth", "party", "sound", "bass", "portable"],
        "blurb": "Portable Bluetooth speaker, deep bass, 20h playtime, splash-proof.",
    },
    {
        "id": "charger-dock",
        "name": "ChargeHub Dock",
        "price": 39,
        "currency": "USD",
        "keywords": ["charger", "charging", "dock", "cable", "power", "usb"],
        "blurb": "3-in-1 fast-charging dock for phone, watch and earbuds.",
    },
]

PRICE_OBJECTION_WORDS = [
    "expensive", "too much", "costly", "pricey", "cheaper", "discount",
    "overpriced", "can't afford", "cannot afford", "budget",
]
SHIPPING_OBJECTION_WORDS = ["shipping", "delivery", "arrive", "ship", "deliver"]
HANDOFF_WORDS = ["human", "agent", "person", "call me", "sales rep", "someone real",
                 "real person", "talk to someone"]
RECOMMEND_WORDS = ["recommend", "suggest", "best", "which one", "what should",
                   "advice", "pick", "choose"]
BUY_WORDS = ["buy", "purchase", "order", "checkout", "add to cart", "i'll take"]
GREETING_WORDS = ["hi", "hello", "hey", "good morning", "good afternoon", "namaste"]

STATES = ("greeting", "qualifying", "recommending", "objection", "capturing", "handoff", "done")


def _contains_any(text, words):
    text = text.lower()
    return any(w in text for w in words)


class SalesBot:
    """Stateful sales conversation engine (one instance, many sessions)."""

    def __init__(self, products=None):
        self.products = products or PRODUCTS
        self.sessions = {}  # session_id -> {"state": ..., "product": ..., "budget": ...}

    # ------------------------------------------------------------------ state
    def _session(self, session_id):
        return self.sessions.setdefault(session_id, {"state": "greeting", "product": None, "budget": None})

    def reset(self, session_id):
        self.sessions.pop(session_id, None)

    # ------------------------------------------------------- product matching
    def match_product(self, text):
        """Return the best-matching product dict for free text, or None.

        Simple keyword scoring: count keyword hits, weight by match density so
        long rambling messages don't beat focused ones.
        """
        words = re.findall(r"[a-z]+", text.lower())
        if not words:
            return None
        best, best_score = None, 0.0
        for product in self.products:
            hits = sum(1 for w in words if w in product["keywords"])
            if hits:
                score = hits / (1 + 0.15 * (len(words) - hits))
                if score > best_score:
                    best, best_score = product, score
        return best

    # --------------------------------------------------------- recommendation
    def recommend(self, budget=None, need_text=""):
        """Pick the best product for a budget (and optional need keywords)."""
        candidates = list(self.products)
        if budget is not None:
            affordable = [p for p in candidates if p["price"] <= budget]
            if affordable:
                candidates = affordable
        if need_text:
            match = self.match_product(need_text)
            if match and match in candidates:
                return match
            if match:
                return match  # need beats budget; flag the stretch below
        return max(candidates, key=lambda p: p["price"])

    # ------------------------------------------------------ objection handling
    def handle_objection(self, text):
        """Return a response string if an objection is detected, else None."""
        low = text.lower()
        if _contains_any(low, SHIPPING_OBJECTION_WORDS):
            return (
                "Good question — shipping is free on orders over $50 and takes "
                "3–5 business days. Express 2-day shipping is available at checkout "
                "for $9. Want me to reserve your item so it ships today?"
            )
        if _contains_any(low, PRICE_OBJECTION_WORDS):
            return (
                "Totally understand — price matters. Two things worth knowing: "
                "(1) every product has a 30-day money-back guarantee, so there's no risk "
                "trying it, and (2) I can apply a 10% first-order discount right now. "
                "Would you like me to hold one for you at the discounted price?"
            )
        if "warranty" in low or "guarantee" in low or "return" in low:
            return (
                "Every product comes with a 1-year warranty and a 30-day no-questions "
                "money-back guarantee. If you're not happy, returns are free. "
                "Shall I set one aside for you?"
            )
        return None

    # ------------------------------------------------------------ lead scoring
    def respond(self, text, session_id="default"):
        """Main entry point: take visitor text, return the bot's reply."""
        session = self._session(session_id)
        state = session["state"]
        text = text.strip()
        low = text.lower()

        # Global intents — work in any state.
        if _contains_any(low, HANDOFF_WORDS):
            session["state"] = "handoff"
            return ("Of course — connecting you with a sales specialist now. "
                    "They usually reply within 5 minutes during business hours. "
                    "Meanwhile, may I have your name and phone number so they can reach you?")

        objection = self.handle_objection(text)
        if objection and state not in ("capturing", "done"):
            session["state"] = "objection"
            return objection

        contact = self._extract_contact(text)
        if contact and state in ("capturing", "handoff", "objection", "recommending"):
            session["state"] = "done"
            name, phone = contact
            return name, phone, True  # caller stores the lead

        if state == "greeting" or _contains_any(low, GREETING_WORDS):
            session["state"] = "qualifying"
            return ("Hi there! Welcome — I can help you find the right product and "
                    "get you the best price. What are you shopping for today? "
                    "(e.g. earbuds, smartwatch, speaker, charger)")

        if state == "qualifying":
            product = self.match_product(text)
            budget = self._extract_budget(text)
            if budget:
                session["budget"] = budget
            if product or budget:
                session["state"] = "recommending"
                pick = self.recommend(budget=session["budget"], need_text=text)
                session["product"] = pick
                stretch = (budget is not None and pick["price"] > budget)
                reply = (f"Based on what you told me, I'd recommend the **{pick['name']}** "
                         f"(${pick['price']}): {pick['blurb']}")
                if stretch:
                    reply += (f" It's slightly above your ${budget} budget, but it's our "
                              "best-seller — and I can offer 10% off your first order.")
                return reply + " Want me to reserve one for you, or prefer to talk to a human?"
            session["state"] = "qualifying"
            return ("Got it. To point you at the right thing: what's your rough budget, "
                    "and is this for yourself or a gift?")

        if state == "recommending":
            if _contains_any(low, RECOMMEND_WORDS):
                pick = self.recommend(budget=session["budget"], need_text=text)
                session["product"] = pick
                return (f"My top pick for you is the **{pick['name']}** (${pick['price']}): "
                        f"{pick['blurb']} Shall I reserve one, or connect you with a specialist?")
            product = self.match_product(text)
            if product:
                session["product"] = product
                session["state"] = "capturing"
                return (f"The **{product['name']}** (${product['price']}) — {product['blurb']} "
                        "It's in stock and ships free over $50. "
                        "Drop your name + phone number and I'll have a specialist confirm your order.")
            if _contains_any(low, BUY_WORDS):
                session["state"] = "capturing"
                name = session["product"]["name"] if session["product"] else "your item"
                return (f"Great choice! To lock in {name}, I just need your name and phone "
                        "number — a specialist will confirm within minutes.")
            return ("I can recommend the right product, check stock, or connect you with "
                    "a human. What would help most?")

        if state == "objection":
            session["state"] = "capturing"
            return ("Makes sense. The fastest way forward: leave your name and phone number, "
                    "and a specialist will sort out pricing/shipping for you personally — "
                    "no obligation.")

        if state == "capturing":
            return ("I just need your name and phone number (or email) to pass to the sales "
                    "team — e.g. `Aarav, 98765 43210`.")

        if state == "handoff":
            return ("A specialist has been notified. Anything else I can help with meanwhile?")

        # state == "done" or anything unexpected: restart gracefully
        self.reset(session_id)
        return self.respond(text, session_id)

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _extract_budget(text):
        m = re.search(r"\$\s?(\d+)|(\d+)\s?(?:usd|dollars|bucks)", text.lower())
        if m:
            return int(m.group(1) or m.group(2))
        return None

    @staticmethod
    def _extract_contact(text):
        """Return (name, contact) if the message looks like name + phone/email."""
        email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        phone = re.search(r"\+?[\d][\d\s\-]{6,14}\d", text)
        name_m = re.search(r"(?:my name is|i am|i'm|this is)\s+([A-Za-z ]{2,40})", text, re.I)
        name = name_m.group(1).strip() if name_m else None
        if not name:
            # "Aarav, 98765 43210" pattern
            parts = [p.strip() for p in re.split(r"[,;]", text) if p.strip()]
            if len(parts) >= 2 and re.fullmatch(r"[A-Za-z ]{2,40}", parts[0]):
                name = parts[0]
        contact = email.group(0) if email else (phone.group(0) if phone else None)
        if contact:
            return name or "Website visitor", contact.strip()
        return None


def score_lead(budget=None, timeline=None, need=None):
    """Score a lead 0–100 from buying signals; return (score, tier).

    budget:   "high" | "medium" | "low" | None
    timeline: "now" | "soon" | "later" | None   (when they want to buy)
    need:     "yes" | "maybe" | "no" | None     (do they need the product)
    """
    score = 20  # baseline: they talked to the bot
    score += {"high": 35, "medium": 20, "low": 5}.get((budget or "").lower(), 0)
    score += {"now": 30, "soon": 15, "later": 0}.get((timeline or "").lower(), 0)
    score += {"yes": 15, "maybe": 7, "no": -10}.get((need or "").lower(), 0)
    score = max(0, min(100, score))
    tier = "hot" if score >= 70 else ("warm" if score >= 40 else "cold")
    return score, tier
