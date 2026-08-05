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


async def compress_prompt(draft: str, answered_points: str = "") -> str:
    """
    Second-pass compression.
    Removes filler words and redundant phrasing ONLY.
    Every piece of content the user provided must survive intact.
    """
    preservation_block = f"""
CONTENT THAT MUST BE PRESERVED (do not remove or summarize any of these):
{answered_points}
""" if answered_points.strip() else ""

    compression_instruction = f"""You are a prompt compression expert. Rewrite the prompt below to be more concise by removing ONLY filler words and redundant phrasing.

STRICT RULES:
1. NEVER remove specific facts, points, or details — only remove the words around them
2. NEVER merge two distinct points into one if information is lost
3. Remove ONLY: "please", "could you", "I want you to", "I would like", "make sure", "ensure that", transitional phrases, meta-commentary
4. Keep the exact Role/Task/Context/Constraints/Output structure
5. Context field must retain ALL specific details — shorten the words, not the content
6. Return ONLY the compressed prompt. No explanation, no preamble, no markdown.
{preservation_block}
DRAFT TO COMPRESS:
{draft}"""

    result = await call_groq(compression_instruction, max_tokens=400, temperature=0.1)
    return result.strip()


async def check_coverage(questions: list, answers: list, final_prompt: str) -> list:
    """
    For each Q&A pair, check whether the answer's intent is reflected
    in the final prompt — directly or indirectly.
    Returns a list of dicts: {question, answer, covered: bool, reason: str}
    """
    qa_block = "\n".join(
        f"{i+1}. Q: {q}\n   A: {a}"
        for i, (q, a) in enumerate(zip(questions, answers))
        if a.strip()
    )

    check_instruction = f"""You are verifying whether a user's answers are reflected in an AI prompt.

For each Q&A pair below, determine if the answer's meaning or intent is present in the final prompt — either directly (same words) or indirectly (same meaning expressed differently).

Q&A PAIRS:
{qa_block}

FINAL PROMPT:
{final_prompt}

For each numbered Q&A pair, respond with ONLY a JSON array in this exact format — nothing else:
[
  {{"index": 1, "covered": true, "reason": "one short phrase explaining how it's covered"}},
  {{"index": 2, "covered": false, "reason": "one short phrase explaining what's missing"}}
]

Rules:
- covered: true if the answer's meaning appears anywhere in the prompt
- covered: false only if the answer's intent is completely absent
- reason: under 8 words
- Return ONLY the JSON array. No explanation, no preamble."""

    try:
        raw = await call_groq(check_instruction, max_tokens=300, temperature=0.0)
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)

        results = []
        for i, (q, a) in enumerate(zip(questions, answers)):
            if not a.strip():
                continue
            match = next((item for item in parsed if item.get("index") == i + 1), None)
            results.append({
                "question": q,
                "answer": a,
                "covered": match.get("covered", True) if match else True,
                "reason": match.get("reason", "") if match else "",
            })
        return results

    except Exception as e:
        log.warning(f"Coverage check failed: {e} — defaulting all to covered")
        return [
            {"question": q, "answer": a, "covered": True, "reason": "included"}
            for q, a in zip(questions, answers) if a.strip()
        ]


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using the standard approximation:
    1 token ≈ 4 characters for English text.
    Matches GPT/Claude tokenizers closely enough for display purposes.
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