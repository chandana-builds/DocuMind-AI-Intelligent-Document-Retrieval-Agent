"""Enhanced Agent (Mode B) for DocuMind AI.

Equipped with the Amazon S3 document retrieval tool.
Retrieves real S3 documents, extracts text passages, ranks evidence,
and generates grounded answers with transparent citations.
"""

import logging
from typing import Dict, Any, List, Optional
from app.config import get_config, AppConfig
from app.tools.s3_document_tool import S3DocumentRetrievalTool
from app.services.llm_service import get_llm_adapter, BaseLLMAdapter, LLMServiceError

logger = logging.getLogger("documind.enhanced_agent")


class EnhancedAgent:
    """Mode B: Enhanced Agent with Amazon S3 Document Retrieval Tool."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        tool: Optional[S3DocumentRetrievalTool] = None,
        llm_adapter: Optional[BaseLLMAdapter] = None,
    ):
        self.config = config or get_config()
        self.tool = tool or S3DocumentRetrievalTool(config=self.config)
        self.llm_adapter = llm_adapter or get_llm_adapter(self.config)

    def answer_question(
        self,
        query: str,
        prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process user question by invoking the Amazon S3 retrieval tool.
        
        Returns:
            Dict containing:
            - agent_mode: "enhanced"
            - mode_label: "Enhanced Agent — Amazon S3 Retrieval Enabled"
            - tool_invoked: str ("search_s3_documents")
            - tool_execution: Dict with input, result, documents searched
            - evidence: List of passage evidence dicts
            - answer: str
            - success: bool
            - error: Optional[str]
        """
        try:
            # Execute tool use cycle via the LLM adapter
            answer, tool_details = self.llm_adapter.run_tool_use_cycle(
                query=query,
                tool=self.tool,
            )

            results = []
            if tool_details and "tool_result" in tool_details:
                results = tool_details["tool_result"].get("results", [])

            return {
                "agent_mode": "enhanced",
                "mode_label": "Enhanced Agent — Amazon S3 Retrieval Enabled",
                "tool_invoked": "search_s3_documents",
                "tool_execution": tool_details,
                "evidence": results,
                "documents_searched": tool_details["tool_result"].get("documents_searched", []) if tool_details else [],
                "answer": answer,
                "success": True,
                "error": None,
            }
        except LLMServiceError as e:
            return {
                "agent_mode": "enhanced",
                "mode_label": "Enhanced Agent — Amazon S3 Retrieval Enabled",
                "tool_invoked": "search_s3_documents",
                "tool_execution": None,
                "evidence": [],
                "documents_searched": [],
                "answer": f"Agent Error: {str(e)}",
                "success": False,
                "error": str(e),
            }
