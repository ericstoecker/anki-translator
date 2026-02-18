from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///anki_translator.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"  # "anthropic" or "openai"
    llm_model: str = "claude-sonnet-4-20250514"

    card_example_count: int = 250  # number of recent cards to use for style derivation
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    duplicate_embedding_threshold: float = 0.6
    duplicate_llm_candidates: int = 10

    model_config = {"env_prefix": "ANKI_", "env_file": ".env"}


settings = Settings()
