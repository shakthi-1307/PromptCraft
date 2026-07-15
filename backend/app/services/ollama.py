import json
import httpx
from fastapi import HTTPException
from app.config import settings


async def call_ollama(prompt: str) -> str:
    payload = {"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            response = await client.post(settings.OLLAMA_URL, json=payload)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=500,
            detail="Could not connect to Ollama. Make sure it is running (ollama serve).",
        )
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Ollama returned an error")
    return response.json()["response"]


def extract_json_array(raw: str):
    """Extract a JSON array from model output, tolerating stray text around it."""
    raw   = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed]
    except json.JSONDecodeError:
        return None
    return None