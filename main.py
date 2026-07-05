import json
import httpx
import fitz  # pymupdf
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import init_db, get_db, User, Prompt
from auth import hash_password, verify_password, create_token, decode_token
from email_service import send_welcome_email

app = FastAPI()

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:latest"

# In-memory file store: { filename: extracted_text }
uploaded_files: dict[str, str] = {}


# --- Startup ---

@app.on_event("startup")
async def startup():
    await init_db()


# --- Auth Models ---

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# --- Prompt Models ---

class UserInput(BaseModel):
    user_input: str
    filenames: list[str] = []


class PromptRequest(BaseModel):
    user_input: str
    questions: list[str]
    answers: list[str]
    filenames: list[str] = []


# --- Auth Endpoints ---

@app.post("/auth/signup")
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        email    = body.email,
        name     = body.name,
        password = hash_password(body.password),
    )
    db.add(user)
    await db.commit()

    send_welcome_email(body.email, body.name)
    token = create_token(body.email)
    return {"token": token, "name": body.name}


@app.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_token(body.email)
    return {"token": token, "name": user.name}


# --- Helpers ---

async def call_ollama(prompt: str) -> str:
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(OLLAMA_URL, json=payload)
    except httpx.ConnectError:
        raise HTTPException(status_code=500, detail="Could not connect to Ollama. Make sure it is running.")
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Ollama returned an error")
    return response.json()["response"]


def extract_json_array(raw: str):
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
            snippet = text[:2000] + ("..." if len(text) > 2000 else "")
            parts.append(f"[File: {name}]\n{snippet}")
    return "\n\n".join(parts)


# --- File Endpoints (protected) ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), email: str = Depends(decode_token)):
    filename = file.filename
    if not (filename.endswith(".pdf") or filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")
    content  = await file.read()
    extracted = extract_text_from_file(filename, content)
    if not extracted:
        raise HTTPException(status_code=400, detail="Could not extract text from the file.")
    uploaded_files[filename] = extracted
    return {"filename": filename, "characters": len(extracted)}


@app.delete("/upload/{filename}")
async def delete_file(filename: str, email: str = Depends(decode_token)):
    uploaded_files.pop(filename, None)
    return {"deleted": filename}


# --- Prompt Endpoints (protected) ---

@app.post("/generate-questions")
async def generate_questions(body: UserInput, email: str = Depends(decode_token)):
    file_context   = build_file_context(body.filenames)
    context_block  = f"\n\nThe user has also uploaded the following file(s) for context:\n{file_context}" if file_context else ""

    prompt = f"""A user wants to use AI for the following task:
"{body.user_input}"{context_block}

Generate exactly 4 short, specific follow-up questions that will help clarify what they need.
If files were provided, your questions should also reflect what is in those files.
Questions should uncover missing context that would make an AI prompt much stronger.

Respond with ONLY a JSON array of 4 question strings. Nothing else.
Example: ["Question 1?", "Question 2?", "Question 3?", "Question 4?"]"""

    raw       = await call_ollama(prompt)
    questions = extract_json_array(raw)
    if not questions:
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")
    return {"questions": questions[:4]}


@app.post("/generate-prompt")
async def generate_prompt(body: PromptRequest, email: str = Depends(decode_token)):
    qa_pairs      = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(body.questions, body.answers))
    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nThe user has uploaded these files as supporting context:\n{file_context}" if file_context else ""

    prompt = f"""You are a prompt engineering expert. A user wants to use AI for the following task:

Original Input: "{body.user_input}"{context_block}

They answered these follow-up questions:
{qa_pairs}

Write a single powerful, well-structured AI prompt they can directly use.
The prompt should assign a clear role, give all necessary context, state the task precisely, and specify the desired output format.

Return ONLY the final prompt text. No explanation, no preamble, no markdown."""

    final_prompt = await call_ollama(prompt)
    return {"prompt": final_prompt.strip()}


# --- History Models ---

class SavePromptRequest(BaseModel):
    user_input: str
    generated: str


# --- History Endpoints ---

@app.post("/history/save")
async def save_prompt(body: SavePromptRequest, email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    entry = Prompt(user_email=email, user_input=body.user_input, generated=body.generated)
    db.add(entry)
    await db.commit()
    return {"saved": True}


@app.get("/history")
async def get_history(email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Prompt)
        .where(Prompt.user_email == email)
        .order_by(Prompt.created_at.desc())
    )
    prompts = result.scalars().all()
    return {"history": [
        {
            "id": p.id,
            "user_input": p.user_input,
            "generated": p.generated,
            "created_at": p.created_at.isoformat(),
        }
        for p in prompts
    ]}


@app.delete("/history/{prompt_id}")
async def delete_prompt(prompt_id: str, email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id, Prompt.user_email == email))
    entry  = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await db.delete(entry)
    await db.commit()
    return {"deleted": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")