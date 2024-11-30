from datetime import datetime
from typing import Optional

from pydantic import AnyUrl, Field

from .base import NoSQLBaseLink


class Link(NoSQLBaseLink):
    title: str = Field(..., description="The title of the link")
    url: AnyUrl = Field(description="The URL of the link")
    source: Optional[str] = Field(None, description="The source of the link")
    published_at: Optional[datetime] = Field(None, description="The publication date of the link")
    extracted_at: datetime = Field(
        default_factory=datetime.now,
        description="The timestamp when the link was extracted",
    )

    class Settings:
        name = "link"