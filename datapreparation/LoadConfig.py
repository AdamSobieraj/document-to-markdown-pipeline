import os
import sys
import yaml
import logging
import argparse
from typing import Any, Dict
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ConfigLoader")
load_dotenv()


class Config:
    """Singleton storing the application configuration."""
    _instance = None
    _data: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _determine_profile(self) -> str:
        """
        Determines the profile in the following order:
        1. Command line argument (--prof / --profile)
        2. Environment variable (APP_PROFILE)
        3. Default ('default')
        """
        # 1. Parse arguments (using parse_known_args to avoid conflicts with the rest of the app)
        parser = argparse.ArgumentParser(add_help=False)  # add_help=False to avoid taking over the -h flag
        parser.add_argument("--prof", "--profile", dest="profile", type=str, help="Configuration profile name")

        # Get arguments, ignoring unknown ones (so the main app can have its own flags)
        args, _ = parser.parse_known_args()

        if args.profile:
            logger.info(f"Detected profile from CLI arguments: {args.profile}")
            return args.profile

        # 2. Check environment variable
        env_profile = os.getenv("APP_PROFILE")
        if env_profile:
            logger.info(f"Detected profile from environment variable: {env_profile}")
            return env_profile

        # 3. Default
        return "default"

    def _load_config(self):
        """Loads configuration: default.yaml + {profile}.yaml + ENV overrides + CLI overrides."""

        # 1. Determine paths
        base_dir = os.path.dirname(os.path.abspath(__file__))  # business_agent/
        project_root = os.path.dirname(base_dir)  # Project root
        config_dir = os.path.join(project_root, "datapreparation/config")

        # 2. Determine profile
        profile = self._determine_profile()
        logger.info(f"Loading configuration for profile: {profile}")

        # 3. Load DEFAULT
        default_path = os.path.join(config_dir, "default.yaml")
        self._data = self._load_yaml(default_path)

        # 4. Load PROFILE specific (overrides)
        if profile != "default":
            profile_path = os.path.join(config_dir, f"{profile}.yaml")
            profile_data = self._load_yaml(profile_path)
            self._merge_dicts(self._data, profile_data)

        # 5. Override from environment variables (optional, for Docker/K8s)
        self._apply_env_overrides()

        # 6. Override from CLI arguments (HIGHEST PRIORITY)
        self._apply_cli_overrides()

        logger.info("Configuration loaded successfully.")

    def _apply_cli_overrides(self):
        """Extracts CLI parameters that override YAML/ENV configuration."""
        parser = argparse.ArgumentParser(add_help=False)

        # Registering CLI arguments relevant to the new YAML structure
        parser.add_argument("--source-type", type=str, help="Overrides source-type (e.g., s3, local)")
        parser.add_argument("--dest-type", type=str, help="Overrides dest-type (e.g., s3, local)")
        parser.add_argument("--bucket", type=str, help="Overrides S3 Bucket name")
        parser.add_argument("--out-bucket", type=str, help="Overrides S3 Output Bucket name")
        parser.add_argument("--dir", type=str, help="Overrides local input directory")
        parser.add_argument("--out-dir", type=str, help="Overrides local output directory")

        # Use parse_known_args to ignore other flags provided by the user
        args, _ = parser.parse_known_args()

        # Apply overrides to the flat dictionary structure
        if args.source_type:
            logger.info(f"Detected CLI argument. Overriding: source-type = '{args.source_type}'")
            self._data["source-type"] = args.source_type

        if args.dest_type:
            logger.info(f"Detected CLI argument. Overriding: dest-type = '{args.dest_type}'")
            self._data["dest-type"] = args.dest_type

        if args.bucket:
            logger.info(f"Detected CLI argument for S3. Overriding: bucket = '{args.bucket}'")
            self._data["bucket"] = args.bucket

        if args.out_bucket:
            logger.info(f"Detected CLI argument for S3. Overriding: out-bucket = '{args.out_bucket}'")
            self._data["out-bucket"] = args.out_bucket

        if args.dir:
            logger.info(f"Detected CLI argument. Overriding: dir = '{args.dir}'")
            self._data["dir"] = args.dir

        if args.out_dir:
            logger.info(f"Detected CLI argument. Overriding: out-dir = '{args.out_dir}'")
            self._data["out-dir"] = args.out_dir

    def _load_yaml(self, path: str) -> Dict:
        if not os.path.exists(path):
            logger.warning(f"Configuration file does not exist: {path}")
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error parsing YAML {path}: {e}")
            return {}

    def _merge_dicts(self, base: Dict, override: Dict):
        """Recursive dictionary merging."""
        for k, v in override.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._merge_dicts(base[k], v)
            else:
                base[k] = v

    def _apply_env_overrides(self):
        """
        Allows overriding any key via ENV.
        Convention: APP__SECTION__KEY (double underscore is the separator)
        """
        prefix = "APP__"
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                # Remove prefix and split by __
                keys = env_key[len(prefix):].lower().split("__")

                # Navigate deep into the dictionary
                target = self._data
                for k in keys[:-1]:
                    if k not in target:
                        target[k] = {}
                    target = target[k]

                # Set the value
                target[keys[-1]] = env_val
                logger.debug(f"Overridden from ENV: {keys} = {env_val}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Retrieves a value from the configuration using dot notation.
        e.g., config.get("source-type") or config.get("nested.key")
        """
        keys = key_path.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val


# # Global instance
# settings = Config()

_settings = None

def get_settings():
    global _settings
    if _settings is None:
        _settings = Config()
    return _settings