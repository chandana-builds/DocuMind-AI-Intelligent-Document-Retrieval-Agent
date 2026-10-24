"""Tests for Document Processor (PDF/TXT extraction and page preservation)."""

import pytest
import pymupdf
from app.services.document_processor import DocumentProcessor, DocumentProcessingError


@pytest.fixture
def sample_pdf_bytes():
    """Create in-memory 2-page PDF using PyMuPDF."""
    doc = pymupdf.open()
    
    # Page 1
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Annual Leave Policy Page 1: Employees receive 28 days of paid vacation per year.")

    # Page 2
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Annual Leave Policy Page 2: Maximum carryover allowance is 5 days.")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_process_pdf_pages_and_metadata(sample_pdf_bytes):
    processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
    passages = processor.process_document(
        file_bytes=sample_pdf_bytes,
        filename="leave_policy.pdf",
        s3_key="documents/leave_policy.pdf",
    )

    assert len(passages) >= 2
    pages = [p["page_number"] for p in passages]
    assert 1 in pages
    assert 2 in pages

    # Verify content in page 1
    p1_passages = [p for p in passages if p["page_number"] == 1]
    assert "28 days" in p1_passages[0]["text"]
    assert p1_passages[0]["filename"] == "leave_policy.pdf"
    assert p1_passages[0]["s3_key"] == "documents/leave_policy.pdf"

    # Verify content in page 2
    p2_passages = [p for p in passages if p["page_number"] == 2]
    assert "5 days" in p2_passages[0]["text"]


def test_process_txt_extraction():
    processor = DocumentProcessor(chunk_size=50, chunk_overlap=10)
    txt_content = (
        "Zenith Reimbursement Policy.\n\n"
        "Section 1: Domestic daily meal per diem is capped at $75 per day.\n\n"
        "Section 2: Itemized receipts are mandatory for all charges exceeding $25."
    ).encode("utf-8")

    passages = processor.process_document(
        file_bytes=txt_content,
        filename="reimbursement.txt",
        s3_key="documents/reimbursement.txt",
    )

    assert len(passages) >= 1
    assert passages[0]["page_number"] is None
    assert "$75 per day" in passages[0]["text"]
    assert passages[0]["filename"] == "reimbursement.txt"


def test_process_corrupt_pdf():
    processor = DocumentProcessor()
    corrupt_bytes = b"Not a real PDF header at all random data"
    with pytest.raises(DocumentProcessingError):
        processor.process_document(
            file_bytes=corrupt_bytes,
            filename="broken.pdf",
            s3_key="documents/broken.pdf",
        )


def test_unsupported_format():
    processor = DocumentProcessor()
    with pytest.raises(DocumentProcessingError):
        processor.process_document(
            file_bytes=b"dummy",
            filename="data.xlsx",
            s3_key="documents/data.xlsx",
        )


def test_empty_bytes():
    processor = DocumentProcessor()
    passages = processor.process_document(
        file_bytes=b"",
        filename="empty.txt",
        s3_key="documents/empty.txt",
    )
    assert passages == []


def test_process_scanned_pdf_without_text():
    # Create a 1-page PDF without text (representing scanned image)
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    processor = DocumentProcessor()
    with pytest.raises(DocumentProcessingError, match="no selectable text"):
        processor.process_document(
            file_bytes=pdf_bytes,
            filename="scanned_photo.pdf",
            s3_key="documents/scanned_photo.pdf",
        )
