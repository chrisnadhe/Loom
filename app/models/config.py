from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Template(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    vendor: str # Cisco, Arista, Aruba, etc.
    content: str # The Jinja2 template content
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Configuration(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="template.id")
    device_name: str
    generated_content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
