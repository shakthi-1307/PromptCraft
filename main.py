import os 
import json 
import httpx 
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles 
from fastapi.responses import FileResponse 
from pydantic import BaseModel 
from dotenv import load_dotenv 

load_dotenv()

app = FastAPI()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL =  f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

class UserInput(BaseModel):
    user_input : str 
    
class PromptRequest(BaseModel):
    user_input: str 
    questions: list[str]
    answers: list[str]
    
async def call_gemini(prompt: str) -> str:
    payload = {
        "contents": [{"parts":[{"text":prompt}]}]
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(GEMINI_URL,json = payload)
        if response.status_code != 200:
            raise HTTPException(status_code = 500, detail = "Gemini API error")
        data = response.json()
        return data["candidate"][0]["content"]["parts"][0]["text"]
    
@app.post("/generate-questions")
async def generate_questions(body: UserInput):
    prompt = f"""A user wants to use AI for the following task:
"{body.user_input}"
 
Generate exactly 4 short, specific follow-up questions that will help clarify what they need.
These questions should uncover the missing context that would make an AI prompt much stronger.
Questions should be targeted to THIS specific input — not generic.
 
Return ONLY a valid JSON array of 4 question strings. No explanation, no markdown, no code block. Example:
["Question 1?", "Question 2?", "Question 3?", "Question 4?"]"""
 
    raw = await call_gemini(prompt)
 
    try:
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        questions = json.loads(raw)
        if not isinstance(questions, list):
            raise ValueError
        return {"questions": questions[:4]}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse questions from AI response")
 
 
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
 
    final_prompt = await call_gemini(prompt)
    return {"prompt": final_prompt.strip()}
 
 
app.mount("/", StaticFiles(directory="static", html=True), name="static")
    