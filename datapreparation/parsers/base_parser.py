import io
from abc import ABC, abstractmethod
from typing import List, Union
from langchain_core.documents import Document


class BaseDocumentParser(ABC):
    """Abstrakcyjna klasa bazowa dla wszystkich parserów dokumentów."""

    @abstractmethod
    def parse(self, file_source: Union[str, io.BytesIO, bytes], **kwargs) -> List[Document]:
        """
        Przetwarza plik (lokalny lub strumień z pamięci RAM) i zwraca
        listę obiektów Document (z zawartością w formacie Markdown).
        """
        pass