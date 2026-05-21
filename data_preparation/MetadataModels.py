from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional

@dataclass
class BaseMetadata:
    """
    Wspólne pola dla plików i chunków.
    Definiuje "kręgosłup" metadanych w systemie.
    """
    source: str  # Mandatory URI (file:// lub s3://)
    title: Optional[str] = None
    url: Optional[str] = None
    extension: Optional[str] = None
    domain: Optional[str] = "general"
    tags: List[str] = field(default_factory=list)
    page_number: Optional[int] = None

    # Numeracja linii w oryginalnym pliku
    embedding_line_start: Optional[int] = None
    embedding_line_end: Optional[int] = None

    # Numeracja linii w oryginalnym pliku
    document_line_start: Optional[int] = None
    document_line_end: Optional[int] = None

    def _clean_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pomocnicza metoda usuwająca None z wyników. Zostawia przypisane wartości, w tym page_number."""
        return {k: v for k, v in data.items() if v is not None}

@dataclass
class FileMetadata(BaseMetadata):
    """
    Model używany przez Loadery (S3/Local).
    Reprezentuje cały plik przed pocięciem.
    """
    def to_dict(self) -> Dict[str, Any]:
        return self._clean_dict(asdict(self))

@dataclass
class ChunkMetadata(BaseMetadata):
    """
    Model używany przez Chunkery (LangChain/NoLib).
    Reprezentuje pojedynczy wektor w bazie Qdrant.
    """
    phrase: str = ""  # Treść fragmentu
    phrase_metadata_id: str = ""  # Unikalne ID

    # Kontener na dane nadmiarowe/niezdefiniowane
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """
        Generuje płaski słownik gotowy do wstawienia do Qdrant.
        """
        data = asdict(self)

        # 1. Wyciągamy i spłaszczamy extra_data
        extras = data.pop("extra_data", {})

        # 2. Usuwamy None (jeśli page_number ma np. 1, to zostaje w słowniku!)
        clean_data = self._clean_dict(data)

        # 3. Scalamy (Schema ma priorytet nad extras)
        return {**extras, **clean_data}