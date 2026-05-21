from abc import ABC, abstractmethod
from typing import Dict, Any
import json


class BaseDataSaver(ABC):
    """
    Interface for saving markdown data to different destinations.
    Responsible ONLY for writing files.
    """

    @abstractmethod
    def save_markdown(
            self,
            source_key: str,
            markdown_content: str,
    ) -> str:
        """
        Saves markdown content to appropriate location.

        Args:
            source_key: Original source file key/path
            markdown_content: Markdown text to save

        Returns:
            str: Path/URL to saved markdown file
        """
        pass

    @abstractmethod
    def save_metadata(
            self,
            source_key: str,
            metadata: Dict[str, Any],
    ) -> str:
        """
        Saves metadata as JSON to appropriate location.

        Args:
            source_key: Original source file key/path
            metadata: Metadata dictionary to save

        Returns:
            str: Path/URL to saved metadata file
        """
        pass

    @abstractmethod
    def get_markdown_url(self, markdown_key: str) -> str:
        """
        Generates public URL for markdown file.

        Args:
            markdown_key: Markdown file key/path

        Returns:
            str: Public URL
        """
        pass