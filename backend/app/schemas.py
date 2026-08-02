from pydantic import BaseModel, EmailStr, field_validator
from typing import Annotated
from pydantic import StringConstraints

Name        = Annotated[str, StringConstraints(min_length=2,  max_length=50,    strip_whitespace=True)]
Password    = Annotated[str, StringConstraints(min_length=6,  max_length=72)]
UserInput   = Annotated[str, StringConstraints(min_length=10, max_length=1000,  strip_whitespace=True)]
ShortAnswer = Annotated[str, StringConstraints(max_length=500, strip_whitespace=True)]


class SignupRequest(BaseModel):
    name: Name
    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    email: EmailStr
    password: Password


class AuthResponse(BaseModel):
    token: str
    name: str


class GenerateQuestionsRequest(BaseModel):
    user_input: UserInput
    filenames: list[str] = []

    @field_validator("filenames")
    @classmethod
    def validate_filenames(cls, filenames):
        for name in filenames:
            if not (name.endswith(".pdf") or name.endswith(".txt")):
                raise ValueError(f"Invalid file type: {name}")
            if len(name) > 255:
                raise ValueError("Filename too long.")
        return filenames


class GeneratePromptRequest(BaseModel):
    user_input: UserInput
    questions: list[str]
    answers: list[ShortAnswer]
    filenames: list[str] = []

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, questions):
        if not 1 <= len(questions) <= 7:
            raise ValueError("Expected between 1 and 5 questions.")
        return questions

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers):
        if not 1 <= len(answers) <= 7:
            raise ValueError("Expected between 1 and 5 answers.")
        return answers


class SavePromptRequest(BaseModel):
    user_input: UserInput
    generated: Annotated[str, StringConstraints(min_length=1, max_length=10000)]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: Password


class PromptHistoryItem(BaseModel):
    id: str
    user_input: str
    generated: str
    created_at: str