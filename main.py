import json
import httpx
import fitz  # pymupdf
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:latest"

# In-memory file store: { filename: extracted_text }
uploaded_files: dict[str, str] = {}


# --- Models ---

class UserInput(BaseModel):
    user_input: str
    filenames: list[str] = []


class PromptRequest(BaseModel):
    user_input: str
    questions: list[str]
    answers: list[str]
    filenames: list[str] = []


# --- Helpers ---

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
            detail="Could not connect to Ollama. Make sure it is running (ollama serve).",
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Ollama returned an error")

    return response.json()["response"]


def extract_json_array(raw: str):
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
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


def extract_text_from_file(filename: str, content: bytes) -> str:
    if filename.endswith(".txt"):
        return content.decode("utf-8", errors="ignore").strip()
    elif filename.endswith(".pdf"):
        text = ""
        with fitz.open(stream=content, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text.strip()
    return ""


def build_file_context(filenames: list[str]) -> str:
    parts = []
    for name in filenames:
        text = uploaded_files.get(name, "")
        if text:
            # Truncate to 2000 chars per file to keep prompt manageable
            snippet = text[:2000] + ("..." if len(text) > 2000 else "")
            parts.append(f"[File: {name}]\n{snippet}")
    return "\n\n".join(parts)


# --- Endpoints ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename
    if not (filename.endswith(".pdf") or filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")

    content = await file.read()
    extracted = extract_text_from_file(filename, content)

    if not extracted:
        raise HTTPException(status_code=400, detail="Could not extract text from the file.")

    uploaded_files[filename] = extracted
    return {"filename": filename, "characters": len(extracted)}


@app.delete("/upload/{filename}")
async def delete_file(filename: str):
    uploaded_files.pop(filename, None)
    return {"deleted": filename}


@app.post("/generate-questions")
async def generate_questions(body: UserInput):
    file_context = build_file_context(body.filenames)

    context_block = ""
    if file_context:
        context_block = f"\n\nThe user has also uploaded the following file(s) for context:\n{file_context}"

    prompt = f"""A user wants to use AI for the following task:
"{body.user_input}"{context_block}

Generate exactly 4 short, specific follow-up questions that will help clarify what they need.
If files were provided, your questions should also reflect what is in those files.
Questions should uncover missing context that would make an AI prompt much stronger.

Respond with ONLY a JSON array of 4 question strings. Nothing else — no explanation, no markdown, no code fences.
Example format:
["Question 1?", "Question 2?", "Question 3?", "Question 4?"]"""

    raw = await call_ollama(prompt)
    questions = extract_json_array(raw)

    if not questions:
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")

    return {"questions": questions[:4]}


@app.post("/generate-prompt")
async def generate_prompt(body: PromptRequest):
    qa_pairs = "\n".join(
        f"Q: {q}\nA: {a}" for q, a in zip(body.questions, body.answers)
    )

    file_context = build_file_context(body.filenames)
    context_block = ""
    if file_context:
        context_block = f"\n\nThe user has uploaded these files as supporting context:\n{file_context}"

    prompt = f"""You are a prompt engineering expert. A user wants to use AI for the following task:

Original Input: "{body.user_input}"{context_block}

They answered these follow-up questions:
{qa_pairs}

Using all of this information, write a single powerful, well-structured AI prompt they can directly use.
The prompt should:
- Assign a clear role to the AI
- Give all necessary context (including references to uploaded files if relevant)
- State the task precisely
- Specify the desired output format

Return ONLY the final prompt text. No explanation, no preamble, no markdown formatting."""

    final_prompt = await call_ollama(prompt)
    return {"prompt": final_prompt.strip()}


app.mount("/", StaticFiles(directory="static", html=True), name="static")