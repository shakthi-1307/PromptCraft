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

import json
import re

def extract_json_array(raw: str):
    raw = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )

    # --------------------
    # 1. Try direct JSON
    # --------------------
    try:
        parsed = json.loads(raw)

        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed]

        if isinstance(parsed, dict):
            if "questions" in parsed:
                return [str(x).strip() for x in parsed["questions"]]

            return [str(v).strip() for v in parsed.values()]

    except Exception:
        pass

    # --------------------
    # 2. Find embedded JSON
    # --------------------
    match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)

    if match:
        try:
            parsed = json.loads(match.group())

            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed]

            if isinstance(parsed, dict):
                if "questions" in parsed:
                    return [str(x).strip() for x in parsed["questions"]]

                return [str(v).strip() for v in parsed.values()]
        except Exception:
            pass

    # --------------------
    # 3. Parse Q1:, Q2:...
    # --------------------
    questions = []

    for line in raw.splitlines():
        m = re.match(r"Q\d+\s*:\s*(.+)", line.strip())
        if m:
            questions.append(m.group(1).strip())

    if questions:
        return questions

    return None