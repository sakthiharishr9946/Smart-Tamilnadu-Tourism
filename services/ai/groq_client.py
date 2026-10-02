from groq import Groq

from config.settings import GROQ_API_KEY, GROQ_MODEL

# Every caller treats a missing/failed AI response as "fall back to the
# deterministic, database-grounded text" rather than an error — the app must
# work identically with no Groq key configured at all.

_client = None


def is_ai_enabled():
    return bool(GROQ_API_KEY)


def _get_client():
    global _client

    if _client is None and GROQ_API_KEY:
        _client = Groq(api_key=GROQ_API_KEY)

    return _client


def generate_ai_text(system_prompt, user_prompt, max_tokens=350, temperature=0.6):
    client = _get_client()

    if client is None:
        return None

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            # The available gpt-oss models are reasoning models that spend
            # tokens on hidden reasoning before the visible answer; "low"
            # keeps that overhead small so max_tokens isn't consumed before
            # any user-facing text is produced.
            reasoning_effort="low",
        )

        text = completion.choices[0].message.content

        return text.strip() if text else None
    except Exception:
        return None
