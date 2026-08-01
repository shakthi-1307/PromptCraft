import json
import httpx
from fastapi import HTTPException
from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)


async def call_ollama(prompt: str, max_tokens: int = 512) -> str:
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.3,
            "top_p": 0.9,
        }
    }
    log.info(f"Calling Ollama | model: {settings.OLLAMA_MODEL} | max_tokens: {max_tokens} | prompt_len: {len(prompt)}")

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(settings.OLLAMA_URL, json=payload)
    except httpx.ConnectError:
        log.error("Could not connect to Ollama — is it running?")
        raise HTTPException(
            status_code=500,
            detail="Could not connect to Ollama. Make sure it is running (ollama serve).",
        )
    except httpx.TimeoutException:
        log.error("Ollama request timed out after 120s")
        raise HTTPException(status_code=504, detail="Ollama request timed out.")

    if response.status_code != 200:
        log.error(f"Ollama non-200: {response.status_code} | {response.text[:200]}")
        raise HTTPException(status_code=500, detail="Ollama returned an error")

    result = response.json()["response"]
    log.info(f"Ollama response received | output_len: {len(result)}")
    return result

import re

def extract_json_array(raw: str):
    raw = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )

    # Find either a JSON object or array
    match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)

    if not match:
        log.warning(f"No JSON found in Ollama output: {raw[:200]}")
        return None

    try:
        parsed = json.loads(match.group())

        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed]

        if isinstance(parsed, dict):
            return [str(v).strip() for v in parsed.values()]

    except json.JSONDecodeError as e:
        log.warning(f"JSON decode failed: {e}")
        return None

    return None