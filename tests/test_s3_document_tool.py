"""Tests for the Amazon S3 Document Retrieval Tool."""

import pytest
import boto3
from moto import mock_aws

from app.config import AppConfig
from app.services.s3_service import S3Service
from app.tools.s3_document_tool import S3DocumentRetrievalTool, TOOL_NAME, TOOL_SCHEMA

TEST_REGION = "us-east-1"
TEST_BUCKET = "tool-test-bucket"
TEST_PREFIX = "documents/"


@pytest.fixture
def mock_tool_environment():
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)

        # Upload a test plain text policy
        policy_text = (
            "Aura Cloud Technologies Leave Policy:\n"
            "Full-time employees receive 28 days of annual paid vacation leave.\n"
            "Unused leave carryover is limited to 5 days."
        ).encode("utf-8")
        client.put_object(
            Bucket=TEST_BUCKET,
            Key=f"{TEST_PREFIX}leave_policy.txt",
            Body=policy_text,
            ContentType="text/plain",
        )

        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name=TEST_BUCKET,
            s3_document_prefix=TEST_PREFIX,
        )
        s3_service = S3Service(config=config, client=client)
        tool = S3DocumentRetrievalTool(config=config, s3_service=s3_service)
        yield tool, client


def test_tool_schema_definition(mock_tool_environment):
    tool, _ = mock_tool_environment
    schema = tool.get_tool_definition()
    assert schema["name"] == TOOL_NAME
    assert "parameters" in schema
    assert "query" in schema["parameters"]["properties"]
    assert "query" in schema["parameters"]["required"]

    bedrock_spec = tool.get_bedrock_tool_spec()
    assert "toolSpec" in bedrock_spec
    assert bedrock_spec["toolSpec"]["name"] == TOOL_NAME


def test_tool_execution_success(mock_tool_environment):
    tool, _ = mock_tool_environment
    result = tool.execute(query="How many annual leave days are provided?")

    assert result["success"] is True
    assert result["error"] is None
    assert len(result["results"]) > 0
    
    top_hit = result["results"][0]
    assert top_hit["filename"] == "leave_policy.txt"
    assert "28 days" in top_hit["excerpt"]
    assert "leave_policy.txt" in result["documents_searched"]


def test_tool_execution_empty_query(mock_tool_environment):
    tool, _ = mock_tool_environment
    result = tool.execute(query="")
    assert result["success"] is False
    assert "cannot be empty" in result["error"]


def test_tool_execution_empty_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket="empty-bucket-123")
        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name="empty-bucket-123",
            s3_document_prefix="documents/",
        )
        s3_service = S3Service(config=config, client=client)
        tool = S3DocumentRetrievalTool(config=config, s3_service=s3_service)

        result = tool.execute(query="Any policy?")
        assert result["success"] is True
        assert len(result["results"]) == 0
        assert "No supported documents found" in result.get("message", "")
