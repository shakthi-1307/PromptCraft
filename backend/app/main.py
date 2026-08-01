import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, get_db
from app.models import User, Prompt
from app.schemas import (
    SignupRequest, LoginRequest,
    GenerateQuestionsRequest, GeneratePromptRequest,
    SavePromptRequest,
)
from app.auth import hash_password, verify_password, create_token, decode_token
from app.limiter import limiter, rate_limit_handler
from app.services.ollama import call_ollama, extract_json_array
from app.services.file import uploaded_files, extract_text, build_file_context
from app.services.email import send_welcome_email
from app.logger import setup_logging, get_logger

setup_logging()
log = get_logger(__name__)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# --- Startup ---

@app.on_event("startup")
async def startup():
    await init_db()
    log.info("Database initialized")


# --- Auth ---

@app.post("/auth/signup")
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        log.warning(f"Signup failed — email already registered: {body.email}")
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(email=body.email, name=body.name, password=hash_password(body.password))
    db.add(user)
    await db.commit()
    log.info(f"New user signed up: {body.email}")

    send_welcome_email(body.email, body.name)
    return {"token": create_token(body.email), "name": body.name}


@app.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password):
        log.warning(f"Failed login attempt for: {body.email}")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    log.info(f"User logged in: {body.email}")
    return {"token": create_token(body.email), "name": user.name}


# --- File Upload ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), email: str = Depends(decode_token)):
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".txt")):
        log.warning(f"Rejected unsupported file type: {file.filename} by {email}")
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")

    content   = await file.read()
    extracted = extract_text(file.filename, content)

    if not extracted:
        log.warning(f"Could not extract text from file: {file.filename} uploaded by {email}")
        raise HTTPException(status_code=400, detail="Could not extract text from the file.")

    uploaded_files[file.filename] = extracted
    log.info(f"File uploaded: {file.filename} ({len(extracted)} chars) by {email}")
    return {"filename": file.filename, "characters": len(extracted)}


@app.delete("/upload/{filename}")
async def delete_file(filename: str, email: str = Depends(decode_token)):
    uploaded_files.pop(filename, None)
    log.info(f"File removed: {filename} by {email}")
    return {"deleted": filename}


# --- Prompt Generation ---

@app.post("/generate-questions")
@limiter.limit("10/minute")
async def generate_questions(request: Request, body: GenerateQuestionsRequest, email: str = Depends(decode_token)):
    log.info(f"Generating questions for: {email} | input length: {len(body.user_input)} | files: {body.filenames}")

    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nThe user has also uploaded the following file(s):\n{file_context}" if file_context else ""

    prompt = f"""Task: "{body.user_input}"{context_block}

Generate 4 concise clarifying questions to fill gaps needed for a precise AI prompt.
Each question targets one unknown: audience, format, constraints, tone, scope, or goal.
No generic questions. Each must be specific to this task.

Output: JSON array only. No other text.
["Q1?","Q2?","Q3?","Q4?"]"""

    try:
        raw = await call_ollama(prompt, max_tokens=256)
    except HTTPException as e:
        log.error(f"Ollama error during question generation for {email}: {e.detail}")
        raise

    questions = extract_json_array(raw)
    if not questions:
        log.error(f"Failed to parse questions from Ollama response for {email}. Raw: {raw[:200]}")
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")

    log.info(f"Questions generated successfully for: {email}")
    return {"questions": questions[:]}


@app.post("/generate-prompt")
@limiter.limit("10/minute")
async def generate_prompt(request: Request, body: GeneratePromptRequest, email: str = Depends(decode_token)):
    log.info(f"Generating prompt for: {email} | input length: {len(body.user_input)}")

    qa_pairs      = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(body.questions, body.answers))
    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nUploaded files for context:\n{file_context}" if file_context else ""

    prompt = f"""Build a tight, token-efficient AI prompt from the inputs below.
Rules for the output prompt:
- Use imperative verbs, no filler phrases ("please", "I want you to", "could you")
- Pack context densely — no repetition
- Specify role, task, constraints, and output format in the fewest words possible
- Output must be copy-paste ready, under 200 words unless complexity demands more

Task: "{body.user_input}"{context_block}

Clarifications:
{qa_pairs}

Output: the final prompt text only. No explanation, no preamble, no markdown."""

    try:
        final_prompt = await call_ollama(prompt, max_tokens=400)
    except HTTPException as e:
        log.error(f"Ollama error during prompt generation for {email}: {e.detail}")
        raise

    log.info(f"Prompt generated successfully for: {email} | output length: {len(final_prompt)}")
    return {"prompt": final_prompt.strip()}


# --- Prompt History ---

@app.post("/history/save")
async def save_prompt(body: SavePromptRequest, email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    entry = Prompt(user_email=email, user_input=body.user_input, generated=body.generated)
    db.add(entry)
    await db.commit()
    log.info(f"Prompt saved to history for: {email}")
    return {"saved": True}


@app.get("/history")
async def get_history(email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    result  = await db.execute(
        select(Prompt).where(Prompt.user_email == email).order_by(Prompt.created_at.desc())
    )
    prompts = result.scalars().all()
    log.info(f"History fetched for: {email} | {len(prompts)} prompts")
    return {"history": [
        {"id": p.id, "user_input": p.user_input, "generated": p.generated, "created_at": p.created_at.isoformat()}
        for p in prompts
    ]}


@app.delete("/history/{prompt_id}")
async def delete_prompt(prompt_id: str, email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id, Prompt.user_email == email))
    entry  = result.scalar_one_or_none()
    if not entry:
        log.warning(f"Prompt delete failed — not found: {prompt_id} by {email}")
        raise HTTPException(status_code=404, detail="Prompt not found")
    await db.delete(entry)
    await db.commit()
    log.info(f"Prompt deleted: {prompt_id} by {email}")
    return {"deleted": True}


# --- Global exception handler ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


# --- Static files ---

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = Path("/app/frontend")

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")