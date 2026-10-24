"""Tests for Amazon S3 Service using moto to simulate AWS S3 without credentials."""

import pytest
import boto3
from moto import mock_aws
from botocore.exceptions import ClientError

from app.config import AppConfig
from app.services.s3_service import (
    S3Service,
    S3BucketNotFoundError,
    S3AccessDeniedError,
    S3ObjectNotFoundError,
    S3DocumentTooLargeError,
)

TEST_REGION = "us-east-1"
TEST_BUCKET = "test-documind-bucket"
TEST_PREFIX = "documents/"


@pytest.fixture
def mock_s3_env():
    """Sets up an in-memory mock S3 bucket with test documents."""
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)
        
        # Populate with sample objects
        client.put_object(
            Bucket=TEST_BUCKET,
            Key=f"{TEST_PREFIX}handbook.txt",
            Body=b"Nexus Robotics Handbook: Working hours are 40 hours per week.",
            ContentType="text/plain",
        )
        client.put_object(
            Bucket=TEST_BUCKET,
            Key=f"{TEST_PREFIX}ignored.png",
            Body=b"\x89PNG\r\n\x1a\n",
            ContentType="image/png",
        )
        client.put_object(
            Bucket=TEST_BUCKET,
            Key=f"{TEST_PREFIX}subdir/policy.pdf",
            Body=b"%PDF-1.4 test dummy content",
            ContentType="application/pdf",
        )

        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name=TEST_BUCKET,
            s3_document_prefix=TEST_PREFIX,
            max_document_size_mb=5,
        )
        service = S3Service(config=config, client=client)
        yield service, client, config


def test_check_s3_connection_success(mock_s3_env):
    service, _, _ = mock_s3_env
    is_connected, msg = service.check_s3_connection()
    assert is_connected is True
    assert "Successfully connected" in msg


def test_check_s3_connection_missing_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name="non-existent-bucket-xyz",
        )
        service = S3Service(config=config, client=client)
        is_connected, msg = service.check_s3_connection()
        assert is_connected is False
        assert "not found" in msg


def test_list_documents(mock_s3_env):
    service, _, _ = mock_s3_env
    docs = service.list_documents()
    
    # Should find handbook.txt and policy.pdf, but ignore image.png
    filenames = [d["filename"] for d in docs]
    assert "handbook.txt" in filenames
    assert "policy.pdf" in filenames
    assert "ignored.png" not in filenames

    # Verify keys
    for d in docs:
        assert d["key"].startswith(TEST_PREFIX)
        assert d["extension"] in (".pdf", ".txt")
        assert d["size_bytes"] > 0


def test_retrieve_document_success(mock_s3_env):
    service, _, _ = mock_s3_env
    data = service.retrieve_document(f"{TEST_PREFIX}handbook.txt")
    assert isinstance(data, bytes)
    assert b"Nexus Robotics Handbook" in data


def test_retrieve_document_not_found(mock_s3_env):
    service, _, _ = mock_s3_env
    with pytest.raises(S3ObjectNotFoundError):
        service.retrieve_document(f"{TEST_PREFIX}missing_document.txt")


def test_retrieve_document_too_large():
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)
        
        # Upload 2MB file but set limit to 1MB
        large_bytes = b"x" * (2 * 1024 * 1024)
        client.put_object(
            Bucket=TEST_BUCKET,
            Key=f"{TEST_PREFIX}oversized.txt",
            Body=large_bytes,
        )

        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name=TEST_BUCKET,
            s3_document_prefix=TEST_PREFIX,
            max_document_size_mb=1,
        )
        service = S3Service(config=config, client=client)

        with pytest.raises(S3DocumentTooLargeError):
            service.retrieve_document(f"{TEST_PREFIX}oversized.txt")


def test_upload_document_success(mock_s3_env):
    service, client, _ = mock_s3_env
    content = b"Fictional test leave content."
    result = service.upload_document(
        file_bytes=content,
        key=f"{TEST_PREFIX}new_policy.txt",
        content_type="text/plain",
    )
    assert result is True

    # Check that object exists in mock S3
    head = client.head_object(Bucket=TEST_BUCKET, Key=f"{TEST_PREFIX}new_policy.txt")
    assert head["ContentLength"] == len(content)


def test_upload_valid_pdf_to_s3(mock_s3_env):
    service, client, _ = mock_s3_env
    pdf_bytes = b"%PDF-1.4 sample valid pdf content for testing"
    result = service.upload_document(
        file_bytes=pdf_bytes,
        key=f"{TEST_PREFIX}uploaded_leave_policy.pdf",
        content_type="application/pdf",
    )
    assert result is True
    docs = service.list_documents()
    uploaded = [d for d in docs if d["filename"] == "uploaded_leave_policy.pdf"]
    assert len(uploaded) == 1
    assert uploaded[0]["size_bytes"] == len(pdf_bytes)


def test_upload_rejects_empty_file(mock_s3_env):
    service, _, _ = mock_s3_env
    with pytest.raises(ValueError, match="empty"):
        service.upload_document(
            file_bytes=b"",
            key=f"{TEST_PREFIX}empty.txt",
        )


def test_upload_rejects_unsupported_file_type(mock_s3_env):
    service, _, _ = mock_s3_env
    with pytest.raises(ValueError, match="Unsupported file extension"):
        service.upload_document(
            file_bytes=b"dangerous content",
            key=f"{TEST_PREFIX}script.exe",
        )


def test_upload_rejects_oversized_file(mock_s3_env):
    service, _, config = mock_s3_env
    # Limit is 5 MB, create 6 MB bytes
    oversized_bytes = b"0" * (6 * 1024 * 1024)
    with pytest.raises(S3DocumentTooLargeError):
        service.upload_document(
            file_bytes=oversized_bytes,
            key=f"{TEST_PREFIX}too_big.pdf",
        )


def test_document_list_refreshed_after_upload(mock_s3_env):
    service, _, _ = mock_s3_env
    initial_count = len(service.list_documents())
    service.upload_document(
        file_bytes=b"Updated company policies",
        key=f"{TEST_PREFIX}brand_new_policy.txt",
    )
    new_docs = service.list_documents()
    assert len(new_docs) == initial_count + 1
    assert any(d["filename"] == "brand_new_policy.txt" for d in new_docs)


def test_safe_key_generation_and_collision_avoidance():
    from app.services.s3_service import sanitize_filename, generate_safe_s3_key

    # Test sanitization
    assert sanitize_filename("../../../etc/passwd.txt") == "passwd.txt"
    assert sanitize_filename("my report (v1) #final.pdf") == "my_report_v1_final.pdf"

    # Test collision avoidance
    existing = ["documents/policy.pdf"]
    new_key = generate_safe_s3_key("policy.pdf", prefix="documents/", existing_keys=existing)
    assert new_key != "documents/policy.pdf"
    assert new_key.startswith("documents/policy_")
    assert new_key.endswith(".pdf")


def test_invalid_key_traversal(mock_s3_env):
    service, _, _ = mock_s3_env
    with pytest.raises(ValueError):
        service.retrieve_document("../etc/passwd")


def test_check_s3_connection_detailed_categories(mock_s3_env):
    service, _, _ = mock_s3_env
    is_conn, category, msg = service.check_s3_connection_detailed()
    assert is_conn is True
    assert category == "CONNECTED"
