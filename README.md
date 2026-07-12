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

| Layer        | Tech                            |
| ------------ | ------------------------------- |
| Frontend     | HTML, CSS, Vanilla JavaScript   |
| Backend      | FastAPI (Python)                |
| Database     | PostgreSQL + SQLAlchemy (async) |
| AI / LLM     | Ollama (local) — LLaMA 3.1      |
| Auth         | JWT + bcrypt                    |
| Email        | Gmail SMTP                      |
| File Parsing | PyMuPDF                         |

## Features

- **Dynamic question generation** — questions are unique to every input, not templated
- **File upload support** — attach `.pdf` or `.txt` files; content is extracted and used as context
- **Voice input** — speak your idea using the browser's native Web Speech API
- **Authentication** — signup, login, JWT-protected routes, welcome email on signup
- **Prompt history** — every generated prompt is saved to PostgreSQL per user, with expand, copy, and delete
- **Rate limiting** — 10 requests per minute per user via slowapi
- **Fully local AI** — no external AI API, no cost, no data leaving your machine

## Project Structure

```
promptcraft/
├── main.py            # FastAPI app — all routes
├── auth.py            # JWT creation and verification
├── database.py        # PostgreSQL models and session
├── email_service.py   # Gmail welcome email
├── .env               # Credentials (not committed)
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start Ollama
ollama serve

# Run the server
uvicorn main:app --reload
```

Open `http://localhost:8000`
