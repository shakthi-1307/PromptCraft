import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
    SavePromptRequest, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.auth import hash_password, verify_password, create_token, decode_token
from app.limiter import limiter, rate_limit_handler
from app.services.groq import call_groq, extract_json_array, compress_prompt, estimate_tokens, check_coverage
from app.services.file import uploaded_files, extract_text, build_file_context
from app.services.email import send_welcome_email, send_reset_email
from app.services.sanitizer import check_injection, sanitize_input
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


@app.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    # Always return success to prevent email enumeration
    if not user:
        log.warning(f"Password reset requested for unknown email: {body.email}")
        return {"message": "If that email exists, a reset link has been sent."}

    # Generate a short-lived token (30 min)
    token  = create_token(body.email, expires_minutes=30)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    user.reset_token        = token
    user.reset_token_expiry = expiry
    await db.commit()

    base_url   = str(request.base_url).rstrip("/")
    reset_link = f"{base_url}/reset-password.html?token={token}"

    send_reset_email(body.email, user.name, reset_link)
    log.info(f"Password reset email sent to: {body.email}")
    return {"message": "If that email exists, a reset link has been sent."}


@app.post("/auth/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    from jose import JWTError, jwt
    from app.config import settings as s

    try:
        payload = jwt.decode(body.token, s.JWT_SECRET, algorithms=[s.JWT_ALGORITHM])
        email   = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid reset token.")
    except JWTError:
        log.warning("Reset password attempt with invalid/expired token")
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    result = await db.execute(select(User).where(User.email == email))
    user   = result.scalar_one_or_none()

    if not user or user.reset_token != body.token:
        log.warning(f"Reset token mismatch for: {email}")
        raise HTTPException(status_code=400, detail="Reset link is invalid or has already been used.")

    if user.reset_token_expiry and user.reset_token_expiry < datetime.now(timezone.utc):
        log.warning(f"Expired reset token used for: {email}")
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    user.password          = hash_password(body.new_password)
    user.reset_token       = None
    user.reset_token_expiry= None
    await db.commit()

    log.info(f"Password reset successfully for: {email}")
    return {"message": "Password updated successfully."}


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
    # Sanitize and check for injection
    clean_input = sanitize_input(body.user_input)
    is_safe, reason = check_injection(clean_input)
    if not is_safe:
        log.warning(f"Injection attempt blocked in generate-questions | user: {email} | reason: {reason}")
        raise HTTPException(status_code=400, detail="Invalid input detected. Please describe your task clearly.")

    log.info(f"Generating questions for: {email} | input length: {len(clean_input)} | files: {body.filenames}")

    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nThe user has also uploaded the following file(s):\n{file_context}" if file_context else ""

    prompt = f"""Task: "{clean_input}"{context_block}

You are a great analyzer and wants to understand the user's input.
Generate 5 to 7 (the number of questions depends on how much you want to ask from the user to provide a very good prompt) clarifying questions.
Each question targets one unknown: audience, format, constraints, tone, scope, or goal.
No generic questions. Each must be specific to this task.

Output: JSON array only. No other text.
["Q1?","Q2?","Q3?","Q4?"]"""

    try:
        raw = await call_groq(prompt, max_tokens=256)
    except HTTPException as e:
        log.error(f"Groq error during question generation for {email}: {e.detail}")
        raise

    questions = extract_json_array(raw)
    if not questions:
        log.error(f"Failed to parse questions from Groq response for {email}. Raw: {raw[:200]}")
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")

    log.info(f"Questions generated successfully for: {email}")
    return {"questions": questions[:]}


@app.post("/generate-prompt")
@limiter.limit("10/minute")
async def generate_prompt(request: Request, body: GeneratePromptRequest, email: str = Depends(decode_token)):
    # Sanitize and check for injection
    clean_input = sanitize_input(body.user_input)
    is_safe, reason = check_injection(clean_input)
    if not is_safe:
        log.warning(f"Injection attempt blocked in generate-prompt | user: {email} | reason: {reason}")
        raise HTTPException(status_code=400, detail="Invalid input detected. Please describe your task clearly.")

    clean_answers = [sanitize_input(a) for a in body.answers]
    for i, answer in enumerate(clean_answers):
        is_safe, reason = check_injection(answer)
        if not is_safe:
            log.warning(f"Injection attempt in answer[{i}] | user: {email} | reason: {reason}")
            raise HTTPException(status_code=400, detail="Invalid content detected in your answers.")

    log.info(f"Generating prompt for: {email} | input length: {len(clean_input)}")

    qa_pairs      = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(body.questions, clean_answers))
    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nFile context:\n{file_context}" if file_context else ""

    # ── PASS 1: Generate structured draft ──────────────────────────────────
    # Build a readable summary of what the user answered so nothing gets lost
    answered_points = "\n".join(
        f"- {a.strip()}" for a in clean_answers if a.strip()
    )

    draft_instruction = f"""You are a prompt engineer. Your job is to convert a user's task and their answers into a structured AI prompt.

CRITICAL RULE: Every specific detail, point, and fact the user provided in their answers MUST appear in the final prompt. Do not drop, merge, or summarize away any information the user gave. Token optimization means removing filler words — never removing the user's content.

Use ONLY this format:
Role: [who the AI should be — one short phrase]
Task: [imperative verb + exact object — one sentence]
Context: [ALL specific details from user answers — preserve every point]
Constraints: [format, length, tone, audience — from user answers]
Output: [exact format expected]

Rules:
- Use imperative verbs (Write, Summarize, Analyze, Generate, Fix, Explain)
- No filler: no "please", "make sure", "I want you to", "could you"
- Context field must contain ALL key points the user mentioned — list them if needed
- Do NOT omit any answer the user gave

User task: {clean_input}{context_block}

User's answers to clarifying questions:
{qa_pairs}

Key points from user's answers (ALL must appear in the prompt):
{answered_points}

Return ONLY the structured prompt. No explanation, no preamble."""

    try:
        draft = await call_groq(draft_instruction, max_tokens=500, temperature=0.2)
    except HTTPException as e:
        log.error(f"Groq error during draft generation for {email}: {e.detail}")
        raise

    log.info(f"Draft generated for {email} | draft_len: {len(draft)}")

    # ── PASS 2: Compress the draft — preserve all content, remove only filler ──
    try:
        final_prompt = await compress_prompt(draft, answered_points)
    except HTTPException as e:
        log.warning(f"Compression failed for {email}, using draft: {e.detail}")
        final_prompt = draft

    # ── Token count ────────────────────────────────────────────────────────
    token_count = estimate_tokens(final_prompt)

    # ── PASS 3: Coverage check — verify all answers made it into the prompt ──
    coverage = await check_coverage(body.questions, clean_answers, final_prompt)
    covered_count = sum(1 for c in coverage if c["covered"])
    log.info(f"Coverage check: {covered_count}/{len(coverage)} answers covered for {email}")

    log.info(f"Prompt ready for {email} | final_len: {len(final_prompt)} | est_tokens: {token_count}")
    return {
        "prompt": final_prompt.strip(),
        "token_count": token_count,
        "coverage": coverage,
    }


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