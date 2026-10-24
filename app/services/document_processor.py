"""Document processor for DocuMind AI.

Extracts text from PDF and TXT documents downloaded from Amazon S3.
Splits text into coherent passages while strictly preserving source metadata
(filename, S3 key, page number).
"""

import io
import logging
from typing import List, Dict, Any, Optional
import pymupdf  # Official modern PyMuPDF import

logger = logging.getLogger("documind.document_processor")


class DocumentProcessingError(Exception):
    """Raised when document extraction fails due to corruption or format issues."""
    pass


class DocumentProcessor:
    """Extracts and chunks documents while maintaining page-level source attribution."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 60):
        """
        Args:
            chunk_size: Approximate number of words per passage.
            chunk_overlap: Number of overlapping words between consecutive passages.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_document(
        self,
        file_bytes: bytes,
        filename: str,
        s3_key: str,
        extension: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Extract text from bytes and chunk into indexed passages with page metadata.
        
        Returns:
            List of passage dicts:
            [{
                "passage_id": str,
                "filename": str,
                "s3_key": str,
                "page_number": Optional[int],
                "text": str,
                "word_count": int
            }]
        """
        if not file_bytes:
            logger.warning("Empty byte stream received for %s", filename)
            return []

        ext = (extension or filename.split(".")[-1]).lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        if ext == ".pdf":
            return self._process_pdf(file_bytes, filename, s3_key)
        elif ext == ".txt":
            return self._process_txt(file_bytes, filename, s3_key)
        else:
            raise DocumentProcessingError(f"Unsupported file format '{ext}'. Only PDF and TXT are supported.")

    def _process_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        s3_key: str
    ) -> List[Dict[str, Any]]:
        """Extract text page-by-page from PDF using PyMuPDF and segment into passages."""
        passages: List[Dict[str, Any]] = []

        try:
            # Open PDF from in-memory bytes stream
            with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                if doc.page_count == 0:
                    logger.warning("PDF %s contains 0 pages.", filename)
                    return []

                for page_idx in range(doc.page_count):
                    page = doc.load_page(page_idx)
                    page_number = page_idx + 1  # 1-indexed for human readability
                    page_text = page.get_text("text").strip()

                    if not page_text:
                        continue

                    # Chunk page text into passages
                    page_chunks = self._chunk_text(page_text)
                    for chunk_idx, chunk_text in enumerate(page_chunks):
                        passages.append({
                            "passage_id": f"{filename}#p{page_number}_c{chunk_idx+1}",
                            "filename": filename,
                            "s3_key": s3_key,
                            "page_number": page_number,
                            "text": chunk_text,
                            "word_count": len(chunk_text.split()),
                        })

                if doc.page_count > 0 and len(passages) == 0:
                    raise DocumentProcessingError(
                        f"PDF '{filename}' contains {doc.page_count} page(s), but has no selectable text. "
                        "The document appears to consist of scanned images or photos (OCR is not supported)."
                    )

        except DocumentProcessingError:
            raise
        except Exception as e:
            raise DocumentProcessingError(f"Failed to parse PDF document '{filename}': {str(e)}")

        return passages

    def _process_txt(
        self,
        file_bytes: bytes,
        filename: str,
        s3_key: str
    ) -> List[Dict[str, Any]]:
        """Extract plain text from bytes with encoding fallbacks and chunk."""
        text = ""
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                text = file_bytes.decode(encoding).strip()
                break
            except UnicodeDecodeError:
                continue

        if not text:
            logger.warning("TXT file %s was empty or could not be decoded.", filename)
            return []

        chunks = self._chunk_text(text)
        passages = []
        for idx, chunk_text in enumerate(chunks):
            passages.append({
                "passage_id": f"{filename}#c{idx+1}",
                "filename": filename,
                "s3_key": s3_key,
                "page_number": None,  # TXT does not have physical pages
                "text": chunk_text,
                "word_count": len(chunk_text.split()),
            })

        return passages

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into passages bounded by word count with sliding overlap.
        Preserves paragraph and sentence boundaries wherever feasible.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        if not paragraphs:
            return []

        chunks: List[str] = []
        current_words: List[str] = []

        for para in paragraphs:
            para_words = para.split()
            if not para_words:
                continue

            if len(current_words) + len(para_words) <= self.chunk_size:
                current_words.extend(para_words)
            else:
                if current_words:
                    chunks.append(" ".join(current_words))
                    # Retain overlap from end of current chunk
                    overlap_words = current_words[-self.chunk_overlap:] if self.chunk_overlap < len(current_words) else []
                    current_words = list(overlap_words)

                # If single paragraph is larger than chunk_size, split by word slices
                if len(para_words) > self.chunk_size:
                    for i in range(0, len(para_words), self.chunk_size - self.chunk_overlap):
                        slice_words = para_words[i : i + self.chunk_size]
                        if slice_words:
                            chunks.append(" ".join(slice_words))
                    current_words = []
                else:
                    current_words.extend(para_words)

        if current_words:
            chunks.append(" ".join(current_words))

        return chunks
