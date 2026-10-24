"""Original Agent (Mode A) for DocuMind AI.

The baseline agent before being equipped with the Amazon S3 document retrieval tool.
It has NO access to the S3 bucket or internal documents.
"""

import logging
from typing import Dict, Any, List, Optional
from app.config import get_config, AppConfig
from app.services.llm_service import get_llm_adapter, BaseLLMAdapter, LLMServiceError

logger = logging.getLogger("documind.original_agent")

ORIGINAL_AGENT_PROMPT = """You are the Original AI Agent (Baseline Mode).
CRITICAL CAPABILITY RESTRICTION:
- You DO NOT have access to any external tools, file systems, or Amazon S3 storage.
- You CANNOT read internal company documents, institutional policies, student handbooks, or private PDFs.
- If the user asks a question about an internal policy, handbook, specific institutional guideline, or private document:
  State clearly that you DO NOT have access to the internal document repository, and therefore cannot answer questions specific to their internal files.
- Never invent, fabricate, or hallucinate specific policy details (such as vacation day allowances, reimbursement limits, or dates) for private organizations.
"""


class OriginalAgent:
    """Mode A: Original Agent without S3 Retrieval Tool."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        llm_adapter: Optional[BaseLLMAdapter] = None,
    ):
        self.config = config or get_config()
        self.llm_adapter = llm_adapter or get_llm_adapter(self.config)

    def answer_question(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Process user question using only baseline model knowledge without any S3 retrieval tool.
        
        Returns:
            Dict containing:
            - agent_mode: "original"
            - mode_label: "Original Agent — S3 Tool Not Enabled"
            - tool_invoked: None
            - evidence: []
            - answer: str
            - success: bool
            - error: Optional[str]
        """
        try:
            answer = self.llm_adapter.generate_direct_response(
                prompt=query,
                system_prompt=ORIGINAL_AGENT_PROMPT,
                history=history,
            )
            return {
                "agent_mode": "original",
                "mode_label": "Original Agent — S3 Tool Not Enabled",
                "tool_invoked": None,
                "evidence": [],
                "answer": answer,
                "success": True,
                "error": None,
            }
        except LLMServiceError as e:
            return {
                "agent_mode": "original",
                "mode_label": "Original Agent — S3 Tool Not Enabled",
                "tool_invoked": None,
                "evidence": [],
                "answer": f"Agent Error: {str(e)}",
                "success": False,
                "error": str(e),
            }
