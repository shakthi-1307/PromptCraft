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

    draft = (draft or "").strip()

    # Never send an empty draft to the compression model
    if not draft:
        raise HTTPException(
            status_code=500,
            detail="Cannot compress an empty draft."
        )

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
7. The output MUST NOT be empty.
8. If no compression is possible, return the original prompt unchanged.

{preservation_block}

DRAFT TO COMPRESS:
{draft}"""

    result = await call_groq(
        compression_instruction,
        max_tokens=400,
        temperature=0.1
    )

    result = (result or "").strip()

    # If compression returned nothing, raise an error so the
    # calling code can safely fall back to the original draft.
    if not result:
        raise HTTPException(
            status_code=500,
            detail="Compression returned an empty prompt."
        )
    return result


async def check_coverage(
    questions: list,
    answers: list,
    final_prompt: str
) -> list:
    """
    Check whether each answered question is reflected in the final prompt.

    IMPORTANT:
    - An empty final prompt means nothing is covered.
    - If the AI coverage check fails, default to FALSE, never TRUE.
    - Only answered questions are checked.
    """

    final_prompt = (final_prompt or "").strip()

    # ---------------------------------------------------------
    # SAFETY CHECK:
    # An empty prompt cannot possibly contain the user's answers.
    # ---------------------------------------------------------
    answered_pairs = [
        (q, a)
        for q, a in zip(questions, answers)
        if a and a.strip()
    ]

    if not answered_pairs:
        return []

    if not final_prompt:
        log.warning("Coverage check received an empty final prompt.")

        return [
            {
                "question": q,
                "answer": a,
                "covered": False,
                "reason": "Final prompt is empty"
            }
            for q, a in answered_pairs
        ]

    # ---------------------------------------------------------
    # Build Q&A block using NEW sequential indexes.
    #
    # This avoids the bug where unanswered questions create
    # gaps such as indexes 2, 3 instead of 1, 2.
    # ---------------------------------------------------------
    qa_block = "\n".join(
        f"{i}. Q: {q}\n   A: {a}"
        for i, (q, a) in enumerate(answered_pairs, start=1)
    )

    check_instruction = f"""You are verifying whether a user's answers are reflected in an AI prompt.

For each Q&A pair below, determine whether the answer's meaning or intent is present in the final prompt.

The answer can be covered:
- directly using the same words
- indirectly using different words with the same meaning

Q&A PAIRS:
{qa_block}

FINAL PROMPT:
{final_prompt}

Return ONLY a valid JSON array in this exact structure:

[
  {{"index": 1, "covered": true, "reason": "short explanation"}},
  {{"index": 2, "covered": false, "reason": "short explanation"}}
]

STRICT RULES:
- Return exactly one result for every Q&A pair.
- covered=true ONLY if the answer's meaning is actually present.
- covered=false if the answer's intent is missing.
- Never assume an answer is covered.
- reason must be under 8 words.
- Return ONLY the JSON array.
- Do not use markdown.
- Do not include any explanation outside the JSON.
"""

    try:
        raw = await call_groq(
            check_instruction,
            max_tokens=300,
            temperature=0.0
        )

        raw = (raw or "").strip()

        if not raw:
            raise ValueError(
                "Coverage model returned an empty response."
            )

        # -----------------------------------------------------
        # Remove optional markdown code fences.
        # -----------------------------------------------------
        if raw.startswith("```json"):
            raw = raw[len("```json"):].strip()
        elif raw.startswith("```"):
            raw = raw[len("```"):].strip()

        if raw.endswith("```"):
            raw = raw[:-3].strip()

        if not raw:
            raise ValueError(
                "Coverage response was empty after cleanup."
            )

        # -----------------------------------------------------
        # Parse JSON.
        # -----------------------------------------------------
        parsed = json.loads(raw)

        if not isinstance(parsed, list):
            raise ValueError(
                "Coverage response is not a JSON array."
            )

        results = []

        # -----------------------------------------------------
        # Match results against our sequential indexes.
        # -----------------------------------------------------
        for i, (q, a) in enumerate(answered_pairs, start=1):

            match = next(
                (
                    item
                    for item in parsed
                    if isinstance(item, dict)
                    and item.get("index") == i
                ),
                None
            )

            # IMPORTANT:
            # If the model failed to return a result for this
            # answer, mark it FALSE instead of TRUE.
            if match is None:
                results.append({
                    "question": q,
                    "answer": a,
                    "covered": False,
                    "reason": "No coverage result returned"
                })
                continue

            covered = match.get("covered", False)

            # Make sure we really have a boolean.
            if not isinstance(covered, bool):
                covered = False

            reason = str(
                match.get("reason", "")
            ).strip()[:100]

            results.append({
                "question": q,
                "answer": a,
                "covered": covered,
                "reason": reason
            })
        return results

    except Exception as e:
        # -----------------------------------------------------
        # IMPORTANT:
        # NEVER default failed coverage checks to TRUE.
        # -----------------------------------------------------
        log.warning(
            f"Coverage check failed: {e}"
        )

        return [
            {
                "question": q,
                "answer": a,
                "covered": False,
                "reason": "Coverage check failed"
            }
            for q, a in answered_pairs
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