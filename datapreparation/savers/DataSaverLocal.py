import logging
import os
import json
from typing import Dict, Any

from interfaces.DataSaver import BaseDataSaver

logger = logging.getLogger(__name__)


class LocalDataSaver(BaseDataSaver):
    """
    Saves markdown files to local file system.
    Only responsible for writing files - no parsing, no metadata building.
    """

    def __init__(self, base_directory: str):
        """
        Args:
            base_directory: Base directory for source files
        """
        self.base_directory = os.path.abspath(base_directory)
        self.markdown_directory = self.base_directory + "_markdown"

    def save_markdown(
            self,
            source_path: str,
            markdown_content: str,
    ) -> str:
        """
        Saves markdown to local file system.

        Args:
            source_path: Original file path (e.g., "/data/HR/file.pdf")
            markdown_content: Markdown text to save

        Returns:
            str: Path to saved markdown file
        """
        markdown_path = self._build_markdown_path(source_path)

        # Create directory if needed
        os.makedirs(os.path.dirname(markdown_path), exist_ok=True)

        # Write file
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info(f"Saved markdown to: {markdown_path}")
        return markdown_path

    def save_metadata(
            self,
            source_path: str,
            metadata: Dict[str, Any],
    ) -> str:
        """
        Saves metadata as JSON to local file system.

        Args:
            source_path: Original file path (e.g., "/data/HR/file.pdf")
            metadata: Metadata dictionary to save

        Returns:
            str: Path to saved metadata file
        """
        metadata_path = self._build_metadata_path(source_path)

        # Create directory if needed
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

        # Write JSON file
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved metadata to: {metadata_path}")
        return metadata_path

    def get_markdown_url(self, markdown_path: str) -> str:
        """Generates file:// URL for markdown file."""
        return f"file://{markdown_path}"

    def _build_markdown_path(self, source_path: str) -> str:
        """
        Builds path for markdown file.
        E.g., "/data/HR/file.pdf" -> "/data_markdown/HR/file.md"
        """
        rel_path = os.path.relpath(source_path, self.base_directory)
        base_name = os.path.splitext(rel_path)[0]
        markdown_rel_path = base_name + ".md"

        return os.path.join(self.markdown_directory, markdown_rel_path)