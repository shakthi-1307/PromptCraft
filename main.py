import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:latest"


class UserInput(BaseModel):
    user_input: str


class PromptRequest(BaseModel):
    user_input: str
    questions: list[str]
    answers: list[str]


async def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(OLLAMA_URL, json=payload)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=500,
            detail="Could not connect to Ollama. Make sure it's running (ollama serve).",
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Ollama returned an error")

    data = response.json()
    return data["response"]


@app.post("/generate-questions")
async def generate_questions(body: UserInput):
    prompt = f"""A user wants to use AI for the following task:
"{body.user_input}"

Generate exactly 4 short, specific follow-up questions that will help clarify what they need.
These questions should uncover the missing context that would make an AI prompt much stronger.
Questions should be targeted to THIS specific input — not generic.

Respond with ONLY a JSON array of 4 question strings. Nothing else — no explanation, no markdown, no code fences.
Example format:
["Question 1?", "Question 2?", "Question 3?", "Question 4?"]"""

    raw = await call_ollama(prompt)
    questions = extract_json_array(raw)

    if not questions:
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")

    return {"questions": questions[:4]}


def extract_json_array(raw: str):
    """Extract a JSON array from a model response, tolerating stray text around it."""
    raw = raw.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None

    snippet = raw[start:end + 1]
    try:
        parsed = json.loads(snippet)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed]
    except json.JSONDecodeError:
        return None

    return None


@app.post("/generate-prompt")
async def generate_prompt(body: PromptRequest):
    qa_pairs = "\n".join(
        f"Q: {q}\nA: {a}" for q, a in zip(body.questions, body.answers)
    )

    prompt = f"""You are a prompt engineering expert. A user wants to use AI for the following task:

Original Input: "{body.user_input}"

They answered these follow-up questions:
{qa_pairs}

Using this information, write a single powerful, well-structured AI prompt they can directly use.
The prompt should:
- Assign a clear role to the AI
- Give all necessary context
- State the task precisely
- Specify the desired output format

Return ONLY the final prompt text. No explanation, no preamble, no markdown formatting."""

    final_prompt = await call_ollama(prompt)
    return {"prompt": final_prompt.strip()}


app.mount("/", StaticFiles(directory="static", html=True), name="static")