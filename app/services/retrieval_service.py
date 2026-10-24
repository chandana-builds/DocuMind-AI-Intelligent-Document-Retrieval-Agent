"""Lexical retrieval service implementing BM25 ranking for DocuMind AI.

Amazon S3 is an object store, not a search engine. This service provides the
transparent, reproducible retrieval engine that ranks passages extracted from
downloaded S3 objects against user queries.
"""

import math
import re
from typing import List, Dict, Any, Tuple


class BM25Retriever:
    """Okapi BM25 lexical ranker for passage search."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Normalize and tokenize text into lowercase word tokens."""
        # Simple, robust alphanumeric regex tokenizer
        tokens = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
        # Filter standard English stopwords
        stopwords = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "is",
            "are", "was", "were", "it", "this", "that", "these", "those", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "with", "as", "by",
            "from", "about", "into", "through", "during", "before", "after", "above",
            "below", "under", "again", "further", "then", "once", "here", "there",
            "when", "where", "why", "how", "all", "any", "both", "each", "few",
            "more", "most", "other", "some", "such", "no", "nor", "not", "only",
            "own", "same", "so", "than", "too", "very", "can", "will", "just", "should",
            "now", "what", "which", "who", "whom"
        }
        return [t for t in tokens if len(t) > 1 and t not in stopwords]

    def rank(
        self,
        query: str,
        passages: List[Dict[str, Any]],
        top_k: int = 4,
        min_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Rank a collection of candidate passages against a query using Okapi BM25.
        
        Args:
            query: Natural language query string.
            passages: List of passage dicts from DocumentProcessor.
            top_k: Max number of relevant passages to return.
            min_score: Minimum score required to be considered relevant evidence.
            
        Returns:
            List of ranked passage evidence dicts with relevance scores and excerpts.
        """
        if not passages or not query.strip():
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        N = len(passages)
        corpus_tokens = [self.tokenize(p["text"]) for p in passages]
        doc_lengths = [len(toks) for toks in corpus_tokens]
        avgdl = sum(doc_lengths) / N if N > 0 else 1.0

        # Compute Document Frequencies (DF) for query tokens
        df: Dict[str, int] = {}
        for q_token in set(query_tokens):
            df[q_token] = sum(1 for toks in corpus_tokens if q_token in toks)

        # Compute IDF for query tokens
        idf: Dict[str, float] = {}
        for q_token in query_tokens:
            n_q = df.get(q_token, 0)
            # Standard BM25 IDF formulation with smoothing
            idf[q_token] = math.log(1.0 + (N - n_q + 0.5) / (n_q + 0.5))

        # Score each passage
        scored_passages: List[Tuple[float, Dict[str, Any], str]] = []
        for i, passage in enumerate(passages):
            tokens = corpus_tokens[i]
            doc_len = doc_lengths[i]
            if doc_len == 0:
                continue

            # Calculate term frequencies
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1

            score = 0.0
            matched_terms = []
            for q_token in query_tokens:
                f_qd = tf.get(q_token, 0)
                if f_qd > 0:
                    matched_terms.append(q_token)
                    numerator = f_qd * (self.k1 + 1.0)
                    denominator = f_qd + self.k1 * (1.0 - self.b + self.b * (doc_len / avgdl))
                    score += idf[q_token] * (numerator / denominator)

            # Bonus for exact phrase match
            if query.lower() in passage["text"].lower():
                score += 2.0

            if score >= min_score and matched_terms:
                excerpt = self._extract_excerpt(passage["text"], query_tokens)
                scored_passages.append((score, passage, excerpt))

        # Sort descending by score
        scored_passages.sort(key=lambda x: x[0], reverse=True)

        # Format top_k results
        results = []
        for score, passage, excerpt in scored_passages[:top_k]:
            results.append({
                "passage_id": passage.get("passage_id", ""),
                "filename": passage["filename"],
                "s3_key": passage["s3_key"],
                "page_number": passage.get("page_number"),
                "excerpt": excerpt,
                "relevance_score": round(score, 3),
                "full_text": passage["text"],
            })

        return results

    def _extract_excerpt(self, text: str, query_tokens: List[str], max_chars: int = 280) -> str:
        """Create a concise excerpt centered around the highest density of query terms."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if not sentences:
            return text[:max_chars]

        # Score sentences by query token matches
        best_sentence_idx = 0
        max_matches = -1

        for idx, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            matches = sum(1 for tok in query_tokens if tok in sentence_lower)
            if matches > max_matches:
                max_matches = matches
                best_sentence_idx = idx

        # Extract context around the best sentence
        start_idx = max(0, best_sentence_idx - 1)
        end_idx = min(len(sentences), best_sentence_idx + 2)
        excerpt_window = " ".join(sentences[start_idx:end_idx]).strip()

        if len(excerpt_window) > max_chars:
            return excerpt_window[:max_chars].rsplit(" ", 1)[0] + "..."
        return excerpt_window
