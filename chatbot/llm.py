"""Optional LLM enhancement hook.

`enhance_reply()` polishes a rule-based reply. By default it is a pure
rule-based pass (no network, no key needed). Point it at any OpenAI-compatible
chat-completions endpoint to upgrade replies with an LLM:

    export LLM_API_URL="https://api.openai.com/v1/chat/completions"
    export LLM_API_KEY="sk-..."
    export LLM_MODEL="gpt-4o-mini"   # optional

Never hard-code keys — they come from the environment only.
"""

import os

LLM_API_URL = os.environ.get("LLM_API_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")


def _rule_based_enhance(prompt, context):
    """Deterministic fallback: light polish of the draft reply."""
    draft = context.get("draft_reply", "")
    product = context.get("product") or {}
    if not draft:
        return prompt
    reply = draft.strip()
    # Keep replies chat-short; trim runaway drafts.
    if len(reply) > 600:
        reply = reply[:597].rsplit(" ", 1)[0] + "..."
    if product and product.get("name") and product["name"] not in reply:
        reply += f" (P.S. the {product['name']} is in stock today.)"
    return reply


def _llm_enhance(prompt, context):
    import requests

    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system",
             "content": ("You are a friendly sales assistant. Rewrite the draft reply to be "
                         "warm, concise (under 60 words) and persuasive. Keep all facts, "
                         "prices and product names exactly as written. Never invent discounts.")},
            {"role": "user",
             "content": f"Visitor said: {prompt}\n\nDraft reply:\n{context.get('draft_reply', '')}"},
        ],
        "max_tokens": 150,
        "temperature": 0.5,
    }
    resp = requests.post(LLM_API_URL, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def enhance_reply(prompt, context=None):
    """Enhance a draft reply. Rule-based by default; LLM if configured.

    prompt:  the visitor's original message (str)
    context: dict with at least "draft_reply"; may include "product", "state"

    Returns the final reply string. Falls back to the rule-based version if
    the LLM call is unconfigured or fails.
    """
    context = context or {}
    if LLM_API_URL and LLM_API_KEY:
        try:
            return _llm_enhance(prompt, context)
        except Exception:
            pass  # fall through to the deterministic version
    return _rule_based_enhance(prompt, context)
