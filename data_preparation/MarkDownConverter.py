import io
import logging
import os
import sys
from typing import List, Dict, Any, Literal

from langchain_core.documents import Document

from LoadConfig import get_settings
from builders.metadata_builder import MetadataBuilder
from interfaces.DataLoader import BaseDataLoader
from interfaces.DataSaver import BaseDataSaver
from loaders.DataLoaderLocal import LocalDataLoader
from loaders.DataLoaderS3 import S3DataLoader
from parsers.ParserSelector import ParserSelector
from savers.DataSaverLocal import LocalDataSaver
from savers.DataSaverS3 import S3DataSaver
# Import validators
from validators import (
    ConverterConfig,
    ProcessingResult,
    FileKeyValidator,
    FlexibleMetadata
)

logger = logging.getLogger(__name__)


class MarkDownConverter:
    """
    Main pipeline orchestrator for converting documents to Markdown.

    Pipeline steps:
        1. Load raw data (from S3 or Local)
        2. Select appropriate parser
        3. Parse to Markdown
        4. Save Markdown (to S3 or Local) with metadata

    Each step is delegated to specialized components following Single Responsibility Principle.
    """

    def __init__(
            self,
            source_type: Literal["s3", "local"],
            destination_type: Literal["s3", "local"] = None,
            **config
    ):
        """
        Args:
            source_type: Where to load files from ("s3" or "local")
            destination_type: Where to save markdown (defaults to same as source)
            **config: Configuration for source/destination

            For S3 source:
                - bucket_name (str): Bucket name
                - prefix (str, optional): Folder prefix

            For Local source:
                - directory (str): Directory path

            For S3 destination:
                - output_bucket (str, optional): Output bucket (defaults to source bucket)

            For Local destination:
                - output_directory (str, optional): Output directory (defaults to source_dir + "_markdown")
        """
        # Set destination type
        destination_type = destination_type or source_type

        # Validate configuration using Pydantic
        validated_config = ConverterConfig(
            source_type=source_type,
            destination_type=destination_type,
            config=config
        )

        self.source_type = validated_config.source_type
        self.destination_type = validated_config.destination_type

        # Initialize components with validated config
        self.loader = self._create_loader(self.source_type, validated_config.config)
        self.saver = self._create_saver(self.destination_type, validated_config.config)
        self.parser_selector = ParserSelector()
        self.metadata_builder = MetadataBuilder()

        logger.info(
            f"MarkDownConverter initialized: {self.source_type.upper()} -> {self.destination_type.upper()}"
        )

    def _create_loader(self, source_type: str, config: Dict[str, Any]) -> BaseDataLoader:
        """Factory method for creating data loader."""
        if source_type == "s3":
            bucket_name = config.get("bucket_name")
            if not bucket_name:
                raise ValueError("S3 source requires 'bucket_name' parameter")

            prefix = config.get("prefix", "")
            return S3DataLoader(bucket_name=bucket_name, prefix=prefix)

        elif source_type == "local":
            directory = config.get("directory")
            if not directory:
                raise ValueError("Local source requires 'directory' parameter")

            return LocalDataLoader(directory=directory)

        else:
            raise ValueError(f"Unknown source type: {source_type}")

    def _create_saver(self, destination_type: str, config: Dict[str, Any]) -> BaseDataSaver:
        """Factory method for creating data saver."""
        if destination_type == "s3":
            # Use output_bucket if specified, otherwise use source bucket
            bucket_name = config.get("output_bucket") or config.get("bucket_name")
            if not bucket_name:
                raise ValueError("S3 destination requires 'bucket_name' or 'output_bucket' parameter")

            return S3DataSaver(bucket_name=bucket_name)

        elif destination_type == "local":
            # Use output_directory if specified, otherwise derive from source directory
            directory = config.get("output_directory") or config.get("directory")
            if not directory:
                raise ValueError("Local destination requires 'directory' or 'output_directory' parameter")

            return LocalDataSaver(base_directory=directory)

        else:
            raise ValueError(f"Unknown destination type: {destination_type}")

    def process_all_files(self) -> List[Dict[str, Any]]:
        """
        Processes all files from source.

        Returns:
            List of processing results with metadata
        """
        results = []
        processed_count = 0
        error_count = 0

        logger.info("Gathering list of files from source...")

        # 1. Load ALL files into a list first so we know the total count
        all_files = self.get_file_list()
        total_files = len(all_files)

        logger.info(f"Found {total_files} files. Starting processing pipeline...")

        # 2. Loop through the list
        for idx, file_key in enumerate(all_files, 1):
            logger.info(f"Processing file {idx}/{total_files}: {file_key}")

            try:
                result = self.process_single_file(file_key)

                # Ensure result is not None
                if result is None:
                    logger.error(f"process_single_file returned None for {file_key}")
                    result = {
                        "file_key": file_key,
                        "status": "error",
                        "error": "Processing returned None - internal error"
                    }

                # Validate result structure
                if not isinstance(result, dict):
                    logger.error(f"process_single_file returned non-dict for {file_key}: {type(result)}")
                    result = {
                        "file_key": file_key,
                        "status": "error",
                        "error": f"Processing returned invalid type: {type(result)}"
                    }

                # Ensure required fields exist
                if "status" not in result:
                    logger.error(f"Result missing 'status' field for {file_key}")
                    result["status"] = "error"
                    result["error"] = "Missing status field in result"

                if "file_key" not in result:
                    result["file_key"] = file_key

                # Validate result using Pydantic (optional - don't fail if validation fails)
                try:
                    validated_result = ProcessingResult(**result)
                    results.append(validated_result.model_dump())
                except Exception as validation_error:
                    logger.debug(f"Result validation warning for {file_key}: {validation_error}")
                    # Add the original result anyway
                    results.append(result)

                # Count successes and errors
                if result.get("status") == "success":
                    processed_count += 1
                    logger.info(f"Successfully processed {file_key}")
                else:
                    error_count += 1
                    logger.warning(f"✗ Failed to process {file_key}: {result.get('error', 'Unknown error')}")

            except Exception as e:
                logger.error(f"Unexpected error processing {file_key}: {e}", exc_info=True)
                error_result = {
                    "file_key": file_key,
                    "status": "error",
                    "error": f"Unexpected exception: {str(e)}"
                }
                results.append(error_result)
                error_count += 1

        logger.info(
            f"Pipeline completed. Success: {processed_count}, Errors: {error_count}, Total: {total_files}"
        )

        return results

    def process_single_file(self, file_key: str) -> Dict[str, Any]:
        """
        Processes a single file through the complete pipeline.

        Pipeline steps:
            1. Load raw data
            2. Select parser
            3. Parse to Markdown
            4. Save Markdown with metadata

        Args:
            file_key: File key/path to process

        Returns:
            Dict with processing results and metadata (ALWAYS returns a dict, never None)
        """
        # Validate file key
        try:
            FileKeyValidator(file_key=file_key)
        except Exception as e:
            logger.error(f"Invalid file key {file_key}: {e}")
            return {
                "file_key": file_key,
                "status": "error",
                "error": f"Invalid file key: {str(e)}"
            }

        logger.debug(f"Processing file: {file_key}")

        try:
            # STEP 1: Load raw data
            logger.debug(f"Step 1: Loading raw data for {file_key}")
            raw_data = self.loader.load_raw_data(file_key)

            if not raw_data:
                logger.warning(f"No data loaded for {file_key}")
                return {
                    "file_key": file_key,
                    "status": "empty",
                    "error": "No data loaded from source"
                }

            # STEP 2: Select parser
            logger.debug(f"Step 2: Selecting parser for {file_key}")
            parser = self.parser_selector.get_parser(file_key)

            if not parser:
                logger.error(f"No parser available for {file_key}")
                return {
                    "file_key": file_key,
                    "status": "error",
                    "error": "No suitable parser found for file type"
                }

            # STEP 3: Parse to Markdown
            logger.debug(f"Step 3: Parsing {file_key} to Markdown")
            documents = self._parse_to_markdown(file_key, raw_data, parser)

            if not documents:
                logger.warning(f"No documents generated for {file_key}")
                return {
                    "file_key": file_key,
                    "status": "empty",
                    "error": "No documents generated after parsing"
                }

            # STEP 4: Save Markdown with metadata
            logger.debug(f"Step 4: Saving Markdown and building metadata for {file_key}")

            try:
                metadata = self._save_and_build_metadata(file_key, documents)

                if metadata is None:
                    logger.error(f"Metadata builder returned None for {file_key}")
                    metadata = {}

                # Validate metadata structure (informational only)
                logger.debug(f"Metadata keys for {file_key}: {list(metadata.keys()) if metadata else 'None'}")

                if FlexibleMetadata.validate_metadata(metadata):
                    logger.debug(f"Metadata validation passed for {file_key}")

            except Exception as meta_error:
                logger.error(f"Error building metadata for {file_key}: {meta_error}", exc_info=True)
                metadata = {"error": str(meta_error)}

            logger.info(f"Successfully processed {file_key}: {len(documents)} documents")

            # ALWAYS return a valid dict
            return {
                "file_key": file_key,
                "status": "success",
                "document_count": len(documents),
                "metadata": metadata,
                "documents": documents,
            }

        except Exception as e:
            logger.error(f"Failed to process {file_key}: {e}", exc_info=True)
            # ALWAYS return a valid dict, even on error
            return {
                "file_key": file_key,
                "status": "error",
                "error": str(e)
            }

    def _parse_to_markdown(
            self,
            file_key: str,
            raw_data: bytes,
            parser
    ) -> List[Document]:
        """
        Step 3: Parse raw data to Markdown documents.

        Args:
            file_key: File key/path
            raw_data: Raw file bytes
            parser: Selected parser instance

        Returns:
            List of Document objects with Markdown content
        """
        ext = os.path.splitext(file_key)[1].lower()

        # Some parsers need BytesIO wrapper, others work with raw bytes
        if self.parser_selector.needs_bytes_io(file_key):
            data_source = io.BytesIO(raw_data)
        else:
            data_source = raw_data

        # Parse file
        documents = parser.parse(data_source, ext=ext)

        return documents

    def _save_and_build_metadata(
            self,
            file_key: str,
            documents: List[Document]
    ) -> Dict[str, Any]:
        """
        Step 4: Save Markdown and build complete metadata.

        Args:
            file_key: Source file key/path
            documents: Parsed documents

        Returns:
            Complete metadata dictionary
        """
        try:
            # Combine documents into single markdown string
            markdown_content = self.metadata_builder.combine_documents_to_markdown(documents)

            # Save markdown
            markdown_key = self.saver.save_markdown(file_key, markdown_content)
            markdown_url = self.saver.get_markdown_url(markdown_key)

            # Extract domain
            domain = self.loader.extract_domain(file_key)

            # Build source URL
            source_url = self._build_source_url(file_key)

            # Build complete metadata
            metadata = self.metadata_builder.build_file_metadata(
                file_key=file_key,
                domain=domain,
                source_url=source_url,
                storage_type=self.source_type,
                markdown_path=markdown_key,
                markdown_url=markdown_url,
            )

            # Save metadata
            metadata_key = self.saver.save_metadata(file_key, metadata)
            logger.info(f"Metadata saved to: {metadata_key}")

            # Enrich documents with metadata
            self.metadata_builder.enrich_documents(documents, metadata)

            # ALWAYS return metadata dict
            return metadata if metadata is not None else {}

        except Exception as e:
            logger.error(f"Error in _save_and_build_metadata for {file_key}: {e}", exc_info=True)
            # Return minimal metadata on error
            return {
                "file_key": file_key,
                "error": str(e),
                "status": "metadata_build_failed"
            }

    def _build_source_url(self, file_key: str) -> str:
        """Builds source URL based on source type."""
        if self.source_type == "s3":
            bucket_name = self.loader.bucket_name
            return f"s3://{bucket_name}/{file_key}"
        else:
            return f"file://{file_key}"

    def get_file_list(self) -> List[str]:
        """
        Returns list of all files to process.

        Returns:
            List of file keys/paths
        """
        return list(self.loader.list_files())


