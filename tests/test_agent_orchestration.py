"""Tests for Agent Orchestration, Original Agent vs Enhanced Agent, and Tool Invocations."""

import pytest
import boto3
from moto import mock_aws
from typing import List, Dict, Any, Optional

from app.config import AppConfig
from app.services.s3_service import S3Service
from app.services.llm_service import BaseLLMAdapter, SYSTEM_PROMPT
from app.tools.s3_document_tool import S3DocumentRetrievalTool, TOOL_NAME
from app.agent.original_agent import OriginalAgent
from app.agent.enhanced_agent import EnhancedAgent
from app.agent.orchestrator import AgentOrchestrator

TEST_REGION = "us-east-1"
TEST_BUCKET = "orch-test-bucket"


class MockLLMAdapter(BaseLLMAdapter):
    """Deterministic LLM adapter for testing agent workflows without network calls."""

    def __init__(self):
        self.last_prompt = None
        self.tool_invoked = False

    def generate_direct_response(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        self.last_prompt = prompt
        # Simulate baseline agent honoring system prompt instructions:
        # Explains lack of access to private document repository
        if "leave" in prompt.lower() or "internal" in prompt.lower() or "policy" in prompt.lower():
            return "I do not have access to your organization's internal document repository or S3 storage."
        return "I am an AI assistant answering from general training knowledge."

    def generate_grounded_response(
        self,
        query: str,
        evidence: List[Dict[str, Any]],
        system_prompt: str = SYSTEM_PROMPT,
    ) -> str:
        if not evidence:
            return "The retrieved documents do not provide sufficient information to answer this question."
        top_ev = evidence[0]
        return f"According to {top_ev['filename']}, the policy specifies: {top_ev['excerpt']}"

    def run_tool_use_cycle(
        self,
        query: str,
        tool: S3DocumentRetrievalTool,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.tool_invoked = True
        tool_result = tool.execute(query=query)
        tool_details = {
            "tool_name": TOOL_NAME,
            "tool_input": {"query": query},
            "tool_result": tool_result,
        }
        answer = self.generate_grounded_response(query, tool_result.get("results", []), system_prompt)
        return answer, tool_details


@pytest.fixture
def agent_test_env():
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)

        # Upload a fictional policy document
        text = (
            "Aura Cloud Technologies Leave Policy:\n"
            "Full-time regular employees receive 28 days of annual paid vacation leave.\n"
        ).encode("utf-8")
        client.put_object(
            Bucket=TEST_BUCKET,
            Key="documents/fictional_leave_policy.txt",
            Body=text,
            ContentType="text/plain",
        )

        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name=TEST_BUCKET,
            s3_document_prefix="documents/",
        )
        s3_service = S3Service(config=config, client=client)
        tool = S3DocumentRetrievalTool(config=config, s3_service=s3_service)
        mock_adapter = MockLLMAdapter()

        original_agent = OriginalAgent(config=config, llm_adapter=mock_adapter)
        enhanced_agent = EnhancedAgent(config=config, tool=tool, llm_adapter=mock_adapter)

        yield original_agent, enhanced_agent, mock_adapter


def test_original_agent_lacks_s3_tool(agent_test_env):
    original_agent, _, _ = agent_test_env
    question = "How many days of annual leave does the company provide?"
    
    result = original_agent.answer_question(question)
    assert result["agent_mode"] == "original"
    assert "Original Agent — S3 Tool Not Enabled" in result["mode_label"]
    assert result["tool_invoked"] is None
    assert result["evidence"] == []
    # Must explain lack of document repository access
    assert "do not have access" in result["answer"].lower() or "cannot access" in result["answer"].lower()


def test_enhanced_agent_invokes_s3_tool_and_grounds_answer(agent_test_env):
    _, enhanced_agent, mock_adapter = agent_test_env
    question = "How many days of annual leave does the company provide?"
    
    result = enhanced_agent.answer_question(question)
    assert result["agent_mode"] == "enhanced"
    assert "Enhanced Agent — Amazon S3 Retrieval Enabled" in result["mode_label"]
    assert result["tool_invoked"] == "search_s3_documents"
    assert mock_adapter.tool_invoked is True

    # Evidence must be present
    assert len(result["evidence"]) > 0
    top_ev = result["evidence"][0]
    assert top_ev["filename"] == "fictional_leave_policy.txt"
    assert "28 days" in top_ev["excerpt"]

    # Answer must cite evidence
    assert "fictional_leave_policy.txt" in result["answer"]
    assert "28 days" in result["answer"]


def test_compare_modes_execution():
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(Bucket=TEST_BUCKET)
        client.put_object(
            Bucket=TEST_BUCKET,
            Key="documents/handbook.txt",
            Body=b"Nexus Robotics Interns: Monthly stipend is $5,200.",
            ContentType="text/plain",
        )
        config = AppConfig(
            aws_region=TEST_REGION,
            s3_bucket_name=TEST_BUCKET,
            s3_document_prefix="documents/",
        )
        s3_service = S3Service(config=config, client=client)
        tool = S3DocumentRetrievalTool(config=config, s3_service=s3_service)
        mock_adapter = MockLLMAdapter()

        orchestrator = AgentOrchestrator(config=config)
        # Inject mock adapter and tool
        orchestrator.llm_adapter = mock_adapter
        orchestrator.tool = tool
        orchestrator.original_agent = OriginalAgent(config=config, llm_adapter=mock_adapter)
        orchestrator.enhanced_agent = EnhancedAgent(config=config, tool=tool, llm_adapter=mock_adapter)

        comparison = orchestrator.compare_modes("What is the monthly stipend for robotics interns?")
        
        assert "original" in comparison
        assert "enhanced" in comparison
        assert comparison["original"]["tool_invoked"] is None
        assert comparison["enhanced"]["tool_invoked"] == "search_s3_documents"
        assert len(comparison["enhanced"]["evidence"]) > 0


def test_no_relevant_evidence_handled_without_fabrication(agent_test_env):
    _, enhanced_agent, _ = agent_test_env
    # Completely unrelated question to leave policies
    result = enhanced_agent.answer_question("What is the nuclear fission reaction cross section of uranium 235?")
    assert result["agent_mode"] == "enhanced"
    assert result["tool_invoked"] == "search_s3_documents"
    assert len(result["evidence"]) == 0
    # Must report that documents do not provide sufficient information
    assert "not contain" in result["answer"].lower() or "not provide sufficient" in result["answer"].lower()


def test_llm_failure_handled_without_fabrication():
    from app.services.llm_service import BaseLLMAdapter, LLMServiceError

    class FailingLLMAdapter(BaseLLMAdapter):
        def generate_direct_response(self, prompt, system_prompt=None, history=None):
            raise LLMServiceError("Simulated AWS Bedrock ThrottlingException")
        def generate_grounded_response(self, query, evidence, system_prompt=None):
            raise LLMServiceError("Simulated AWS Bedrock ThrottlingException")
        def run_tool_use_cycle(self, query, tool, system_prompt=None):
            raise LLMServiceError("Simulated AWS Bedrock ThrottlingException")

    config = AppConfig(s3_bucket_name="any-bucket")
    failing_adapter = FailingLLMAdapter()
    agent = EnhancedAgent(config=config, llm_adapter=failing_adapter)

    result = agent.answer_question("Any question?")
    assert result["success"] is False
    assert "Simulated AWS Bedrock ThrottlingException" in result["answer"]
    assert result["error"] is not None
