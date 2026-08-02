from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Gmail
    GMAIL_USER: str = ""
    GMAIL_APP_PASS: str = ""

    class Config:
        env_file = ".env"


settings = Settings()