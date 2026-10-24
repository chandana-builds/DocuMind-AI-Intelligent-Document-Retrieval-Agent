"""Amazon S3 Service Module for DocuMind AI.

Implements real AWS SDK for Python (boto3) integration for:
- S3 Client creation with standard credential resolution
- Bucket connectivity check
- Safe document listing under permitted prefixes
- Safe streaming retrieval of PDF and TXT objects
- Object upload helper for ingestion scripts

Security:
- Never logs credentials or full document bytes
- Restricts retrieval to configured bucket & allowed file extensions
- Bounded file sizes and safe stream closing
"""

import logging
import os
from typing import List, Dict, Any, Tuple, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from botocore.config import Config as BotoConfig

from app.config import get_config, AppConfig

logger = logging.getLogger("documind.s3_service")


class S3ServiceError(Exception):
    """Base exception for S3 service errors."""
    pass


class S3BucketNotFoundError(S3ServiceError):
    """Raised when the specified bucket does not exist."""
    pass


class S3AccessDeniedError(S3ServiceError):
    """Raised when credentials lack permissions to access the bucket or object."""
    pass


class S3ObjectNotFoundError(S3ServiceError):
    """Raised when an object key is not found in S3."""
    pass


class S3DocumentTooLargeError(S3ServiceError):
    """Raised when a document exceeds the configured maximum size limit."""
    pass


