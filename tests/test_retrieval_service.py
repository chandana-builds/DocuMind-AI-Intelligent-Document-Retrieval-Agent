"""Tests for BM25 Lexical Retrieval Service."""

import pytest
from app.services.retrieval_service import BM25Retriever


@pytest.fixture
def sample_passages():
    return [
        {
            "passage_id": "doc1#p1_c1",
            "filename": "fictional_leave_policy.pdf",
            "s3_key": "documents/fictional_leave_policy.pdf",
            "page_number": 1,
            "text": "Aura Cloud Technologies provides 28 days of fully paid annual leave to all employees.",
        },
        {
            "passage_id": "doc1#p1_c2",
            "filename": "fictional_leave_policy.pdf",
            "s3_key": "documents/fictional_leave_policy.pdf",
            "page_number": 1,
            "text": "Employees receive 10 days of medical and mental wellness sick leave each calendar year.",
        },
        {
            "passage_id": "doc2#p1_c1",
            "filename": "fictional_internship_handbook.pdf",
            "s3_key": "documents/fictional_internship_handbook.pdf",
            "page_number": 1,
            "text": "The Nexus Robotics Summer Internship runs for 12 continuous weeks with a monthly stipend of $5,200.",
        },
        {
            "passage_id": "doc3#c1",
            "filename": "fictional_reimbursement_policy.txt",
            "s3_key": "documents/fictional_reimbursement_policy.txt",
            "page_number": None,
            "text": "Domestic Travel per diem: Up to $75 per day. Itemized receipts are mandatory for expenses exceeding $25.",
        },
    ]


def test_bm25_retrieval_leave_days(sample_passages):
    retriever = BM25Retriever()
    results = retriever.rank("How many days of annual leave does the company provide?", sample_passages)

    assert len(results) > 0
    top_hit = results[0]
    assert top_hit["filename"] == "fictional_leave_policy.pdf"
    assert top_hit["page_number"] == 1
    assert "28 days" in top_hit["excerpt"]
    assert top_hit["relevance_score"] > 0


def test_bm25_retrieval_internship_stipend(sample_passages):
    retriever = BM25Retriever()
    results = retriever.rank("What is the monthly stipend for robotics interns?", sample_passages)

    assert len(results) > 0
    top_hit = results[0]
    assert top_hit["filename"] == "fictional_internship_handbook.pdf"
    assert "$5,200" in top_hit["excerpt"]


def test_bm25_retrieval_no_match(sample_passages):
    retriever = BM25Retriever()
    # Query completely unrelated to internal policies
    results = retriever.rank("quantum entanglement astrophysics telescope orbit", sample_passages)
    assert len(results) == 0


def test_bm25_empty_query_or_passages():
    retriever = BM25Retriever()
    assert retriever.rank("", []) == []
    assert retriever.rank("leave", []) == []
