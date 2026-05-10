from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Configuration(SQLModel, table=True):
    """Stores generated device configurations with full metadata for history."""

    id: Optional[int] = Field(default=None, primary_key=True)
    device_name: str = Field(index=True)
    os_type: str = Field(default="")        # e.g. cisco_ios_complete
    template_name: str = Field(default="")  # human-readable label
    generated_content: str
    ai_review: Optional[str] = Field(default=None)  # JSON string of AI review result
    created_at: datetime = Field(default_factory=datetime.utcnow)
