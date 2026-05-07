from abc import ABC, abstractmethod
from typing import Generator


class BaseDataLoader(ABC):
    """
    Interface for loading raw data from different sources.
    Responsible ONLY for reading files and listing them.
    """

    @abstractmethod
    def list_files(self) -> Generator[str, None, None]:
        """
        Lists all files available in the source.

        Yields:
            str: File key/path
        """
        pass

    @abstractmethod
    def load_raw_data(self, file_key: str) -> bytes:
        """
        Loads raw file data as bytes.

        Args:
            file_key: File key/path to load

        Returns:
            bytes: Raw file content
        """
        pass

    @abstractmethod
    def extract_domain(self, file_key: str) -> str:
        """
        Extracts domain (main folder) from file key.

        Args:
            file_key: File key/path

        Returns:
            str: Domain name
        """
        pass