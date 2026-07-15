from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "llama3.1:latest"

    # Gmail
    GMAIL_USER: str = ""
    GMAIL_APP_PASS: str = ""

    class Config:
        env_file = ".env"


settings = Settings()