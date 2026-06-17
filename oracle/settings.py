from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_default_model: str = Field(default="gpt-4o", alias="OPENAI_DEFAULT_MODEL")

    # Tavily
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/oracle.db", alias="DATABASE_URL"
    )
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")

    # Embedding
    embedding_model: str = Field(
        default="text-embedding-3-small", alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=1536, alias="EMBEDDING_DIMENSION")

    # Thresholds
    groundedness_tripwire_threshold: float = Field(
        default=0.70, alias="GROUNDEDNESS_TRIPWIRE_THRESHOLD"
    )
    groundedness_warn_threshold: float = Field(
        default=0.85, alias="GROUNDEDNESS_WARN_THRESHOLD"
    )
    max_turns: int = Field(default=15, alias="MAX_TURNS")
    chroma_n_results: int = Field(default=5, alias="CHROMA_N_RESULTS")
    semantic_location_distance_threshold: float = Field(
        default=0.30, alias="SEMANTIC_LOCATION_DISTANCE_THRESHOLD"
    )

    # Session
    session_backend: str = Field(default="sqlite", alias="SESSION_BACKEND")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    session_ttl_hours: int = Field(default=24, alias="SESSION_TTL_HOURS")

    # Observability
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    trace_sensitive_data: bool = Field(default=False, alias="TRACE_SENSITIVE_DATA")
    logfire_token: str = Field(default="", alias="LOGFIRE_TOKEN")

    # Phase 2 toggle
    mcp_enabled: bool = Field(default=False, alias="MCP_ENABLED")

    @property
    def primary_model(self) -> str:
        return "claude-sonnet-4-5"

    @property
    def validator_model(self) -> str:
        return self.openai_default_model

    @property
    def sentinel_model(self) -> str:
        return "gpt-4o-mini"

    @property
    def chroma_dir_resolved(self) -> Path:
        return Path(self.chroma_persist_dir).resolve()

    @property
    def db_path_resolved(self) -> Path:
        url = self.database_url.replace("sqlite+aiosqlite:///", "")
        return Path(url).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
