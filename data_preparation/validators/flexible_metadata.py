"""Flexible metadata validator that adapts to different structures."""

from typing import Dict, Any
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class FlexibleMetadata(BaseModel):
    """
    Flexible metadata validator that accepts any structure.

    This validator performs basic checks without enforcing a strict schema,
    allowing the metadata builder to define its own structure.
    """

    metadata: Dict[str, Any] = Field(..., description="Metadata dictionary")

    class Config:
        extra = "allow"

    @classmethod
    def validate_metadata(cls, metadata: Dict[str, Any]) -> bool:
        """
        Validate metadata dictionary with flexible rules.

        Args:
            metadata: Metadata dictionary to validate

        Returns:
            True if validation passes, False otherwise
        """
        if not isinstance(metadata, dict):
            logger.error(f"Metadata must be a dictionary, got {type(metadata)}")
            return False

        if not metadata:
            logger.warning("Metadata dictionary is empty")
            return False

        # Log the structure for debugging
        logger.debug(f"Metadata structure: {list(metadata.keys())}")

        # Check for common URL fields
        url_fields = ['source', 'source_url', 'markdown_url', 'markdown_path']
        found_urls = [field for field in url_fields if field in metadata]

        if found_urls:
            for field in found_urls:
                value = metadata[field]
                if isinstance(value, str) and value:
                    logger.debug(f"Found URL field '{field}': {value[:50]}...")
        else:
            logger.warning("No URL fields found in metadata")

        return True