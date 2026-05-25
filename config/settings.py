"""Environment-driven configuration. ALL env vars are read ONLY here."""

from functools import lru_cache
from typing import Any, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single source of truth for all configuration.

    Model provider priority: OpenAI > Anthropic > Google > Groq > Ollama.
    MCP servers are connected via MCPTools(command=...) using the commands below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- Model Provider ------------------------------------------
    default_model_provider: str = Field(default="openai", description="Primary model provider")
    default_model_id: str = Field(default="gpt-4o", description="Model ID to use")
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    groq_api_key: Optional[str] = Field(default=None)
    ollama_base_url: Optional[str] = Field(default=None)

    # -- Database ------------------------------------------------
    platform_db_url: str = Field(
        description="PostgreSQL connection string for operational tables (no default — must be set via env)",
    )

    # Database connection pool tuning
    db_pool_size: int = Field(default=10, description="SQLAlchemy pool size")
    db_max_overflow: int = Field(default=20, description="SQLAlchemy max overflow connections")
    db_pool_recycle: int = Field(default=3600, description="Seconds after which connections are recycled")

    # -- Knowledge -----------------------------------------------
    knowledge_base_path: str = Field(
        default="./knowledge/platform",
        description="Filesystem path to project docs/chats for ingestion",
    )

    # -- MCP Server Commands -------------------------------------
    ts_mcp_command: str = Field(
        default="node mcp-servers/ts-mcp-server/dist/index.js",
        description="Command to start the TypeScript MCP server",
    )
    py_mcp_command: str = Field(
        default="python mcp-servers/py-mcp-server/main.py",
        description="Command to start the Python MCP server",
    )
    js_mcp_command: Optional[str] = Field(
        default=None,
        description="Command to start the JS MCP server (optional in MVP)",
    )

    # -- MCP Server URLs (for HTTP-based communication) ----------
    ts_mcp_server_url: Optional[str] = Field(
        default=None,
        description="HTTP URL for the TypeScript MCP server (used in containerized setups)",
    )
    py_mcp_server_url: Optional[str] = Field(
        default=None,
        description="HTTP URL for the Python MCP server (used in containerized setups)",
    )

    # -- HITL ----------------------------------------------------
    hitl_require_approval: bool = Field(default=True)
    hitl_approval_timeout_seconds: int = Field(default=3600)

    # -- API -----------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authenticating POST/DELETE endpoints. If unset, auth is disabled.",
    )

    def get_model(self) -> Any:
        """Factory: return the best available Agno model based on configured keys."""
        provider = self.default_model_provider.lower()
        model_id = self.default_model_id

        # Try requested provider first
        if provider == "openai" and self.openai_api_key:
            from agno.models.openai import OpenAIChat
            return OpenAIChat(id=model_id, api_key=self.openai_api_key)
        elif provider == "anthropic" and self.anthropic_api_key:
            from agno.models.anthropic import Claude
            return Claude(id=model_id, api_key=self.anthropic_api_key)
        elif provider == "google" and self.google_api_key:
            from agno.models.google import Gemini
            return Gemini(id=model_id, api_key=self.google_api_key)
        elif provider == "groq" and self.groq_api_key:
            from agno.models.groq import Groq
            return Groq(id=model_id, api_key=self.groq_api_key)
        elif provider == "ollama" and self.ollama_base_url:
            from agno.models.ollama import Ollama
            return Ollama(id=model_id, host=self.ollama_base_url)

        # Fallback: try each provider in priority order
        if self.openai_api_key:
            from agno.models.openai import OpenAIChat
            return OpenAIChat(id="gpt-4o", api_key=self.openai_api_key)
        if self.anthropic_api_key:
            from agno.models.anthropic import Claude
            return Claude(id="claude-sonnet-4-20250514", api_key=self.anthropic_api_key)
        if self.google_api_key:
            from agno.models.google import Gemini
            return Gemini(id="gemini-2.0-flash", api_key=self.google_api_key)
        if self.groq_api_key:
            from agno.models.groq import Groq
            return Groq(id="llama-3.3-70b-versatile", api_key=self.groq_api_key)
        if self.ollama_base_url:
            from agno.models.ollama import Ollama
            return Ollama(id="llama3.1", host=self.ollama_base_url)

        raise ValueError(
            "No model provider API key found. Set at least one of: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, GROQ_API_KEY, OLLAMA_BASE_URL"
        )

    def get_db_engine(self) -> Any:
        """Return SQLAlchemy async engine for operational database with tuned pool."""
        from sqlalchemy.ext.asyncio import create_async_engine
        return create_async_engine(
            self.platform_db_url,
            echo=False,
            pool_size=self.db_pool_size,
            max_overflow=self.db_max_overflow,
            pool_recycle=self.db_pool_recycle,
        )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
