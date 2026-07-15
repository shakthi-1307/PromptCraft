from pydantic import BaseModel, EmailStr


# --- Auth ---

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    name: str


# --- Prompts ---

class GenerateQuestionsRequest(BaseModel):
    user_input: str
    filenames: list[str] = []


class GeneratePromptRequest(BaseModel):
    user_input: str
    questions: list[str]
    answers: list[str]
    filenames: list[str] = []


class SavePromptRequest(BaseModel):
    user_input: str
    generated: str


# --- History ---

class PromptHistoryItem(BaseModel):
    id: str
    user_input: str
    generated: str
    created_at: str