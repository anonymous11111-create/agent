from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:123456@localhost:5432/jchatmind"

    # LLM
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    ZHIPUAI_API_KEY: str = ""
    ZHIPUAI_BASE_URL: str = "https://api.z.ai/api/coding/paas/v1"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"

    # RAG
    RAG_SIMILARITY_THRESHOLD: float = 0.5
    RAG_TOP_K: int = 5
    RAG_CHUNK_MAX_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 100
    RAG_KEYWORD_THRESHOLD: float = 0.01
    RAG_KEYWORD_TOP_K: int = 5
    RAG_RRF_K: int = 60
    RAG_FINAL_TOP_N: int = 5

    # Agent
    AGENT_MAX_STEPS: int = 20
    AGENT_TIMEOUT_SECONDS: int = 300
    AGENT_MAX_DUPLICATE_CALLS: int = 2
    AGENT_MAX_RETRY_ATTEMPTS: int = 3
    CHAT_MEMORY_WINDOW_SIZE: int = 20

    # Context compact
    CONTEXT_COMPACT_LIMIT: int = 50000
    CONTEXT_COMPACT_KEEP_RECENT: int = 3
    CONTEXT_COMPACT_PERSIST_THRESHOLD: int = 30000
    CONTEXT_COMPACT_PREVIEW_CHARS: int = 2000

    # Email
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

    # Storage
    DOCUMENT_STORAGE_PATH: str = "./data/documents"
    SKILLS_DIR: str = "./skills"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
