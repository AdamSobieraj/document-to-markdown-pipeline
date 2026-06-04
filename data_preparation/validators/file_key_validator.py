"""File key/path validator."""

import os
import logging
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

valid_extensions_env = os.getenv('VALID_FILE_EXTENSIONS', '')
VALID_FILE_EXTENSIONS = [ext.strip() for ext in valid_extensions_env.split(',') if ext.strip()]

class FileKeyValidator(BaseModel):
    """Validation model for file keys/paths."""

    file_key: str = Field(..., min_length=1)

    @field_validator('file_key')
    @classmethod
    def validate_file_key(cls, v):
        """
        Validate file key format.

        Checks:
        - Not empty
        - No invalid characters (backslash, null)
        - Warns about unusual file extensions
        """
        if not v or v.strip() == "":
            raise ValueError("File key cannot be empty")

        # Check for invalid characters
        invalid_chars = ['\\', '\0']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"File key contains invalid character: {char}")

        # Extract extension and validate
        ext = os.path.splitext(v)[1].lower()
        if ext:
            if ext not in VALID_FILE_EXTENSIONS:
                logger.warning(f"File {v} has unusual extension: {ext}")

        return v