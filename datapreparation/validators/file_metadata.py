"""File metadata validator."""

from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class FileMetadata(BaseModel):
    """
    Validation model for file metadata.

    Made flexible to accommodate different metadata structures
    from various metadata builders.
    """

    # Core fields (some may be optional depending on builder implementation)
    file_key: Optional[str] = Field(None, min_length=1)
    domain: Optional[str] = Field(None, min_length=1)
    source_url: Optional[str] = Field(None, min_length=1)
    storage_type: Optional[Literal["s3", "local"]] = None
    markdown_path: Optional[str] = Field(None, min_length=1)
    markdown_url: Optional[str] = Field(None, min_length=1)

    # Alternative field names (for compatibility)
    source: Optional[str] = Field(None, min_length=1)

    # Additional optional fields
    file_size: Optional[int] = Field(None, ge=0)
    created_at: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional fields not explicitly defined

    @field_validator('source_url', 'markdown_url', 'source')
    @classmethod
    def validate_url(cls, v):
        """
        Validate URL format.

        Accepted protocols:
        - s3://
        - file://
        - http://
        - https://
        """
        if v is None:
            return v

        valid_protocols = ('s3://', 'file://', 'http://', 'https://')

        if not v.startswith(valid_protocols):
            # Just warn instead of raising error for flexibility
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"URL '{v}' doesn't start with standard protocol. "
                f"Expected one of: {', '.join(valid_protocols)}"
            )

        return v

    @model_validator(mode='after')
    def validate_has_some_required_fields(self):
        """
        Ensure at least some core fields are present.
        This is a soft validation - we just warn if critical fields are missing.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check if we have some identifier
        if not any([self.file_key, self.source, self.source_url]):
            logger.warning("Metadata missing file identifier (file_key, source, or source_url)")

        # Check if we have markdown location
        if not any([self.markdown_path, self.markdown_url]):
            logger.warning("Metadata missing markdown location (markdown_path or markdown_url)")

        return self