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

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


# --- Startup ---

@app.on_event("startup")
async def startup():
    await init_db()


# --- Auth ---

@app.post("/auth/signup")
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(email=body.email, name=body.name, password=hash_password(body.password))
    db.add(user)
    await db.commit()

    send_welcome_email(body.email, body.name)
    return {"token": create_token(body.email), "name": body.name}


@app.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {"token": create_token(body.email), "name": user.name}


# --- File Upload ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), email: str = Depends(decode_token)):
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported.")

    content   = await file.read()
    extracted = extract_text(file.filename, content)

    if not extracted:
        raise HTTPException(status_code=400, detail="Could not extract text from the file.")

    uploaded_files[file.filename] = extracted
    return {"filename": file.filename, "characters": len(extracted)}


@app.delete("/upload/{filename}")
async def delete_file(filename: str, email: str = Depends(decode_token)):
    uploaded_files.pop(filename, None)
    return {"deleted": filename}


# --- Prompt Generation ---

@app.post("/generate-questions")
@limiter.limit("10/minute")
async def generate_questions(request: Request, body: GenerateQuestionsRequest, email: str = Depends(decode_token)):
    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nThe user has also uploaded the following file(s):\n{file_context}" if file_context else ""

    prompt = f"""A user wants to use AI for the following task:
"{body.user_input}"{context_block}

Analyze the given input and if you want more information on the given input you can ask 4-7 questions to the user, specific follow-up questions that will help clarify what they need.
If files were provided, reflect what is in those files in your questions.
Questions should uncover missing context that would make an AI prompt much stronger.

Respond with ONLY a JSON array of question strings. Nothing else.
Example: ["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]"""

    raw       = await call_ollama(prompt)
    questions = extract_json_array(raw)

    if not questions:
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")

    return {"questions": questions[:]}


@app.post("/generate-prompt")
@limiter.limit("10/minute")
async def generate_prompt(request: Request, body: GeneratePromptRequest, email: str = Depends(decode_token)):
    qa_pairs      = "\n".join(f"Q: {q}\nA: {a}" for q, a in zip(body.questions, body.answers))
    file_context  = build_file_context(body.filenames)
    context_block = f"\n\nUploaded files for context:\n{file_context}" if file_context else ""

    prompt = f"""You are a prompt engineering expert. A user wants to use AI for the following task:

Original Input: "{body.user_input}"{context_block}

They answered these follow-up questions:
{qa_pairs}

Write a single powerful, well-structured AI prompt they can directly use.
Assign a clear role, give all necessary context, state the task precisely, and specify the desired output format.

Return ONLY the final prompt text. No explanation, no preamble, no markdown."""

    final_prompt = await call_ollama(prompt)
    return {"prompt": final_prompt.strip()}


# --- Prompt History ---

@app.post("/history/save")
async def save_prompt(body: SavePromptRequest, email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    entry = Prompt(user_email=email, user_input=body.user_input, generated=body.generated)
    db.add(entry)
    await db.commit()
    return {"saved": True}


@app.get("/history")
async def get_history(email: str = Depends(decode_token), db: AsyncSession = Depends(get_db)):
    result  = await db.execute(
        select(Prompt).where(Prompt.user_email == email).order_by(Prompt.created_at.desc())
    )
    prompts = result.scalars().all()
    return {"history": [
        {"id": p.id, "user_input": p.user_input, "generated": p.generated, "created_at": p.created_at.isoformat()}
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


app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")