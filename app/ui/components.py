"""UI Components and custom styling for DocuMind AI.

Implements an executive developer interface with AWS design tokens,
evidence-grounded source citation cards, and Before & After mode badges.
"""

import streamlit as st
from typing import Dict, Any, List, Optional
from app.config import mask_secret

CUSTOM_CSS = """
<style>
/* Modern typography and container polish */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* AWS Gradient accent header */
.main-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    border: 1px solid rgba(255, 153, 0, 0.25);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.25);
}

.main-title {
    color: #ffffff;
    font-size: 1.85rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.main-tagline {
    color: #94a3b8;
    font-size: 0.95rem;
    margin-top: 0.35rem;
    margin-bottom: 0;
}

.badge-aws {
    background-color: #ff9900;
    color: #111827;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.2rem 0.55rem;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: inline-block;
}

/* Mode Indicators */
.mode-pill-enhanced {
    display: inline-flex;
    align-items: center;
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.35);
    padding: 0.35rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.mode-pill-original {
    display: inline-flex;
    align-items: center;
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.35);
    padding: 0.35rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

/* Tool execution telemetries */
.tool-telemetry-box {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-left: 4px solid #ff9900;
    border-radius: 6px;
    padding: 0.65rem 0.85rem;
    font-size: 0.82rem;
    color: #cbd5e1;
    margin: 0.75rem 0;
    font-family: monospace;
}

/* Evidence Cards */
.evidence-card {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin-top: 0.65rem;
    margin-bottom: 0.65rem;
    transition: border-color 0.2s ease;
}

.evidence-card:hover {
    border-color: rgba(255, 153, 0, 0.4);
}

.evidence-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
}

.evidence-filename {
    color: #38bdf8;
    font-weight: 600;
    font-size: 0.88rem;
    text-decoration: none;
}

.evidence-page-tag {
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    font-size: 0.75rem;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    font-weight: 600;
}

.evidence-excerpt {
    color: #e2e8f0;
    font-size: 0.85rem;
    line-height: 1.5;
    background: rgba(15, 23, 42, 0.5);
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    border-left: 2px solid #38bdf8;
    margin: 0.35rem 0 0 0;
}

.evidence-score {
    color: #94a3b8;
    font-size: 0.75rem;
    margin-top: 0.35rem;
    text-align: right;
}

/* Connection Badges */
.status-badge {
    padding: 0.35rem 0.65rem;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
}
.status-badge-connected {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.4);
}
.status-badge-auth {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.4);
}
.status-badge-error {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.4);
}

.file-preview-box {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    margin: 0.35rem 0;
    font-size: 0.82rem;
    color: #cbd5e1;
}
</style>
"""


def render_header():
    """Render top brand header."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="main-header">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <h1 class="main-title">
                        DocuMind AI
                        <span class="badge-aws">S3 Document Intelligence</span>
                    </h1>
                    <p class="main-tagline">
                        An AI agent that turns stored documents into evidence-backed, verifiable answers.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_connection_status(category: str, message: str, bucket_masked: str, region: str):
    """Render standardized, informative AWS S3 connection status."""
    if category == "LOCAL_SANDBOX":
        st.markdown(
            f'<div class="status-badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4);">● Local Sandbox Active (Offline Demo)</div>',
            unsafe_allow_html=True,
        )
        st.caption("Running with local document storage & offline evidence synthesis (no AWS credentials required).")
    elif category == "CONNECTED":
        st.markdown(
            f'<div class="status-badge status-badge-connected">● Connected: <code>{bucket_masked}</code></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"✓ AWS Region: `{region}` | Verified read/list permissions.")
    elif category == "AUTH_FAILED":
        st.markdown(
            '<div class="status-badge status-badge-auth">▲ AWS Authentication Required</div>',
            unsafe_allow_html=True,
        )
        st.caption("No valid AWS credentials found in environment or `~/.aws/credentials`.")
    elif category == "MISSING_CONFIG":
        st.markdown(
            '<div class="status-badge status-badge-error">✖ S3 Bucket Unconfigured</div>',
            unsafe_allow_html=True,
        )
        st.caption("`S3_BUCKET_NAME` is missing in `.env`.")
    elif category == "ACCESS_DENIED":
        st.markdown(
            '<div class="status-badge status-badge-error">✖ S3 Access Denied (403)</div>',
            unsafe_allow_html=True,
        )
        st.caption("IAM identity lacks `s3:ListBucket` or `s3:GetObject` permission.")
    elif category == "BUCKET_UNAVAILABLE":
        st.markdown(
            '<div class="status-badge status-badge-error">✖ Bucket Not Found (404)</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Bucket does not exist in region `{region}`.")
    elif category == "NETWORK_ERROR":
        st.markdown(
            '<div class="status-badge status-badge-error">✖ AWS Network Error</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Could not reach AWS endpoint in region `{region}`.")
    else:
        st.markdown(
            f'<div class="status-badge status-badge-error">✖ Disconnected</div>',
            unsafe_allow_html=True,
        )
        st.caption(message)


def render_evidence_card(evidence: Dict[str, Any], index: int):
    """Render an individual source evidence card with page attribution."""
    filename = evidence.get("filename", "Unknown Document")
    page_number = evidence.get("page_number")
    excerpt = evidence.get("excerpt", "")
    score = evidence.get("relevance_score", 0.0)
    s3_key = evidence.get("s3_key", "")

    page_html = (
        f'<span class="evidence-page-tag">Page {page_number}</span>'
        if page_number
        else '<span class="evidence-page-tag">Text Document</span>'
    )

    st.markdown(
        f"""
        <div class="evidence-card">
            <div class="evidence-header">
                <span class="evidence-filename">📄 {filename}</span>
                {page_html}
            </div>
            <div class="evidence-excerpt">"{excerpt}"</div>
            <div class="evidence-score">
                S3 Key: <code>{s3_key}</code> &bull; Relevance Score: <strong>{score}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tool_telemetry(tool_details: Dict[str, Any]):
    """Display real agent tool invocation telemetry badge."""
    tool_name = tool_details.get("tool_name", "search_s3_documents")
    tool_input = tool_details.get("tool_input", {})
    query = tool_input.get("query", "")
    results = tool_details.get("tool_result", {}).get("results", [])
    docs_searched = tool_details.get("tool_result", {}).get("documents_searched", [])
    warnings = tool_details.get("tool_result", {}).get("document_warnings", [])

    warning_html = ""
    if warnings:
        warning_html = f"<div style='color: #f59e0b; margin-top: 0.3rem;'>⚠️ <strong>Notices:</strong> {'; '.join(warnings)}</div>"

    st.markdown(
        f"""
        <div class="tool-telemetry-box">
            <div>⚡ <strong>Tool Invocation:</strong> <code>{tool_name}</code></div>
            <div>🔍 <strong>Search Query:</strong> "{query}"</div>
            <div>📂 <strong>Documents Examined:</strong> {len(docs_searched)} ({', '.join(docs_searched) if docs_searched else 'None'})</div>
            <div>📊 <strong>Retrieved Evidence Passages:</strong> {len(results)} passage(s) matched</div>
            {warning_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