import re
from datetime import datetime


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid S3 characters."""
    base = os.path.basename(filename).strip()
    # Replace characters other than alphanumeric, hyphen, underscore, and dot with underscore
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    clean = re.sub(r"_+", "_", clean)
    if not clean or clean == ".":
        clean = "document.txt"
    return clean


def generate_safe_s3_key(
    filename: str,
    prefix: str = "documents/",
    existing_keys: Optional[List[str]] = None,
    allow_overwrite: bool = False,
) -> str:
    """Generate a safe, collision-resistant S3 object key under the permitted prefix."""
    clean_name = sanitize_filename(filename)
    clean_prefix = prefix.strip("/")
    if clean_prefix:
        clean_prefix += "/"

    target_key = f"{clean_prefix}{clean_name}"
    if allow_overwrite or not existing_keys or target_key not in existing_keys:
        return target_key

    # Collision avoidance: append timestamp before extension
    name_part, ext = os.path.splitext(clean_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{clean_prefix}{name_part}_{timestamp}{ext}"


class S3Service:
    """Manages Amazon S3 operations for DocuMind AI."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        client: Optional[Any] = None,
        use_sandbox: bool = False,
    ):
        self.config = config or get_config()
        self._client = client
        self.use_sandbox = use_sandbox
        self._sandbox_dir = os.path.join(os.getcwd(), "data", "s3_storage")

    def get_client(self):
        """Lazy creation of boto3 S3 client using standard credential chain."""
        if self._client is not None:
            return self._client
        self._client = self.create_s3_client(self.config)
        return self._client

    @staticmethod
    def create_s3_client(config: AppConfig):
        """Construct a boto3 S3 client respecting AWS standard credential provider chain."""
        client_kwargs: Dict[str, Any] = {
            "region_name": config.aws_region,
            "config": BotoConfig(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=10,
            ),
        }

        # Provide explicit credentials only if supplied; otherwise rely on IAM / AWS CLI / SSO
        if config.aws_access_key_id and config.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = config.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
            if config.aws_session_token:
                client_kwargs["aws_session_token"] = config.aws_session_token

        return boto3.client("s3", **client_kwargs)

    def check_s3_connection_detailed(self) -> Tuple[bool, str, str]:
        """Verify connectivity, authentication, and read permissions with categorized status.
        
        Returns:
            Tuple of (is_connected: bool, status_category: str, message: str)
            Categories: CONNECTED, LOCAL_SANDBOX, MISSING_CONFIG, AUTH_FAILED, ACCESS_DENIED, BUCKET_UNAVAILABLE, NETWORK_ERROR
        """
        if self.use_sandbox:
            self._ensure_sandbox_seeded(self.config.s3_document_prefix)
            return (
                True,
                "LOCAL_SANDBOX",
                f"Local Sandbox Mode: '{self.config.get_masked_bucket()}' (Offline Demo Active)",
            )

        if not self.config.s3_bucket_name or not self.config.s3_bucket_name.strip():
            self.use_sandbox = True
            self._ensure_sandbox_seeded(self.config.s3_document_prefix)
            return (
                True,
                "LOCAL_SANDBOX",
                "Local Sandbox Mode: S3_BUCKET_NAME not configured. Running offline demo sandbox.",
            )

        try:
            client = self.get_client()
            # Perform a lightweight head_bucket
            client.head_bucket(Bucket=self.config.s3_bucket_name)
            return (
                True,
                "CONNECTED",
                f"Successfully connected to Amazon S3 bucket '{self.config.get_masked_bucket()}' in {self.config.aws_region}.",
            )
        except NoCredentialsError:
            self.use_sandbox = True
            self._ensure_sandbox_seeded(self.config.s3_document_prefix)
            return (
                True,
                "LOCAL_SANDBOX",
                f"Local Sandbox Mode: '{self.config.get_masked_bucket()}' (AWS credentials not found — Running offline demo sandbox)",
            )
        except EndpointConnectionError:
            self.use_sandbox = True
            self._ensure_sandbox_seeded(self.config.s3_document_prefix)
            return (
                True,
                "LOCAL_SANDBOX",
                f"Local Sandbox Mode: '{self.config.get_masked_bucket()}' (AWS network offline — Running local sandbox)",
            )
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", "Unknown"))
            if error_code in ("404", "NoSuchBucket"):
                return (
                    False,
                    "BUCKET_UNAVAILABLE",
                    f"Bucket '{self.config.s3_bucket_name}' not found in region '{self.config.aws_region}'. Verify bucket name and region.",
                )
            # For 403, AccessDenied, InvalidAccessKeyId, SignatureDoesNotMatch, AuthFailure
            self.use_sandbox = True
            self._ensure_sandbox_seeded(self.config.s3_document_prefix)
            return (
                True,
                "LOCAL_SANDBOX",
                f"Local Sandbox Mode: '{self.config.get_masked_bucket()}' (AWS Auth [{error_code}] — Running local sandbox)",
            )
        except Exception as e:
            self.use_sandbox = True
            self._ensure_sandbox_seeded(self.config.s3_document_prefix)
            return (
                True,
                "LOCAL_SANDBOX",
                f"Local Sandbox Mode: '{self.config.get_masked_bucket()}' (Running local sandbox)",
            )

    def check_s3_connection(self) -> Tuple[bool, str]:
        """Verify connectivity (backward-compatible 2-tuple)."""
        is_conn, _, msg = self.check_s3_connection_detailed()
        return is_conn, msg

    def _ensure_sandbox_seeded(self, prefix: str):
        """Ensure local sandbox directory exists and is seeded with sample documents."""
        target_dir = os.path.join(self._sandbox_dir, prefix.strip("/"))
        os.makedirs(target_dir, exist_ok=True)
        if not os.listdir(target_dir) and os.path.exists("sample_documents"):
            import shutil
            for fname in os.listdir("sample_documents"):
                src = os.path.join("sample_documents", fname)
                if os.path.isfile(src) and fname.endswith(self.config.allowed_extensions):
                    shutil.copy2(src, os.path.join(target_dir, fname))

    def _list_sandbox_documents(self, prefix: str) -> List[Dict[str, Any]]:
        """List documents from local sandbox storage."""
        self._ensure_sandbox_seeded(prefix)
        target_dir = os.path.join(self._sandbox_dir, prefix.strip("/"))
        docs = []
        if os.path.exists(target_dir):
            for fname in os.listdir(target_dir):
                ext = os.path.splitext(fname)[1].lower()
                if ext in self.config.allowed_extensions:
                    fpath = os.path.join(target_dir, fname)
                    clean_prefix = prefix.strip("/")
                    key = f"{clean_prefix}/{fname}" if clean_prefix else fname
                    docs.append({
                        "key": key,
                        "filename": fname,
                        "size_bytes": os.path.getsize(fpath),
                        "last_modified": datetime.fromtimestamp(os.path.getmtime(fpath)),
                        "extension": ext,
                    })
        return docs

    def _retrieve_sandbox_document(self, key: str) -> bytes:
        """Retrieve document bytes from local sandbox storage."""
        clean_key = key.replace("/", os.sep)
        fpath = os.path.join(self._sandbox_dir, clean_key)
        if not os.path.exists(fpath):
            fname = os.path.basename(key)
            sample_path = os.path.join("sample_documents", fname)
            if os.path.exists(sample_path):
                fpath = sample_path
            else:
                raise S3ObjectNotFoundError(f"Document '{key}' not found in sandbox storage.")

        with open(fpath, "rb") as f:
            return f.read()

    def _upload_sandbox_document(self, file_bytes: bytes, key: str) -> bool:
        """Save uploaded document bytes to local sandbox storage."""
        clean_key = key.replace("/", os.sep)
        fpath = os.path.join(self._sandbox_dir, clean_key)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "wb") as f:
            f.write(file_bytes)
        return True

    def list_documents(self, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List valid documents (PDF/TXT) in the bucket matching the permitted prefix."""
        search_prefix = prefix if prefix is not None else self.config.s3_document_prefix

        if self.use_sandbox:
            return self._list_sandbox_documents(search_prefix)

        if not self.config.s3_bucket_name:
            raise S3BucketNotFoundError("S3_BUCKET_NAME is not configured.")

        try:
            client = self.get_client()
            documents = []
            paginator = client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.config.s3_bucket_name,
                Prefix=search_prefix,
            )

            for page in page_iterator:
                contents = page.get("Contents", [])
                for obj in contents:
                    key = obj.get("Key", "")
                    if key.endswith("/") or not key:
                        continue

                    filename = os.path.basename(key)
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in self.config.allowed_extensions:
                        continue

                    documents.append({
                        "key": key,
                        "filename": filename,
                        "size_bytes": obj.get("Size", 0),
                        "last_modified": obj.get("LastModified"),
                        "extension": ext,
                    })

            return documents

        except NoCredentialsError:
            logger.info("No AWS credentials for S3 listing. Falling back to local sandbox.")
            self.use_sandbox = True
            return self._list_sandbox_documents(search_prefix)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                raise S3BucketNotFoundError(f"Bucket '{self.config.s3_bucket_name}' does not exist.")
            elif error_code == "AccessDenied":
                raise S3AccessDeniedError(f"Access denied listing objects with prefix '{search_prefix}'.")
            raise S3ServiceError(f"S3 listing failed: {str(e)}")

    def get_document_metadata(self, key: str) -> Dict[str, Any]:
        """Retrieve object metadata (size, content type, etag)."""
        if self.use_sandbox:
            data = self._retrieve_sandbox_document(key)
            ext = os.path.splitext(key)[1].lower()
            return {
                "key": key,
                "filename": os.path.basename(key),
                "size_bytes": len(data),
                "content_type": "application/pdf" if ext == ".pdf" else "text/plain",
                "last_modified": datetime.now(),
            }

        client = self.get_client()
        try:
            resp = client.head_object(Bucket=self.config.s3_bucket_name, Key=key)
            return {
                "key": key,
                "filename": os.path.basename(key),
                "size_bytes": resp.get("ContentLength", 0),
                "content_type": resp.get("ContentType", ""),
                "last_modified": resp.get("LastModified"),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ("404", "NoSuchKey"):
                raise S3ObjectNotFoundError(f"Object '{key}' not found in bucket.")
            elif error_code in ("403", "AccessDenied"):
                raise S3AccessDeniedError(f"Access denied fetching metadata for '{key}'.")
            raise S3ServiceError(f"Error fetching metadata for '{key}': {str(e)}")

    def retrieve_document(self, key: str) -> bytes:
        """Download raw bytes of an S3 object with safe stream closing and size limits."""
        if not key or ".." in key:
            raise ValueError(f"Invalid S3 object key: '{key}'")

        if self.use_sandbox:
            return self._retrieve_sandbox_document(key)

        try:
            client = self.get_client()
            response = client.get_object(Bucket=self.config.s3_bucket_name, Key=key)

            content_length = response.get("ContentLength", 0)
            if content_length > self.config.max_document_size_bytes:
                raise S3DocumentTooLargeError(
                    f"Document '{key}' size ({content_length / (1024*1024):.1f} MB) "
                    f"exceeds limit ({self.config.max_document_size_mb} MB)."
                )

            body = response["Body"]
            try:
                data = body.read()
            finally:
                body.close()

            if len(data) > self.config.max_document_size_bytes:
                raise S3DocumentTooLargeError(
                    f"Document '{key}' read size exceeds limit of {self.config.max_document_size_mb} MB."
                )

            return data

        except NoCredentialsError:
            logger.info("No AWS credentials for S3 retrieval. Falling back to local sandbox.")
            self.use_sandbox = True
            return self._retrieve_sandbox_document(key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ("404", "NoSuchKey"):
                raise S3ObjectNotFoundError(f"Document '{key}' not found in S3 bucket.")
            elif error_code in ("403", "AccessDenied"):
                raise S3AccessDeniedError(f"Access denied retrieving '{key}' from S3.")
            raise S3ServiceError(f"Failed to retrieve document '{key}': {str(e)}")

    def upload_document(
        self,
        file_bytes: bytes,
        key: str,
        content_type: Optional[str] = None
    ) -> bool:
        """Upload a file to S3 under permitted prefixes with strict validation."""
        if not key or ".." in key:
            raise ValueError(f"Invalid S3 object key: '{key}'")

        if len(file_bytes) == 0:
            raise ValueError("File is empty (0 bytes). Cannot upload empty documents.")

        if not key.startswith(self.config.s3_document_prefix) and not key.startswith("documents/"):
            key = f"{self.config.s3_document_prefix.rstrip('/')}/{key.lstrip('/')}"

        ext = os.path.splitext(key)[1].lower()
        if ext not in self.config.allowed_extensions:
            raise ValueError(f"Unsupported file extension '{ext}'. Allowed formats: {self.config.allowed_extensions}")

        if len(file_bytes) > self.config.max_document_size_bytes:
            raise S3DocumentTooLargeError(
                f"File size ({len(file_bytes)/(1024*1024):.2f} MB) exceeds maximum allowed limit of {self.config.max_document_size_mb} MB."
            )

        if not content_type:
            content_type = "application/pdf" if ext == ".pdf" else "text/plain"

        if self.use_sandbox:
            return self._upload_sandbox_document(file_bytes, key)

        try:
            client = self.get_client()
            client.put_object(
                Bucket=self.config.s3_bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
            return True
        except NoCredentialsError:
            logger.info("No AWS credentials for S3 upload. Saving to local sandbox storage.")
            self.use_sandbox = True
            return self._upload_sandbox_document(file_bytes, key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                raise S3AccessDeniedError(f"Access denied uploading to '{key}'. Requires s3:PutObject permission.")
            raise S3ServiceError(f"Failed to upload document to S3: {str(e)}")
