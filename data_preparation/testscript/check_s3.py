import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from botocore.exceptions import ClientError

from DataLoaderS3Service import DataLoaderS3Service

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def main():
    try:
        service = DataLoaderS3Service()
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    client = service.s3_client
    bucket = service.settings.get("bucket")

    if not bucket:
        logger.error("Brak nazwy bucketa (config: bucket / CLI: --bucket)")
        sys.exit(1)

    # 1. Check connection and access to the bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        logger.error(f"Brak połączenia / brak dostępu do bucketa '{bucket}': {e}")
        sys.exit(1)

    logger.info(f"OK — połączenie z bucketem: {bucket}")

    # 2. List files
    files = []
    total_size = 0
    try:
        paginator = client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('/'):
                    continue  # folder placeholders
                files.append(obj)
                total_size += obj.get('Size', 0)
    except ClientError as e:
        logger.error(f"Błąd podczas listowania plików: {e}")
        sys.exit(1)

    print("-" * 80)
    for obj in files:
        print(f"{obj.get('Size', 0):>14,} B  {obj.get('LastModified')}  {obj['Key']}")
    print("-" * 80)
    print(f"Razem: {len(files)} plików, {total_size:,} B")


if __name__ == "__main__":
    main()
