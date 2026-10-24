"""CLI utility to upload sample test documents to the configured Amazon S3 bucket.

Usage:
    python scripts/upload_sample_documents.py [--dir sample_documents] [--prefix documents/]
"""

import os
import sys
import argparse
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_config
from app.services.s3_service import S3Service, S3ServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("upload_sample_documents")


def upload_sample_documents(sample_dir: str = "sample_documents", prefix: str = "documents/"):
    config = get_config()

    print("\n" + "=" * 65)
    print("  DocuMind AI — S3 Document Ingestion Utility")
    print("=" * 65)
    print(f"Target AWS Region : {config.aws_region}")
    print(f"Target S3 Bucket  : {config.s3_bucket_name or '[MISSING - Set S3_BUCKET_NAME]'}")
    print(f"Target Key Prefix : {prefix}")
    print(f"Source Directory  : {sample_dir}")
    print("=" * 65 + "\n")

    if not config.s3_bucket_name:
        print("[ERROR] S3_BUCKET_NAME is not set in environment or .env file.")
        print("Please configure your bucket name before uploading documents.")
        sys.exit(1)

    s3_service = S3Service(config)
    is_connected, msg = s3_service.check_s3_connection()
    if not is_connected:
        print(f"[AWS CONNECTION FAILED]\n{msg}\n")
        print("Troubleshooting:")
        print("1. Ensure AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY are valid.")
        print("2. Verify that the bucket exists and your IAM identity has s3:PutObject and s3:ListBucket permissions.")
        sys.exit(1)

    if not os.path.exists(sample_dir):
        print(f"[ERROR] Source directory '{sample_dir}' does not exist.")
        sys.exit(1)

    files_to_upload = [
        f for f in os.listdir(sample_dir)
        if os.path.isfile(os.path.join(sample_dir, f)) and not f.startswith(".")
    ]

    if not files_to_upload:
        print(f"[WARNING] No files found in '{sample_dir}'.")
        sys.exit(0)

    success_count = 0
    failure_count = 0

    clean_prefix = prefix.strip("/")
    if clean_prefix:
        clean_prefix += "/"

    for filename in sorted(files_to_upload):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in config.allowed_extensions:
            print(f"[SKIP] '{filename}' has unsupported extension '{ext}'. Allowed: {config.allowed_extensions}")
            continue

        file_path = os.path.join(sample_dir, filename)
        file_size = os.path.getsize(file_path)

        if file_size > config.max_document_size_bytes:
            print(f"[FAIL] '{filename}' ({file_size / (1024*1024):.2f} MB) exceeds max limit of {config.max_document_size_mb} MB.")
            failure_count += 1
            continue

        target_key = f"{clean_prefix}{filename}"
        content_type = "application/pdf" if ext == ".pdf" else "text/plain"

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            s3_service.upload_document(
                file_bytes=data,
                key=target_key,
                content_type=content_type,
            )
            print(f"[SUCCESS] Uploaded '{filename}' -> s3://{config.s3_bucket_name}/{target_key} ({file_size} bytes)")
            success_count += 1
        except S3ServiceError as e:
            print(f"[FAIL] Could not upload '{filename}': {str(e)}")
            failure_count += 1
        except Exception as e:
            print(f"[FAIL] Unexpected error uploading '{filename}': {str(e)}")
            failure_count += 1

    print("\n" + "-" * 65)
    print(f"Upload Complete: {success_count} succeeded, {failure_count} failed.")
    print("-" * 65 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload sample documents to configured S3 bucket.")
    parser.add_argument("--dir", default="sample_documents", help="Local directory containing sample docs.")
    parser.add_argument("--prefix", default="documents/", help="Target S3 key prefix.")
    args = parser.parse_args()

    upload_sample_documents(sample_dir=args.dir, prefix=args.prefix)
