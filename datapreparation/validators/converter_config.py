"""Converter configuration validator."""

from typing import Dict, Any, Literal
from pydantic import BaseModel, model_validator
import logging

from .s3_config import S3Config
from .local_config import LocalConfig

logger = logging.getLogger(__name__)


class ConverterConfig(BaseModel):
    """Validation model for MarkDownConverter configuration."""

    source_type: Literal["s3", "local"]
    destination_type: Literal["s3", "local"]
    config: Dict[str, Any]

    @model_validator(mode='after')
    def validate_config_params(self):
        """
        Validate that required parameters are present based on source/destination type.

        Also validates the actual config values using S3Config or LocalConfig.
        """
        # Validate SOURCE configuration
        if self.source_type == "s3":
            if "bucket_name" not in self.config:
                raise ValueError("S3 source requires 'bucket_name' parameter")

            # Validate S3 config
            s3_config = S3Config(
                bucket_name=self.config["bucket_name"],
                prefix=self.config.get("prefix", ""),
                output_bucket=self.config.get("output_bucket")
            )

            # Update config with validated values
            self.config["bucket_name"] = s3_config.bucket_name
            self.config["prefix"] = s3_config.prefix
            if s3_config.output_bucket:
                self.config["output_bucket"] = s3_config.output_bucket

        elif self.source_type == "local":
            if "directory" not in self.config:
                raise ValueError("Local source requires 'directory' parameter")

            # Validate Local config
            local_config = LocalConfig(
                directory=self.config["directory"],
                output_directory=self.config.get("output_directory")
            )

            # Update config with validated values
            self.config["directory"] = local_config.directory
            if local_config.output_directory:
                self.config["output_directory"] = local_config.output_directory

        # Validate DESTINATION configuration if different from source
        if self.destination_type != self.source_type:
            if self.destination_type == "s3":
                if "output_bucket" not in self.config and "bucket_name" not in self.config:
                    raise ValueError(
                        "S3 destination requires 'bucket_name' or 'output_bucket' parameter"
                    )

            elif self.destination_type == "local":
                if "output_directory" not in self.config and "directory" not in self.config:
                    raise ValueError(
                        "Local destination requires 'directory' or 'output_directory' parameter"
                    )

        return self