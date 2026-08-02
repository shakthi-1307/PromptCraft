# ✦ PromptCraft

A full-stack web application that transforms rough ideas into powerful AI prompts using dynamic clarification and local LLM inference.

## The Problem

Most people type vague ideas into AI tools and get vague answers back. The quality of an AI response is almost entirely determined by the quality of the prompt — but writing a good prompt is a skill most people don't have. PromptCraft bridges that gap.

## How It Works

```
User types rough idea
        ↓
AI generates 4 dynamic follow-up questions specific to that input
        ↓
User answers them (supports voice input)
        ↓
AI builds a structured, token-efficient prompt
        ↓
User copies it and uses it anywhere (ChatGPT, Claude, Gemini, etc.)
```

## Tech Stack

| Layer            | Tech                            |
| ---------------- | ------------------------------- |
| Frontend         | HTML, CSS, Vanilla JavaScript   |
| Backend          | FastAPI (Python)                |
| Database         | PostgreSQL + SQLAlchemy (async) |
| AI / LLM         | Ollama (local) — LLaMA 3.1      |
| Auth             | JWT + bcrypt                    |
| Email            | Gmail SMTP                      |
| File Parsing     | PyMuPDF                         |
| Rate Limiting    | slowapi                         |
| Containerization | Docker + docker-compose         |

## Features

- **Dynamic question generation** — questions are unique to every input, not templated
- **Token-efficient output** — generated prompts use imperative verbs, no filler, under 200 words
- **File upload support** — attach multiple `.pdf` or `.txt` files simultaneously; content injected as context
- **Voice input** — speak your idea using the native browser Web Speech API
- **Authentication** — signup, login, JWT-protected routes, welcome email on signup
- **Password reset** — forgot password flow via time-limited email link (expires in 30 minutes)
- **Prompt history** — every generated prompt saved to PostgreSQL per user, with expand, copy, and delete
- **Rate limiting** — 10 requests per minute per user
- **Logging** — rotating log files (console + file), all key events and errors captured
- **Fully local AI** — no external AI API, no cost, no data leaving your machine

## Project Structure

```
PromptCraft/
├── .gitignore
├── .env.example
├── docker-compose.yml
├── README.md
│
├── frontend/
│   ├── index.html           # Main app + auth
│   ├── reset-password.html  # Password reset page
│   ├── style.css
│   └── app.js
│
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── .env.example
    │
    └── app/
        ├── __init__.py
        ├── main.py          # All routes
        ├── config.py        # Environment variables
        ├── database.py      # DB engine and session
        ├── models.py        # SQLAlchemy models (User, Prompt)
        ├── schemas.py       # Pydantic request/response models
        ├── auth.py          # JWT logic
        ├── limiter.py       # Rate limiting
        ├── logger.py        # Logging setup
        │
        └── services/
            ├── ollama.py    # LLM calls
            ├── file.py      # PDF/TXT extraction
            └── email.py     # Gmail SMTP (welcome + reset)
```

## Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/shakthi-1307/PromptCraft.git
cd PromptCraft

# 2. Set up environment
cd backend
cp .env.example .env        # fill in your values

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Ollama
ollama serve

# 5. Run the server
uvicorn app.main:app --reload
```

Open `http://localhost:8000`

## Running with Docker

```bash
# At project root
cp .env.example .env        # fill in your values
docker-compose up --build
```