# --- ENTRY POINT ---
if __name__ == "__main__":

    settings = get_settings()

    # 1. Fetch core configuration from the settings object
    source_type = settings.get("source-type")

    if not source_type:
        print("ERROR: Key 'source-type' not found in settings.")
        sys.exit(1)

    dest_type = settings.get("dest-type")
    debug_mode = settings.get("debug", False)

    # 2. Map the settings keys to the parameter names expected by the MarkDownConverter class
    raw_config = {
        "bucket_name": settings.get("bucket"),
        "prefix": settings.get("prefix"),
        "output_bucket": settings.get("out-bucket"),
        "directory": settings.get("dir"),
        "output_directory": settings.get("out-dir"),
    }

    # Clean the dictionary from None values so the default fallback logic inside the converter works properly
    config = {k: v for k, v in raw_config.items() if v is not None}

    # 3. Setup Logging
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # 4. Initialize and run the pipeline
    try:
        converter = MarkDownConverter(
            source_type=source_type,
            destination_type=dest_type,
            **config
        )

        # process_all_files will return the results
        results = converter.process_all_files()

        # Generate final statistics
        successes = sum(1 for r in results if r.get("status") == "success")
        errors = sum(1 for r in results if r.get("status") == "error")
        empties = sum(1 for r in results if r.get("status") == "empty")

        print(f"\n{'=' * 60}")
        print(f"PROCESSING COMPLETE")
        print(f"{'=' * 60}")
        print(f"Total files:     {len(results)}")
        print(f"Successful:      {successes}")
        print(f"Errors:          {errors}")
        print(f"Empty:           {empties}")
        print(f"{'=' * 60}\n")

        if errors > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)