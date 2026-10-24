"""Configuration management for DocuMind AI.

Safely loads configuration from environment variables and .env file.
Adheres to AWS security best practices (never exposes credentials or logs them).
"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()


def mask_secret(value: Optional[str], visible_chars: int = 4) -> str:
    """Safely mask sensitive strings for display in UI or logs."""
    if not value:
        return "[Not Configured]"
    if len(value) <= visible_chars * 2:
        return "****"
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"


@dataclass(frozen=True)
class AppConfig:
    """Application configuration parameters."""
    
    # AWS Core Settings
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "")
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token: Optional[str] = os.getenv("AWS_SESSION_TOKEN")
    
    # S3 Restrictions
    s3_document_prefix: str = os.getenv("S3_DOCUMENT_PREFIX", "documents/")
    max_document_size_mb: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "10"))
    allowed_extensions: tuple = (".pdf", ".txt")
    
    # AI / LLM Configuration
    llm_provider: str = os.getenv("LLM_PROVIDER", "bedrock").lower()
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
    )
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    
    # Retrieval Hyperparameters
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "4"))
    passage_chunk_size: int = int(os.getenv("PASSAGE_CHUNK_SIZE", "400"))
    passage_chunk_overlap: int = int(os.getenv("PASSAGE_CHUNK_OVERLAP", "60"))
    min_relevance_score: float = float(os.getenv("MIN_RELEVANCE_SCORE", "0.5"))

    @property
    def max_document_size_bytes(self) -> int:
        return self.max_document_size_mb * 1024 * 1024

    def is_s3_configured(self) -> bool:
        """Checks if S3 bucket name is set."""
        return bool(self.s3_bucket_name and self.s3_bucket_name.strip())

    def is_llm_configured(self) -> bool:
        """Checks if at least one selected LLM provider has configuration."""
        if self.llm_provider == "bedrock":
            # Bedrock relies on AWS credentials or IAM role + region
            return bool(self.aws_region and self.bedrock_model_id)
        elif self.llm_provider == "openai":
            return bool(self.openai_api_key and self.openai_api_key.strip())
        elif self.llm_provider == "gemini":
            return bool(self.gemini_api_key and self.gemini_api_key.strip())
        return False

    def get_masked_bucket(self) -> str:
        """Return safe representation of bucket name."""
        if not self.s3_bucket_name:
            return "Not Configured"
        if len(self.s3_bucket_name) <= 6:
            return self.s3_bucket_name
        return f"{self.s3_bucket_name[:3]}...{self.s3_bucket_name[-3:]}"


def get_config() -> AppConfig:
    """Fetch current application configuration."""
    return AppConfig()
