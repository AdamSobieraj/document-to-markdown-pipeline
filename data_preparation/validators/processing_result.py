"""Processing result validator."""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from langchain_core.documents import Document


class ProcessingResult(BaseModel):
    """Validation model for file processing results."""

    file_key: str = Field(
        ...,
        min_length=1,
        description="File key/path"
    )
    status: Literal["success", "error", "empty"] = Field(
        ...,
        description="Processing status"
    )
    document_count: Optional[int] = Field(
        None,
        ge=0,
        description="Number of documents generated"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="File metadata"
    )
    documents: Optional[List[Document]] = Field(
        None,
        description="Generated documents"
    )

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode='after')
    def validate_status_fields(self):
        """
        Cross-validate status with other fields.

        Rules:
        - Success status requires document_count > 0 and metadata
        - Error status requires error message
        """
        if self.status == "success":
            if self.document_count is None or self.document_count == 0:
                raise ValueError("Success status must have document_count > 0")
            if self.metadata is None:
                raise ValueError("Success status must have metadata")

        elif self.status == "error":
            if self.error is None or self.error == "":
                raise ValueError("Error status must have error message")

        return self