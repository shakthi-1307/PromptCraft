# ✦ PromptCraft

A full-stack web application that transforms rough ideas into powerful AI prompts using dynamic clarification and local LLM inference.

## What it does

Most people get mediocre results from AI because they write weak prompts. PromptCraft fixes that — you type a rough idea, the app asks smart follow-up questions tailored to your input, and generates a structured, high-quality prompt you can copy and use anywhere.

## How it works

```
User types rough idea
       ↓
AI generates 4 dynamic follow-up questions specific to that input
       ↓
User answers them
       ↓
AI builds a strong, structured prompt
       ↓
User copies and uses it
```

## Tech Stack

| Layer         | Tech                            |
| ------------- | ------------------------------- |
| Frontend      | HTML, CSS, Vanilla JavaScript   |
| Backend       | FastAPI (Python)                |
| Database      | PostgreSQL + SQLAlchemy (async) |
| AI / LLM      | Ollama (local) — LLaMA 3.1      |
| Auth          | JWT + bcrypt                    |
| Email         | Gmail SMTP                      |
| File Parsing  | PyMuPDF                         |
| Rate Limiting | slowapi                         |

## Features

- **Dynamic question generation** — questions are unique to every input, not templated
- **File upload support** — attach `.pdf` or `.txt` files; content is extracted and used as context
- **Voice input** — speak your idea using the browser's native Web Speech API
- **Authentication** — signup, login, JWT-protected routes, welcome email on signup
- **Prompt history** — every generated prompt saved to PostgreSQL per user, with expand, copy, and delete
- **Rate limiting** — 10 requests per minute per user
- **Fully local AI** — no external AI API, no cost, no data leaving your machine

## Project Structure

```
PromptCraft/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app — all routes
│   │   ├── config.py        # Environment variables
│   │   ├── database.py      # DB engine and session
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic request/response models
│   │   ├── auth.py          # JWT logic
│   │   ├── limiter.py       # Rate limiting
│   │   └── services/
│   │       ├── ollama.py    # LLM calls
│   │       ├── file.py      # PDF/TXT extraction
│   │       └── email.py     # Gmail SMTP
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .gitignore
└── README.md
```

## Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/shakthi-1307/PromptCraft.git
cd PromptCraft

# 2. Set up backend
cd backend
cp .env.example .env        # fill in your values
pip install -r requirements.txt

# 3. Start Ollama
ollama serve

# 4. Run the server
uvicorn app.main:app --reload
```

Open `http://localhost:8000`
