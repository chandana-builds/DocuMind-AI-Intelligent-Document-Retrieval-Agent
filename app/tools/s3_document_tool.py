"""Amazon S3 Document Retrieval Tool for DocuMind AI.

This module exposes the explicit, callable tool that the AI agent invokes
to retrieve real documents from Amazon S3, extract passages, and rank evidence.
"""

import logging
from typing import Dict, Any, List, Optional
from app.config import get_config, AppConfig
from app.services.s3_service import S3Service, S3ServiceError
from app.services.document_processor import DocumentProcessor
from app.services.retrieval_service import BM25Retriever

logger = logging.getLogger("documind.s3_document_tool")

# Standard Tool Specification (Schema)
TOOL_NAME = "search_s3_documents"
TOOL_DESCRIPTION = (
    "Search permitted documents stored in the configured Amazon S3 bucket "
    "and return relevant evidence for answering a user question."
)

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": TOOL_DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The user's natural-language question or key search terms to locate evidence for.",
            },
            "prefix": {
                "type": "string",
                "description": "Optional permitted S3 prefix for restricting the search (e.g. 'documents/').",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of relevant passages to return (default: 4).",
            },
        },
        "required": ["query"],
    },
}

BEDROCK_TOOL_SPEC = {
    "toolSpec": {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's natural-language question or key search terms.",
                    },
                    "prefix": {
                        "type": "string",
                        "description": "Optional permitted S3 prefix (e.g. 'documents/').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of relevant passages to return.",
                    },
                },
                "required": ["query"],
            }
        },
    }
}


class S3DocumentRetrievalTool:
    """The explicit tool callable by the AI Agent for S3 document retrieval."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        s3_service: Optional[S3Service] = None,
        document_processor: Optional[DocumentProcessor] = None,
        retriever: Optional[BM25Retriever] = None,
    ):
        self.config = config or get_config()
        self.s3_service = s3_service or S3Service(self.config)
        self.document_processor = document_processor or DocumentProcessor(
            chunk_size=self.config.passage_chunk_size,
            chunk_overlap=self.config.passage_chunk_overlap,
        )
        self.retriever = retriever or BM25Retriever()
        
        # Bounded session cache: {s3_key: list of passages}
        self._passage_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return generic tool schema dictionary."""
        return TOOL_SCHEMA

    def get_bedrock_tool_spec(self) -> Dict[str, Any]:
        """Return Amazon Bedrock Converse API tool specification format."""
        return BEDROCK_TOOL_SPEC

    def clear_cache(self) -> None:
        """Clear document passage cache."""
        self._passage_cache.clear()

    def execute(
        self,
        query: str,
        prefix: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute the S3 search tool workflow.
        
        Steps:
        1. Validate inputs.
        2. Enumerate permitted documents in configured S3 bucket.
        3. Retrieve document bytes via S3 get_object (using session cache to prevent redundant downloads).
        4. Extract text & preserve page numbers.
        5. Rank passages against query using BM25.
        6. Return structured evidence payload.
        """
        if not query or not query.strip():
            return {
                "success": False,
                "query": query,
                "results": [],
                "documents_searched": [],
                "error": "Query parameter cannot be empty.",
            }

        k = max_results or self.config.retrieval_top_k
        search_prefix = prefix or self.config.s3_document_prefix

        # 1. Enumerate objects in S3 bucket
        try:
            doc_items = self.s3_service.list_documents(prefix=search_prefix)
        except S3ServiceError as e:
            logger.error("Error listing S3 documents: %s", str(e))
            return {
                "success": False,
                "query": query,
                "results": [],
                "documents_searched": [],
                "error": f"Failed to access S3 bucket: {str(e)}",
            }

        if not doc_items:
            return {
                "success": True,
                "query": query,
                "results": [],
                "documents_searched": [],
                "message": f"No supported documents found in S3 bucket under prefix '{search_prefix}'.",
                "error": None,
            }

        # 2. Retrieve & process documents
        all_passages: List[Dict[str, Any]] = []
        documents_searched: List[str] = []
        document_warnings: List[str] = []

        for item in doc_items:
            key = item["key"]
            filename = item["filename"]
            documents_searched.append(filename)

            # Check bounded in-memory passage cache
            if key in self._passage_cache:
                all_passages.extend(self._passage_cache[key])
                continue

            try:
                # Real boto3 S3 get_object retrieval
                file_bytes = self.s3_service.retrieve_document(key)
                passages = self.document_processor.process_document(
                    file_bytes=file_bytes,
                    filename=filename,
                    s3_key=key,
                    extension=item.get("extension"),
                )
                self._passage_cache[key] = passages
                all_passages.extend(passages)
            except Exception as e:
                warn_msg = f"{filename}: {str(e)}"
                logger.warning("Failed to retrieve or process '%s': %s", key, str(e))
                document_warnings.append(warn_msg)
                continue

        if not all_passages:
            warning_detail = f" ({'; '.join(document_warnings)})" if document_warnings else ""
            return {
                "success": True,
                "query": query,
                "results": [],
                "documents_searched": documents_searched,
                "document_warnings": document_warnings,
                "message": f"Documents were found in S3, but no text could be extracted{warning_detail}.",
                "error": None,
            }

        # 3. Rank passages using BM25 lexical ranking
        ranked_results = self.retriever.rank(
            query=query,
            passages=all_passages,
            top_k=k,
            min_score=self.config.min_relevance_score,
        )

        return {
            "success": True,
            "query": query,
            "results": ranked_results,
            "total_passages_indexed": len(all_passages),
            "documents_searched": documents_searched,
            "document_warnings": document_warnings,
            "error": None,
        }
