# ✦ PromptCraft

**Live demo:** https://promptcraft-ql0s.onrender.com

A full-stack web application that transforms vague ideas into optimized, token-efficient AI prompts using dynamic clarification, a two-pass LLM generation system, and a structured key-value prompt format.

---

## The Problem

Most people type vague ideas into AI tools and get vague answers back. The quality of an AI response is almost entirely determined by the quality of the prompt — but writing a good prompt is a skill most people don't have. PromptCraft bridges that gap.

## How It Works

```
User types rough idea
        ↓
AI generates 4 dynamic follow-up questions specific to that input
        ↓
User answers them (supports voice input + file uploads)
        ↓
Pass 1 — AI builds a structured draft using Role/Task/Context/Constraints/Output format
        ↓
Pass 2 — Compression pass strips filler words, preserves all user content
        ↓
Pass 3 — Coverage check verifies every answer made it into the final prompt
        ↓
User sees optimized prompt + token count + answer coverage panel
        ↓
User can edit the prompt inline — token count updates live
        ↓
Copy and use anywhere (ChatGPT, Claude, Gemini, etc.)
```

---

## Tech Stack

| Layer            | Tech                                       |
| ---------------- | ------------------------------------------ |
| Frontend         | HTML, CSS, Vanilla JavaScript              |
| Backend          | FastAPI (Python)                           |
| Database         | PostgreSQL (Supabase)                      |
| ORM              | SQLAlchemy (async)                         |
| AI / LLM         | Groq API — LLaMA 3.1 8B Instant            |
| Auth             | JWT + bcrypt                               |
| Email            | Gmail SMTP                                 |
| File Parsing     | PyMuPDF                                    |
| Rate Limiting    | slowapi                                    |
| Containerization | Docker + docker-compose                    |
| Deployment       | Render (web service) + Supabase (database) |
| CI/CD            | GitHub — auto-deploy on push               |

---

## Features

- **Dynamic question generation** — 4 questions unique to every input, not templated
- **Two-pass prompt generation** — structured draft + compression pass for token efficiency
- **Answer coverage panel** — side panel showing which of the user's answers made it into the final prompt, with tick/check indicators
- **Inline prompt editing** — edit the final prompt directly with live token count updates
- **Token count badge** — colour-coded (green/amber/red) estimated token count on every generated prompt
- **Token-efficient output** — structured Role/Task/Context/Constraints/Output format, imperative verbs only, no filler
- **File upload support** — attach multiple `.pdf` or `.txt` files simultaneously; text extracted and injected as context
- **Voice input** — speak your idea using the native browser Web Speech API
- **Authentication** — signup, login, JWT-protected routes, welcome email on signup
- **Password reset** — forgot password flow via 30-minute time-limited email link
- **Prompt history** — every generated prompt saved to PostgreSQL per user, with expand, copy, and delete
- **Rate limiting** — 10 requests per minute per user (by JWT identity)
- **Prompt injection protection** — 27 compiled regex patterns blocking instruction overrides, role hijacking, jailbreak attempts
- **Rotating logs** — console + file logging, 5MB per file, 3 backups, all key events captured

---

## Project Structure

```
PromptCraft/
├── .gitignore
├── .env.example
├── docker-compose.yml
├── README.md
│
├── frontend/
│   ├── index.html              # Main app + auth + forgot password
│   ├── reset-password.html     # Password reset page
│   ├── style.css
│   └── app.js
│
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── migrate.py              # One-time DB migration script
    ├── .env.example
    │
    └── app/
        ├── __init__.py
        ├── main.py             # All routes
        ├── config.py           # Environment variables (pydantic-settings)
        ├── database.py         # DB engine and session
        ├── models.py           # SQLAlchemy models (User, Prompt)
        ├── schemas.py          # Pydantic request/response models
        ├── auth.py             # JWT logic
        ├── limiter.py          # Rate limiting
        ├── logger.py           # Rotating log setup
        │
        └── services/
            ├── __init__.py
            ├── groq.py         # Groq API — call, compress, coverage check, token estimate
            ├── file.py         # PDF/TXT extraction
            ├── email.py        # Gmail SMTP (welcome + reset emails)
            └── sanitizer.py    # Prompt injection protection (27 patterns)
```

---

## Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/shakthi-1307/PromptCraft.git
cd PromptCraft/backend

# 2. Set up environment
cp .env.example .env    # fill in your values

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
uvicorn app.main:app --reload
```

Open `http://localhost:8000`

---

## Running with Docker

```bash
# At project root
cp .env.example .env    # fill in your values
docker-compose up --build
```

---

## Environment Variables

| Variable         | Description                                              |
| ---------------- | -------------------------------------------------------- |
| `DATABASE_URL`   | PostgreSQL connection string (asyncpg)                   |
| `JWT_SECRET`     | Random secret for signing tokens                         |
| `GROQ_API_KEY`   | Get free at [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL`     | Model to use (default: `llama-3.1-8b-instant`)           |
| `GMAIL_USER`     | Gmail address for sending emails                         |
| `GMAIL_APP_PASS` | Gmail App Password (Settings → Security → App Passwords) |

---

## Deployment

Deployed on **Render** (free web service) with **Supabase** managed PostgreSQL.

- Auto HTTPS via Render's SSL
- CI/CD — every push to `main` triggers a redeploy
- Environment variables injected via Render dashboard
- Cold start on free tier: ~30-50 seconds after inactivity

**Live:** https://promptcraft-ql0s.onrender.com
