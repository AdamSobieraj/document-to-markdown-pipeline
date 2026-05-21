"""Local filesystem configuration validator."""

from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class LocalConfig(BaseModel):
    """Validation model for Local filesystem configuration."""

    directory: str = Field(
        ...,
        min_length=1,
        description="Local directory path"
    )
    output_directory: Optional[str] = Field(
        None,
        description="Output directory path"
    )

    @field_validator('directory', 'output_directory')
    @classmethod
    def validate_directory(cls, v):
        """
        Validate directory path.

        Checks:
        - Path is valid format
        - Can be resolved
        """
        if v is None:
            return v

        path = Path(v)

        # Check if path is valid (will raise if invalid characters)
        try:
            path.resolve()
        except Exception as e:
            raise ValueError(f"Invalid directory path: {v}. Error: {e}")

        return str(path)