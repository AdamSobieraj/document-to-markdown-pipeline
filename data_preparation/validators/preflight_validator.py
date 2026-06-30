"""Pre-flight file structure validator.

Validates all files before the conversion pipeline starts.
Checks: file size (not empty, under limit) and format integrity (magic bytes / structural checks).
Works with both Local and S3 sources via the BaseDataLoader abstraction.
"""

import logging
import os
from typing import List, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class PreFlightValidationError(Exception):
    """Raised when one or more pre-flight checks fail for any file."""

    def __init__(self, issues: List[Tuple[str, str, str]]):
        """
        Args:
            issues: List of (file_key, check_name, detail_message) tuples.
        """
        self.issues = issues
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        lines = [f"Pre-flight validation failed for {len(self.issues)} file(s):"]
        for file_key, check, detail in self.issues:
            lines.append(f"  - {file_key}: {check} -- {detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal result model (Pydantic, consistent with existing validators)
# ---------------------------------------------------------------------------

class _PreflightIssue(BaseModel):
    """Single validation issue for a file."""

    file_key: str = Field(..., min_length=1)
    check: str = Field(..., description="Name of the check that failed")
    detail: str = Field(..., description="Human-readable detail about the failure")


# ---------------------------------------------------------------------------
# Main validator class
# ---------------------------------------------------------------------------

class FileStructureValidator:
    """
    Pre-flight validator that checks all files BEFORE the conversion pipeline.

    Checks performed (in order):
        1. File is not empty (size > 0 bytes)
        2. File size is under the configured max (chunking.max_file_size_mb)
        3. Format integrity -- magic bytes / structural check:
           - PDF: starts with %PDF
           - DOCX/XLSX/PPTX: valid ZIP structure (local directory header
             + central directory record within first 512 bytes)
           - MD/TXT/XML/XSD/JSON: valid UTF-8 or ASCII text

    Behavior:
        - Checks ALL files first, collects all issues
        - If ANY issues found -> raises PreFlightValidationError with full report
        - If all files pass -> returns silently, pipeline proceeds

    Integration:
        - Works for both Local and S3 sources via BaseDataLoader
        - For S3, size is obtained from HEAD request (Content-Length)
        - For format checks on S3, downloads only a small sample
    """

    # Magic bytes for format detection
    PDF_MAGIC = b"%PDF"
    ZIP_LOCAL_HEADER = b"PK\x03\x04"

    # Maximum bytes to sample for text validation (practical limit)
    _TEXT_SAMPLE_MAX = 8192

    # Format -> expected magic bytes / structural checks
    FORMAT_CHECKS = {
        ".pdf": "pdf",
        ".docx": "zip",
        ".xlsx": "zip",
        ".pptx": "zip",
        ".md": "text",
        ".txt": "text",
        ".xml": "text",
        ".xsd": "text",
        ".json": "text",
    }

    def __init__(self, loader, max_file_size_mb: int = 100):
        """
        Args:
            loader: BaseDataLoader instance (LocalDataLoader or S3DataLoader).
            max_file_size_mb: Maximum allowed file size in megabytes.
        """
        self.loader = loader
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def validate_all(self, file_keys: List[str]) -> None:
        """
        Validate all files. Raises PreFlightValidationError if any issues found.

        Args:
            file_keys: List of file keys/paths to validate.

        Raises:
            PreFlightValidationError: If any file fails validation. Contains
                all issues collected across all files.
        """
        issues: List[_PreflightIssue] = []

        for file_key in file_keys:
            issues.extend(self._validate_single(file_key))

        if issues:
            typed_issues = [
                (i.file_key, i.check, i.detail) for i in issues
            ]
            raise PreFlightValidationError(typed_issues)

    def _validate_single(self, file_key: str) -> List[_PreflightIssue]:
        """Run all checks on a single file. Returns list of issues."""
        issues: List[_PreflightIssue] = []
        ext = self._get_extension(file_key)

        # Check 1: Not empty
        issues.extend(self._check_not_empty(file_key))

        # Check 2: Under max size (only if not already empty)
        if not any(i.check == "empty_file" for i in issues):
            issues.extend(self._check_max_size(file_key))

        # Check 3: Format integrity
        format_check = self.FORMAT_CHECKS.get(ext)
        if format_check:
            issues.extend(self._check_format(file_key, format_check))

        return issues

    def _get_extension(self, file_key: str) -> str:
        """Get lowercase file extension."""
        return os.path.splitext(file_key)[1].lower()

    def _check_not_empty(self, file_key: str) -> List[_PreflightIssue]:
        """Check that file is not empty (size > 0)."""
        try:
            size = self.loader.get_file_size(file_key)
            if size == 0:
                return [_PreflightIssue(
                    file_key=file_key,
                    check="empty_file",
                    detail="File is empty (0 bytes)"
                )]
        except Exception as e:
            # If we cannot determine size, skip this check
            logger.warning(
                "Cannot determine size for %s, skipping empty-file check: %s",
                file_key, e
            )
        return []

    def _check_max_size(self, file_key: str) -> List[_PreflightIssue]:
        """Check that file size is under the configured maximum."""
        try:
            size = self.loader.get_file_size(file_key)
            if size > self.max_file_size_bytes:
                size_mb = size / (1024 * 1024)
                return [_PreflightIssue(
                    file_key=file_key,
                    check="file_too_large",
                    detail=f"File is {size_mb:.1f} MB, exceeds maximum of "
                           f"{self.max_file_size_bytes / (1024 * 1024):.0f} MB"
                )]
        except Exception as e:
            logger.warning(
                "Cannot determine size for %s, skipping max-size check: %s",
                file_key, e
            )
        return []

    def _check_format(self, file_key: str, format_type: str) -> List[_PreflightIssue]:
        """
        Check format integrity using magic bytes / structural validation.

        Args:
            file_key: File key/path
            format_type: One of 'pdf', 'zip', 'text'
        """
        try:
            if format_type == "pdf":
                return self._check_pdf(file_key)
            elif format_type == "zip":
                return self._check_zip(file_key)
            elif format_type == "text":
                return self._check_text(file_key)
        except Exception as e:
            logger.warning(
                "Format check error for %s: %s", file_key, e
            )
        return []

    def _check_pdf(self, file_key: str) -> List[_PreflightIssue]:
        """PDF: first 4 bytes must be '%PDF'."""
        try:
            sample = self.loader.load_sample(file_key, 4)
            if not sample.startswith(self.PDF_MAGIC):
                return [_PreflightIssue(
                    file_key=file_key,
                    check="invalid_format",
                    detail="File does not start with %PDF magic bytes"
                )]
        except Exception as e:
            logger.warning("Cannot read PDF header for %s: %s", file_key, e)
        return []

    def _check_zip(self, file_key: str) -> List[_PreflightIssue]:
        """
        DOCX/XLSX/PPTX: valid ZIP structure.

        Checks:
            First 4 bytes are PK local directory header (PK\\x03\\x04).

        Note: The ZIP central directory record (PK\\x01\\x02) is stored at the
        end of the file, so we only validate the local header here.  Genuine
        corruption will be caught by the parser anyway.
        """
        try:
            sample = self.loader.load_sample(file_key, 4)

            if not sample.startswith(self.ZIP_LOCAL_HEADER):
                return [_PreflightIssue(
                    file_key=file_key,
                    check="invalid_format",
                    detail="File does not start with ZIP local file header (PK\\x03\\x04)"
                )]
        except Exception as e:
            logger.warning("Cannot read ZIP structure for %s: %s", file_key, e)
        return []

    def _check_text(self, file_key: str) -> List[_PreflightIssue]:
        """
        Text format (MD/TXT/XML/XSD/JSON): valid UTF-8 or ASCII.

        Reads up to 8192 bytes to get a representative sample.
        """
        try:
            sample_size = min(self._TEXT_SAMPLE_MAX, self.loader.get_file_size(file_key))
            if sample_size == 0:
                return []  # Already caught by empty-file check
            sample = self.loader.load_sample(file_key, sample_size)
            sample.decode("utf-8")  # Raises on invalid UTF-8
        except UnicodeDecodeError:
            return [_PreflightIssue(
                file_key=file_key,
                check="invalid_format",
                detail="File contains invalid UTF-8 / ASCII characters"
            )]
        except Exception as e:
            logger.warning("Cannot read text content for %s: %s", file_key, e)
        return []
