import logging
from typing import Generator

from interfaces.DataLoader import BaseDataLoader
from DataLoaderS3Service import DataLoaderS3Service

logger = logging.getLogger(__name__)


class S3DataLoader(BaseDataLoader):
    """
    Loads raw data from S3.
    Only responsible for reading files - no parsing, no metadata.
    """

    def __init__(self, bucket_name: str, prefix: str = ""):
        """
        Args:
            bucket_name: S3 bucket name
            prefix: Folder prefix to filter files
        """
        self.bucket_name = bucket_name

        # Normalize prefix
        clean_prefix = prefix.strip() if prefix else ""
        if clean_prefix:
            self.prefix = f"{clean_prefix}/" if not clean_prefix.endswith("/") else clean_prefix
            logger.info("S3DataLoader: Set folder filter to: '%s'", self.prefix)
        else:
            self.prefix = ""
            logger.warning(
                "!!! WARNING: No prefix specified. Will process ENTIRE BUCKET !!!"
            )

        self.s3_service = DataLoaderS3Service()

    def list_files(self) -> Generator[str, None, None]:
        """Lists all files in S3 bucket with specified prefix."""
        return self.s3_service.list_objects(self.bucket_name, self.prefix)

    def load_raw_data(self, file_key: str) -> bytes:
        """Loads raw file bytes from S3."""
        logger.debug(f"Loading raw data from S3: {file_key}")
        return self.s3_service.download_bytes(self.bucket_name, file_key)

    def extract_domain(self, file_key: str) -> str:
        """
        Extracts top-level folder from S3 key.
        E.g., "technical/ISO20022/file.pdf" -> "technical"
        """
        clean_key = file_key.lstrip("/")
        parts = clean_key.split("/")
        return parts[0] if len(parts) > 1 else "general"