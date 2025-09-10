from typing import Literal, Optional
from datetime import datetime
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram - General news group
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    telegram_group_id: int = Field(..., description="Telegram group/channel ID for general cybersecurity news")
    telegram_topic_id: Optional[int] = Field(None, description="Topic ID for general news in forum supergroups")
    
    # Telegram - Vulnerabilities group
    telegram_vulnerabilities_group_id: int = Field(..., description="Telegram group/channel ID for vulnerability news")
    telegram_vulnerabilities_topic_id: Optional[int] = Field(None, description="Topic ID for vulnerability news in forum supergroups")
    
    # Database
    database_url: str = Field(
        ...,  # Required field, no default
        description="Database connection URL (PostgreSQL/Supabase)"
    )
    
    # Parser
    parse_interval_minutes: int = Field(default=120, ge=5, le=1440)  # 2 hours
    max_articles_per_fetch: int = Field(default=10, ge=1, le=50)
    max_articles_per_category: int = Field(default=5, ge=1, le=25, description="Max articles per category (general/vulnerabilities)")
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)
    min_article_date: str = Field(default="2025-08-01", description="Minimum article date (YYYY-MM-DD)")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    
    # Translation
    translation_target_language: str = Field(default="ru", description="Target language for translation")
    translation_source_language: str = Field(default="auto", description="Source language for translation")
    microsoft_translator_key: Optional[str] = Field(default=None, description="Microsoft Translator API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key for ChatGPT translator")
    
    # Proxy settings
    proxy_url: Optional[str] = Field(default=None, description="HTTP proxy URL (e.g., http://proxy:8080)")
    proxy_username: Optional[str] = Field(default=None, description="Proxy username")
    proxy_password: Optional[str] = Field(default=None, description="Proxy password")
    
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_format: Literal["json", "console"] = Field(default="json")
    
    # Monitoring
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=8000, ge=1024, le=65535)
    
    # Sentry
    sentry_dsn: Optional[str] = Field(default=None)
    
    # Environment
    environment: Literal["development", "production"] = Field(
        default="development"
    )
    
    # API
    parse_api_key: Optional[str] = Field(default=None, description="API key for manual parse trigger")
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        # Clean up the URL if it contains the variable name prefix
        if v.startswith("DATABASE_URL="):
            v = v.replace("DATABASE_URL=", "", 1)
        
        # Strip any whitespace
        v = v.strip()
        
        # Remove any extra spaces in the URL (common copy-paste error)
        import re
        v = re.sub(r'\s+', '', v)
        
        # Support both sync and async PostgreSQL drivers
        if v.startswith("postgresql://"):
            # Convert to async driver for SQLAlchemy async
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Validate supported database types
        if not v.startswith(("sqlite", "postgresql+asyncpg", "postgresql+psycopg", "mysql")):
            # Try to provide helpful error message
            if "postgres" in v.lower():
                raise ValueError(f"Database URL should start with 'postgresql+asyncpg://' not '{v[:30]}...'")
            raise ValueError(f"Unsupported database type. URL starts with: '{v[:50]}...'")
        return v
    
    @field_validator("min_article_date")
    @classmethod
    def validate_min_article_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("min_article_date must be in YYYY-MM-DD format")
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def min_article_datetime(self) -> datetime:
        return datetime.strptime(self.min_article_date, "%Y-%m-%d")


settings = Settings()