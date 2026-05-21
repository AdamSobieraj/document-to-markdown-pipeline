import logging
import os
from typing import Dict

from parsers.base_parser import BaseDocumentParser
from parsers.text_parser import TextParser
from parsers.pdf_parser import PdfParser
from parsers.docx_parser import DocxParser
from parsers.xlsx_parser import XlsxParser
from parsers.pptx_parser import PptxParser

logger = logging.getLogger(__name__)


class ParserSelector:
    """
    Selects appropriate parser based on file extension.
    Implements lazy loading for heavy parsers.
    """

    def __init__(self):
        # Parser factories for lazy loading
        self.parser_factories: Dict[str, type[BaseDocumentParser]] = {
            ".pdf": PdfParser,
            ".docx": DocxParser,
            ".xlsx": XlsxParser,
            ".pptx": PptxParser,
        }

        # Cached parser instances
        self.parsers: Dict[str, BaseDocumentParser] = {}

        # Default parser for text files
        self.default_parser = TextParser()

    def get_parser(self, file_key: str) -> BaseDocumentParser:
        """
        Returns appropriate parser for file.

        Args:
            file_key: File path/key

        Returns:
            BaseDocumentParser: Parser instance
        """
        ext = os.path.splitext(file_key)[1].lower()

        # Use default parser for text-based files
        if ext not in self.parser_factories:
            logger.debug(f"Using default TextParser for extension: {ext}")
            return self.default_parser

        # Lazy load parser if needed
        if ext not in self.parsers:
            logger.info(f"Initializing parser for extension: {ext}")
            self.parsers[ext] = self.parser_factories[ext]()

        return self.parsers[ext]

    def needs_bytes_io(self, file_key: str) -> bool:
        """
        Checks if parser needs BytesIO wrapper instead of raw bytes.

        Args:
            file_key: File path/key

        Returns:
            bool: True if BytesIO wrapper needed
        """
        ext = os.path.splitext(file_key)[1].lower()
        return ext in self.parser_factories