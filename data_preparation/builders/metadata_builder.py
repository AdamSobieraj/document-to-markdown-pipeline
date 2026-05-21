import os
from typing import Dict, Any, List

from langchain_core.documents import Document

from MetadataModels import FileMetadata


class MetadataBuilder:
    """
    Builds metadata objects for files and documents.
    Centralizes metadata creation logic.
    """

    @staticmethod
    def build_file_metadata(
            file_key: str,
            domain: str,
            source_url: str,
            storage_type: str,
            markdown_path: str = None,
            markdown_url: str = None,
    ) -> Dict[str, Any]:
        """
        Builds complete file metadata.

        Args:
            file_key: File key/path
            domain: Domain name (main folder)
            source_url: Full URL to source file
            storage_type: Type of storage ("s3" or "local")
            markdown_path: Path to markdown file (optional)
            markdown_url: URL to markdown file (optional)

        Returns:
            Dict with file metadata
        """
        filename = os.path.basename(file_key)
        ext = os.path.splitext(file_key)[1].lower()

        # Create base metadata object
        meta_obj = FileMetadata(
            source=source_url,
            title=filename,
            extension=ext,
            url=source_url,
            domain=domain,
            tags=[storage_type, domain.lower()],
            page_number=None,
        )

        # Convert to dict
        metadata = meta_obj.to_dict()

        # Add markdown paths if available
        if markdown_path:
            metadata["markdown_path"] = markdown_path
        if markdown_url:
            metadata["markdown_url"] = markdown_url

        return metadata

    @staticmethod
    def enrich_documents(
            documents: List[Document],
            base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        Enriches documents with base metadata.
        Merges document-specific metadata with file-level metadata.

        Args:
            documents: List of documents to enrich
            base_metadata: Base metadata to add to all documents

        Returns:
            List of enriched documents
        """
        for doc in documents:
            merged_meta = base_metadata.copy()
            merged_meta.update(doc.metadata)
            doc.metadata = merged_meta

        return documents

    @staticmethod
    def combine_documents_to_markdown(documents: List[Document]) -> str:
        """
        Combines multiple documents into single markdown string.

        Args:
            documents: List of documents

        Returns:
            str: Combined markdown content
        """
        markdown_parts = []

        for index, doc in enumerate(documents):
            if index > 0:
                markdown_parts.append("\n\n---\n\n")

            # Add page number comment if available
            if doc.metadata.get('page_number'):
                markdown_parts.append(f"<!-- Page {doc.metadata['page_number']} -->\n\n")

            markdown_parts.append(doc.page_content)

        return "".join(markdown_parts)