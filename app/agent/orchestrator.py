"""Agent Orchestrator for DocuMind AI.

Coordinates execution of Original and Enhanced agents and powers the
Before & After comparative evaluation for the AWS Builder Center Challenge.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from app.config import get_config, AppConfig
from app.agent.original_agent import OriginalAgent
from app.agent.enhanced_agent import EnhancedAgent
from app.tools.s3_document_tool import S3DocumentRetrievalTool
from app.services.llm_service import get_llm_adapter, BaseLLMAdapter

logger = logging.getLogger("documind.orchestrator")


class AgentOrchestrator:
    """Manages agent execution modes and before/after comparisons."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        tool: Optional[S3DocumentRetrievalTool] = None,
        llm_adapter: Optional[BaseLLMAdapter] = None,
        s3_service: Optional[Any] = None,
    ):
        self.config = config or get_config()
        self.llm_adapter = llm_adapter or get_llm_adapter(self.config)
        self.tool = tool or S3DocumentRetrievalTool(config=self.config, s3_service=s3_service)
        self.original_agent = OriginalAgent(config=self.config, llm_adapter=self.llm_adapter)
        self.enhanced_agent = EnhancedAgent(
            config=self.config,
            tool=self.tool,
            llm_adapter=self.llm_adapter,
        )

    def ask(self, query: str, mode: str = "enhanced") -> Dict[str, Any]:
        """Execute query in specified mode ('original' or 'enhanced')."""
        start_time = time.time()
        if mode == "original":
            result = self.original_agent.answer_question(query)
        else:
            result = self.enhanced_agent.answer_question(query)
        result["execution_time_seconds"] = round(time.time() - start_time, 2)
        return result

    def compare_modes(self, query: str) -> Dict[str, Any]:
        """Run identical query through BOTH Original and Enhanced agents for side-by-side evaluation."""
        original_res = self.ask(query, mode="original")
        enhanced_res = self.ask(query, mode="enhanced")

        return {
            "query": query,
            "original": original_res,
            "enhanced": enhanced_res,
        }
