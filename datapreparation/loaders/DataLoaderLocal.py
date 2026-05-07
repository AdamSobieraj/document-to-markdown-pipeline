import logging
import os
from typing import Generator

from interfaces.DataLoader import BaseDataLoader
from config_loader import get_settings

logger = logging.getLogger(__name__)


class LocalDataLoader(BaseDataLoader):
    """
    Loads raw data from local file system.
    Only responsible for reading files - no parsing, no metadata.
    """

    def __init__(self, directory: str):
        """
        Args:
            directory: Path to directory with files
        """
        self.directory = os.path.abspath(directory)

        if not os.path.exists(self.directory):
            raise ValueError(f"Directory does not exist: {self.directory}")

        logger.info("LocalDataLoader: Reading from directory: %s", self.directory)

    def list_files(self) -> Generator[str, None, None]:
        """Lists all files in directory with allowed extensions."""

        settings = get_settings()
        allowed_exts = settings.get("chunking.allowed_extensions", [])
        ext_tuple = tuple(allowed_exts)

        for root, _, files in os.walk(self.directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ext_tuple:
                    yield os.path.join(root, file)

    def load_raw_data(self, file_path: str) -> bytes:
        """Loads raw file bytes from disk."""
        logger.debug(f"Loading raw data from disk: {file_path}")
        with open(file_path, 'rb') as f:
            return f.read()

    def extract_domain(self, file_path: str) -> str:
        """
        Extracts domain from file path.
        Domain is first folder relative to base directory.
        """
        rel_path = os.path.relpath(file_path, self.directory)
        normalized_path = rel_path.replace('\\', '/')
        parts = normalized_path.split('/')

        if len(parts) > 1:
            return parts[0]

        return os.path.basename(self.directory) or "local"