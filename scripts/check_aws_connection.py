"""AWS Connectivity and Permissions Diagnostic Script for DocuMind AI.

Tests:
1. Local environment configuration (.env and variables).
2. AWS Credentials resolution (IAM, Environment, Profiles).
3. Amazon S3 bucket connectivity and object listing.
4. Amazon Bedrock runtime client and model permission check.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_config, mask_secret
from app.services.s3_service import S3Service


def run_diagnostics():
    config = get_config()

    print("\n" + "=" * 70)
    print("  DocuMind AI — AWS Connectivity & Environment Diagnostics")
    print("=" * 70)

    # 1. Config overview
    print("\n[1] Configuration Overview:")
    print(f"  - AWS Region         : {config.aws_region}")
    print(f"  - S3 Bucket Name     : {config.s3_bucket_name or '[NOT SET]'}")
    print(f"  - S3 Document Prefix : {config.s3_document_prefix}")
    print(f"  - AWS Access Key ID  : {mask_secret(config.aws_access_key_id)}")
    print(f"  - LLM Provider       : {config.llm_provider}")
    print(f"  - Bedrock Model ID   : {config.bedrock_model_id}")

    # 2. STS Identity Check
    print("\n[2] AWS Identity Check (STS):")
    try:
        session = boto3.Session(
            region_name=config.aws_region,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            aws_session_token=config.aws_session_token,
        )
        sts = session.client("sts")
        caller_identity = sts.get_caller_identity()
        print(f"  [OK] Identity Validated:")
        print(f"    - Account: {caller_identity.get('Account')}")
        print(f"    - ARN    : {caller_identity.get('Arn')}")
        print(f"    - UserId : {caller_identity.get('UserId')}")
    except NoCredentialsError:
        print("  [FAIL] No AWS credentials found via environment, ~/.aws/credentials, or IAM role.")
    except Exception as e:
        print(f"  [FAIL] STS call failed: {str(e)}")

    # 3. S3 Bucket Check
    print("\n[3] Amazon S3 Bucket Connectivity:")
    if not config.s3_bucket_name:
        print("  [FAIL] S3_BUCKET_NAME is not configured in .env file.")
    else:
        s3_service = S3Service(config)
        is_conn, message = s3_service.check_s3_connection()
        if is_conn:
            print(f"  [OK] {message}")
            try:
                docs = s3_service.list_documents()
                print(f"  [OK] Document listing successful: Found {len(docs)} document(s) under '{config.s3_document_prefix}'.")
                for doc in docs:
                    print(f"    * {doc['filename']} ({doc['size_bytes']} bytes)")
            except Exception as e:
                print(f"  [WARN] Connected to bucket, but listing failed: {str(e)}")
        else:
            print(f"  [FAIL] Connection failed: {message}")

    # 4. Amazon Bedrock Check
    print("\n[4] Amazon Bedrock Access:")
    if config.llm_provider != "bedrock":
        print(f"  [INFO] LLM_PROVIDER is set to '{config.llm_provider}', skipping Bedrock test.")
    else:
        try:
            bedrock_client = session.client("bedrock", region_name=config.aws_region)
            models = bedrock_client.list_foundation_models(byOutputModality="TEXT")
            matching = [
                m["modelId"] for m in models.get("modelSummaries", [])
                if m["modelId"] == config.bedrock_model_id
            ]
            if matching:
                print(f"  [OK] Target model '{config.bedrock_model_id}' is available in region '{config.aws_region}'.")
            else:
                print(f"  [INFO] Model '{config.bedrock_model_id}' not found in standard public list for '{config.aws_region}'. Verify model ID.")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            print(f"  [WARN] Bedrock control plane query returned [{code}]: {e.response.get('Error', {}).get('Message')}")
            print("    (Note: Bedrock runtime invocation may still work if IAM allows bedrock:InvokeModel)")
        except Exception as e:
            print(f"  [WARN] Could not query Bedrock models: {str(e)}")

    print("\n" + "=" * 70)
    print("  Diagnostic Check Completed.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_diagnostics()
