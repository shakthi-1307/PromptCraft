import json
from groq import AsyncGroq
from fastapi import HTTPException
from app.config import settings
from app.logger import get_logger

log    = get_logger(__name__)
client = AsyncGroq(api_key=settings.GROQ_API_KEY)


async def call_groq(prompt: str, max_tokens: int = 512, temperature: float = 0.3) -> str:
    log.info(f"Calling Groq | model: {settings.GROQ_MODEL} | max_tokens: {max_tokens} | prompt_len: {len(prompt)}")
    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
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
    log.info(f"Groq response | output_len: {len(result)} | tokens_used: {response.usage.total_tokens}")
    return result


async def compress_prompt(draft: str) -> str:
    """
    Second-pass compression.
    Takes a draft prompt and strips all filler, enforces key-value structure,
    and targets the absolute minimum tokens needed to convey the same intent.
    """
    compression_instruction = f"""You are a prompt compression expert. Your only job is to rewrite the prompt below into the most token-efficient version possible while preserving 100% of its meaning and intent.

STRICT RULES:
1. Use this exact structure — nothing else:
   Role: [one short phrase]
   Task: [imperative verb + exact object]
   Context: [only facts the AI cannot infer — omit if unnecessary]
   Constraints: [format, length, tone, audience — comma separated]
   Output: [exact format expected]

2. Remove ALL of these without exception:
   - "please", "could you", "I want you to", "I would like", "make sure", "ensure that"
   - Any sentence that restates another sentence
   - Transitional phrases ("First,", "Additionally,", "Finally,")
   - Meta-commentary ("This prompt is for...", "The goal is...")

3. Every word must earn its place. If removing a word does not change what the AI will do — remove it.

4. The output must be under 80 words unless the task is genuinely complex.

5. Return ONLY the compressed prompt. No explanation, no preamble, no markdown, no quotes.

DRAFT PROMPT TO COMPRESS:
{draft}"""

    result = await call_groq(compression_instruction, max_tokens=300, temperature=0.1)
    return result.strip()


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using the standard approximation:
    1 token ≈ 4 characters for English text.
    This matches GPT/Claude tokenizers closely enough for display purposes.
    """
    return max(1, len(text) // 4)


def extract_json_array(raw: str):
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed]
    except json.JSONDecodeError:
        pass

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