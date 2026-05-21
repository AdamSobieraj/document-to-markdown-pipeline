"""S3 configuration validator."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class S3Config(BaseModel):
    """Validation model for S3 configuration."""

    bucket_name: str = Field(
        ...,
        min_length=3,
        max_length=63,
        description="S3 bucket name"
    )
    prefix: str = Field(
        default="",
        description="S3 prefix/folder path"
    )
    output_bucket: Optional[str] = Field(
        None,
        min_length=3,
        max_length=63,
        description="Output S3 bucket name"
    )

    @field_validator('bucket_name', 'output_bucket')
    @classmethod
    def validate_bucket_name(cls, v):
        """
        Validate S3 bucket name format.

        Rules:
        - Must be 3-63 characters
        - Can contain alphanumeric, hyphens, and dots
        - Cannot start or end with hyphen
        - Must be lowercase
        """
        if v is None:
            return v

        if not v.replace('-', '').replace('.', '').isalnum():
            raise ValueError(
                f"Invalid bucket name: {v}. "
                "Must contain only alphanumeric characters, hyphens, and dots"
            )

        if v.startswith('-') or v.endswith('-'):
            raise ValueError(f"Bucket name cannot start or end with hyphen: {v}")

        return v.lower()

    @field_validator('prefix')
    @classmethod
    def validate_prefix(cls, v):
        """Validate S3 prefix - should not start with /"""
        if v and v.startswith('/'):
            raise ValueError("Prefix should not start with '/'")
        return v