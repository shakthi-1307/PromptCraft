import json
from groq import AsyncGroq
from fastapi import HTTPException
from app.config import settings
from app.logger import get_logger

log    = get_logger(__name__)
client = AsyncGroq(api_key=settings.GROQ_API_KEY)


async def call_groq(prompt: str, max_tokens: int = 512) -> str:
    """
    Send a prompt to Groq and return the text response.
    Uses llama-3.1-8b-instant by default — fast and free.
    """
    log.info(f"Calling Groq | model: {settings.GROQ_MODEL} | max_tokens: {max_tokens} | prompt_len: {len(prompt)}")

    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
            top_p=0.9,
        )
    except Exception as e:
        error_msg = str(e)

        if "401" in error_msg or "invalid_api_key" in error_msg.lower():
            log.error("Groq API key is invalid or missing")
            raise HTTPException(status_code=500, detail="AI service authentication failed. Contact support.")

        if "429" in error_msg or "rate_limit" in error_msg.lower():
            log.warning("Groq rate limit hit")
            raise HTTPException(status_code=429, detail="AI service is busy. Please try again in a moment.")

        if "503" in error_msg or "unavailable" in error_msg.lower():
            log.error("Groq service unavailable")
            raise HTTPException(status_code=503, detail="AI service is temporarily unavailable. Please try again.")

        log.error(f"Groq API error: {error_msg}")
        raise HTTPException(status_code=500, detail="AI service error. Please try again.")

    result = response.choices[0].message.content
    log.info(f"Groq response received | output_len: {len(result)} | tokens_used: {response.usage.total_tokens}")
    return result


def extract_json_array(raw: str):
    """
    Extract a JSON array from the model response.
    Groq models are much more reliable with JSON than local models,
    but we still handle edge cases defensively.
    """
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # Try direct parse first (Groq usually returns clean JSON)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed]
    except json.JSONDecodeError:
        pass

    # Fall back to bracket extraction
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        log.warning(f"No JSON array found in Groq output: {raw[:200]}")
        return None

    try:
        parsed = json.loads(raw[start:end + 1])
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed]
    except json.JSONDecodeError as e:
        log.warning(f"JSON decode failed: {e} | snippet: {raw[start:end+1][:200]}")
        return None

    return None