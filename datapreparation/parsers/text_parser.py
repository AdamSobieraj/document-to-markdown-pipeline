import logging
import io
from typing import List, Union
from langchain_core.documents import Document
from .base_parser import BaseDocumentParser

logger = logging.getLogger(__name__)


class TextParser(BaseDocumentParser):
    """Parser dla plików tekstowych (TXT, JSON, XML, kod), dodaje bloki kodu Markdown."""
    def parse(self, file_source: Union[str, io.BytesIO, bytes], **kwargs) -> List[Document]:
        ext = kwargs.get('ext', '')
        try:
            # Sprawdzamy czy to ścieżka do pliku, czy dane z pamięci (S3)
            if isinstance(file_source, str):
                with open(file_source, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            elif isinstance(file_source, bytes):
                content = file_source.decode("utf-8", errors="replace")
            elif isinstance(file_source, io.BytesIO):
                content = file_source.read().decode("utf-8", errors="replace")
            else:
                raise ValueError("Nieobsługiwany typ źródła pliku")

            if content.strip():
                ext_clean = ext.replace('.', '').lower()
                code_block_exts = {'json', 'xml', 'xsd', 'yaml', 'yml', 'js', 'py', 'java', 'html', 'csv'}

                if ext_clean in code_block_exts:
                    md_content = f"```{ext_clean}\n{content}\n```"
                else:
                    md_content = content

                return [Document(page_content=md_content, metadata={"page_number": 1})]
            return []
        except Exception as e:
            logger.error(f"Błąd odczytu tekstu: {e}")
            return []