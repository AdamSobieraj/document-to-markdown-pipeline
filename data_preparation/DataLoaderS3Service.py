import logging
import os
from dataclasses import dataclass
from typing import Generator

import boto3
from dotenv import load_dotenv

from LoadConfig import get_settings

logger = logging.getLogger(__name__)

load_dotenv()


@dataclass(frozen=True, slots=True)
class S3TextObject:
    text: str
    content_length: int | None = None
    content_range: str | None = None
    etag: str | None = None


class DataLoaderS3Service:
    def __init__(self):
        self.aws_key = os.getenv('S3_AKID')
        self.aws_secret = os.getenv('S3_SK')
        self.aws_region = os.getenv('AWS_REGION') or os.getenv('S3_REGION') or "eu-north-1"
        self.s3_endpoint = os.getenv('S3_ENDPOINT')
        self.s3_verify = self._resolve_s3_verify()

        if not self.aws_key or not self.aws_secret:
            raise RuntimeError("Missing AWS credentials in .env file")

        self.session = boto3.Session(
            aws_access_key_id=self.aws_key,
            aws_secret_access_key=self.aws_secret,
            region_name=self.aws_region,
        )

        client_kwargs: dict[str, object] = {'verify': self.s3_verify}
        if self.s3_endpoint:
            client_kwargs['endpoint_url'] = self.s3_endpoint

        logger.info(

            "S3Service: endpoint=%s verify=%s",
            self.s3_endpoint or "<aws-default>",
            self.s3_verify,
        )
        self.s3_client = self.session.client('s3', **client_kwargs)
        self.settings = get_settings()

    @staticmethod
    def _resolve_s3_verify() -> bool | str:
        verify_disabled = os.getenv('S3_SSL_VERIFY') or os.getenv('AWS_SSL_VERIFY')
        if verify_disabled and verify_disabled.lower() in {'0', 'false', 'no', 'off'}:
            return False

        explicit_bundle = os.getenv('S3_CA_BUNDLE') or os.getenv('AWS_CA_BUNDLE')
        if explicit_bundle:
            return DataLoaderS3Service._resolve_ca_path(explicit_bundle)

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fallback_candidates = (
            'root-ca.pem',
            'root-ca.crt',
            'ca.pem',
            'ca.crt',
        )
        for candidate in fallback_candidates:
            candidate_path = os.path.join(project_root, candidate)
            if os.path.exists(candidate_path):
                return candidate_path

        return True

    @staticmethod
    def _resolve_ca_path(path_value: str) -> str:
        normalized = os.path.expandvars(os.path.expanduser(path_value))
        if os.path.isabs(normalized):
            return normalized

        cwd_candidate = os.path.abspath(normalized)
        if os.path.exists(cwd_candidate):
            return cwd_candidate

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_candidate = os.path.join(project_root, normalized)
        if os.path.exists(project_candidate):
            return project_candidate

        return normalized

    def list_objects(self, bucket_name: str, prefix: str = "") -> Generator[str, None, None]:
        """
        Returns file keys only from the given prefix (folder).
        """
        paginator = self.s3_client.get_paginator('list_objects_v2')

        # If prefix is empty, use empty string
        prefix_arg = prefix if prefix else ""

        # Get allowed extensions from settings, or set defaults if missing
        allowed_exts = self.settings.get("chunking.allowed_extensions", [])
        if not allowed_exts:
            # Added .xsd because they were seen in logs
            allowed_exts = ['.txt', '.md', '.pdf', '.docx', '.xlsx', '.xsd', '.xml', '.json']

        ext_tuple = tuple(allowed_exts)

        # Key moment: the Prefix parameter filters files on the AWS side
        # Thanks to this, we don't fetch the list of the entire bucket
        try:
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix_arg):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']

                        # Ignore the folder itself (if AWS returns it as an object)
                        if key.endswith('/'):
                            continue

                        # Filter by extensions
                        if key.lower().endswith(ext_tuple):
                            yield key
        except Exception as e:
            logger.error(f"S3Service Error listing objects: {e}")
            raise e

    def _decode_text(self, data: bytes, *, allow_replacement: bool = False) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            if allow_replacement:
                return data.decode("utf-8", errors="replace")

            return data.decode("windows-1252")

    @staticmethod
    def _normalize_etag(etag: str | None) -> str | None:
        if not etag:
            return None
        return etag.strip('"')

    def download_text_response(
            self,
            bucket_name: str,
            object_key: str,
    ) -> S3TextObject:
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=object_key)
            data = response["Body"].read()
            return S3TextObject(
                text=self._decode_text(data),
                content_length=response.get("ContentLength"),
                etag=self._normalize_etag(response.get("ETag")),
            )
        except Exception as e:
            logger.error(f"S3Service Error downloading {object_key}: {e}")
            raise e

    def download_text(self, bucket_name: str, object_key: str) -> str:
        return self.download_text_response(bucket_name, object_key).text

    def download_text_range(
            self,
            bucket_name: str,
            object_key: str,
            start_byte: int,
            end_byte: int | None = None,
    ) -> S3TextObject:
        if start_byte < 0:
            raise ValueError("start_byte must be zero or greater.")
        if end_byte is not None and end_byte < start_byte:
            raise ValueError("end_byte must be greater than or equal to start_byte.")

        range_header = (
            f"bytes={start_byte}-"
            if end_byte is None
            else f"bytes={start_byte}-{end_byte}"
        )

        try:
            response = self.s3_client.get_object(
                Bucket=bucket_name,
                Key=object_key,
                Range=range_header,
            )
            data = response["Body"].read()
            return S3TextObject(
                text=self._decode_text(data, allow_replacement=True),
                content_length=response.get("ContentLength"),
                content_range=response.get("ContentRange"),
                etag=self._normalize_etag(response.get("ETag")),
            )
        except Exception as e:
            logger.error(
                "S3Service Error downloading %s with range %s: %s",
                object_key,
                range_header,
                e,
            )
            raise e

    def download_bytes(self, bucket_name: str, key: str) -> bytes:
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"S3 Download Error (Bytes): {e}")
            raise e

    def upload_bytes(
            self,
            bucket_name: str,
            key: str,
            data: bytes,
            content_type: str | None = None,
    ) -> None:
        """
        Uploads bytes to S3.

        Args:
            bucket_name: S3 bucket name
            key: File key (path) in S3
            data: Data in bytes format
            content_type: MIME type (default 'application/octet-stream')
        """
        try:
            put_kwargs: dict[str, object] = {
                'Bucket': bucket_name,
                'Key': key,
                'Body': data,
                'ContentLength': len(data),
            }
            if content_type:
                put_kwargs['ContentType'] = content_type

            self.s3_client.put_object(**put_kwargs)
        except Exception as e:
            logger.error("S3 Upload Error (%s): %s", key, e)
            raise e