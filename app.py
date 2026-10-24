"""DocuMind AI — Main Streamlit Application.

An AI agent that retrieves documents from Amazon S3 and answers questions
using their contents with page-level evidence citations.
"""

import os
import sys
import time
from typing import List, Dict, Any
import streamlit as st

# Configure page layout and title
st.set_page_config(
    page_title="DocuMind AI — S3 Document Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import get_config, mask_secret
from app.services.s3_service import (
    S3Service,
    S3ServiceError,
    S3DocumentTooLargeError,
    sanitize_filename,
    generate_safe_s3_key,
)
from app.agent.orchestrator import AgentOrchestrator
from app.ui.components import (
    render_header,
    render_connection_status,
    render_evidence_card,
    render_tool_telemetry,
)

# Load application configuration
config = get_config()


# Instantiate S3 service
s3_service = S3Service(config)


def init_session_state():
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "comparison_history" not in st.session_state:
        st.session_state.comparison_history = []
    if "s3_connected" not in st.session_state:
        st.session_state.s3_connected = None
    if "s3_category" not in st.session_state:
        st.session_state.s3_category = "UNKNOWN"
    if "s3_status_msg" not in st.session_state:
        st.session_state.s3_status_msg = ""
    if "s3_documents" not in st.session_state:
        st.session_state.s3_documents = []
    if "orchestrator" not in st.session_state or st.session_state.orchestrator is None:
        try:
            st.session_state.orchestrator = AgentOrchestrator(config=config, s3_service=s3_service)
        except Exception as e:
            from app.services.llm_service import LocalSynthesisAdapter
            from app.tools.s3_document_tool import S3DocumentRetrievalTool
            tool = S3DocumentRetrievalTool(config=config, s3_service=s3_service)
            adapter = LocalSynthesisAdapter(config)
            st.session_state.orchestrator = AgentOrchestrator(
                config=config, tool=tool, llm_adapter=adapter, s3_service=s3_service
            )


init_session_state()

# Render executive header (clean brand banner without demo script expander)
render_header()

# Helper function to refresh S3 status and document listing
def refresh_s3_state():
    is_conn, category, msg = s3_service.check_s3_connection_detailed()
    st.session_state.s3_connected = is_conn
    st.session_state.s3_category = category
    st.session_state.s3_status_msg = msg
    if is_conn:
        try:
            st.session_state.s3_documents = s3_service.list_documents()
        except Exception as e:
            st.session_state.s3_documents = []
    else:
        st.session_state.s3_documents = []
    # Clear tool cache so it reflects the latest documents
    if st.session_state.get("orchestrator") and hasattr(st.session_state.orchestrator, "tool"):
        st.session_state.orchestrator.tool.clear_cache()


# Initial check on startup: always ensure active connection or sandbox
if (
    st.session_state.s3_connected is not True
    or not st.session_state.s3_documents
):
    refresh_s3_state()

# -------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ System & Agent Control")

    # 1. AWS Connection Status
    st.markdown("##### ☁️ Amazon S3 Status")
    render_connection_status(
        category=st.session_state.s3_category,
        message=st.session_state.s3_status_msg,
        bucket_masked=config.get_masked_bucket(),
        region=config.aws_region,
    )

    col_ref, col_rst = st.columns(2)
    with col_ref:
        if st.button("🔄 Probe S3", use_container_width=True):
            with st.spinner("Probing S3 connectivity..."):
                refresh_s3_state()
                st.rerun()
    with col_rst:
        if st.button("🧹 Clear State", use_container_width=True):
            st.session_state.clear()
            init_session_state()
            refresh_s3_state()
            st.rerun()

    st.markdown("---")

    # 2. Agent Execution Mode Selector
    st.markdown("##### 🤖 Agent Execution Mode")
    mode_options = [
        "Enhanced Agent (S3 Retrieval Enabled)",
        "Original Agent (S3 Tool Not Enabled)",
        "Side-by-Side Comparison (Before & After)",
    ]
    selected_mode_label = st.radio(
        "Choose Mode:",
        mode_options,
        index=0,
        help="Demonstrates agent behavior before and after being equipped with the S3 retrieval tool.",
        label_visibility="collapsed",
    )

    if "Enhanced Agent" in selected_mode_label:
        current_mode = "enhanced"
        st.markdown(
            '<div class="mode-pill-enhanced">✓ Mode B: Enhanced Agent (S3 Retrieval Active)</div>',
            unsafe_allow_html=True,
        )
    elif "Original Agent" in selected_mode_label:
        current_mode = "original"
        st.markdown(
            '<div class="mode-pill-original">⚠ Mode A: Original Agent (S3 Tool Disabled)</div>',
            unsafe_allow_html=True,
        )
    else:
        current_mode = "compare"
        st.markdown(
            '<div class="mode-pill-enhanced">⚡ Side-by-Side Comparative Mode</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # 3. Document Upload Area (Issue 2)
    st.markdown("##### 📤 Upload Documents to S3")
    st.caption("Upload your own PDF or TXT files to your configured Amazon S3 bucket.")

    uploaded_files = st.file_uploader(
        "Select documents:",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help=f"Supported formats: PDF, TXT. Max file size: {config.max_document_size_mb} MB per file.",
    )

    if uploaded_files:
        st.markdown("**Selected Files to Upload:**")
        total_bytes = 0
        for f in uploaded_files:
            f_size_kb = len(f.getvalue()) / 1024
            total_bytes += len(f.getvalue())
            st.markdown(
                f'<div class="file-preview-box">📄 <strong>{f.name}</strong> ({f_size_kb:.1f} KB)</div>',
                unsafe_allow_html=True,
            )

        # Upload Button
        can_upload = bool(st.session_state.s3_connected)
        if not can_upload:
            st.warning("⚠️ S3 is disconnected. Configure AWS credentials to enable live uploads.")

        if st.button("⬆️ Upload to Amazon S3", type="primary", disabled=not can_upload, use_container_width=True):
            existing_keys = [d["key"] for d in st.session_state.s3_documents]
            success_count = 0
            failed_count = 0
            progress_bar = st.progress(0, text="Uploading files to Amazon S3...")

            for idx, file_obj in enumerate(uploaded_files):
                file_bytes = file_obj.getvalue()
                filename = file_obj.name

                # Validation checks
                if len(file_bytes) == 0:
                    st.error(f"❌ '{filename}' is empty (0 bytes). Skipped.")
                    failed_count += 1
                    continue

                if len(file_bytes) > config.max_document_size_bytes:
                    st.error(
                        f"❌ '{filename}' ({len(file_bytes)/(1024*1024):.1f} MB) exceeds limit of {config.max_document_size_mb} MB."
                    )
                    failed_count += 1
                    continue

                # Generate safe key and avoid collisions
                target_key = generate_safe_s3_key(
                    filename=filename,
                    prefix=config.s3_document_prefix,
                    existing_keys=existing_keys,
                    allow_overwrite=False,
                )

                try:
                    s3_service.upload_document(
                        file_bytes=file_bytes,
                        key=target_key,
                        content_type="application/pdf" if filename.lower().endswith(".pdf") else "text/plain",
                    )
                    existing_keys.append(target_key)
                    success_count += 1
                    dest_str = f"`s3://{config.s3_bucket_name}/{target_key}`" if st.session_state.s3_category == "CONNECTED" else f"`data/s3_storage/{target_key}` (Sandbox)"
                    st.success(f"✓ Uploaded `{os.path.basename(target_key)}` to {dest_str}")
                except Exception as e:
                    st.error(f"❌ Failed to upload '{filename}': {str(e)}")
                    failed_count += 1

                progress_bar.progress((idx + 1) / len(uploaded_files), text=f"Processed {idx + 1}/{len(uploaded_files)}")

            # Refresh list and clear cache so new documents are immediately indexed
            refresh_s3_state()
            if success_count > 0:
                st.toast(f"Successfully uploaded {success_count} document(s)!", icon="🚀")
                time.sleep(0.5)
                st.rerun()

    st.markdown("---")

    # 4. S3 Documents in Bucket
    st.markdown(f"##### 📂 Documents in S3 Bucket ({len(st.session_state.s3_documents)})")

    if st.session_state.s3_documents:
        for doc in st.session_state.s3_documents:
            size_kb = doc["size_bytes"] / 1024
            st.markdown(f"- 📄 **{doc['filename']}** ({size_kb:.1f} KB)")
    else:
        st.info("No documents currently in S3 under prefix.")

    # Secondary Sample Documents Uploader (collapsed)
    with st.expander("📥 Ingest Sample Test Policies (Optional)", expanded=False):
        st.caption("Upload pre-built fictional policies (Leave Policy, Internship Handbook, Reimbursement Policy).")
        if st.button("Upload 3 Sample Policies", disabled=not st.session_state.s3_connected, use_container_width=True):
            if os.path.exists("sample_documents"):
                with st.spinner("Uploading sample policies to S3..."):
                    uploaded = 0
                    for fname in os.listdir("sample_documents"):
                        fpath = os.path.join("sample_documents", fname)
                        if os.path.isfile(fpath) and fname.endswith(config.allowed_extensions):
                            with open(fpath, "rb") as f:
                                s3_service.upload_document(
                                    file_bytes=f.read(),
                                    key=f"{config.s3_document_prefix.rstrip('/')}/{fname}",
                                )
                                uploaded += 1
                    st.success(f"Uploaded {uploaded} sample policies to S3!")
                    refresh_s3_state()
                    st.rerun()
            else:
                st.error("sample_documents/ directory not found.")

    st.markdown("---")

    # 5. Collapsed AWS Setup & Troubleshooting Expander (Issue 5 & 6)
    with st.expander("🛠️ AWS Setup & Troubleshooting", expanded=False):
        st.markdown(
            f"""
            **Current AWS Parameters:**
            - **Region:** `{config.aws_region}`
            - **Bucket:** `{config.s3_bucket_name or '[Not Configured]'}`
            - **Prefix:** `{config.s3_document_prefix}`
            - **Access Key:** `{mask_secret(config.aws_access_key_id)}`
            - **LLM Provider:** `{config.llm_provider.upper()}`

            **Quick Troubleshooting:**
            1. Copy `.env.example` to `.env` in the project root:
               ```bash
               cp .env.example .env
               ```
            2. Configure `S3_BUCKET_NAME` and your AWS credentials in `.env` or run `aws configure`.
            3. Run the live diagnostic tool:
               ```bash
               python scripts/check_aws_connection.py
               ```
            4. Verify your IAM identity has `s3:ListBucket`, `s3:GetObject`, and `s3:PutObject`.
            """
        )

# -------------------------------------------------------------
# MAIN CONTENT AREA
# -------------------------------------------------------------

# Document Status Banner
doc_count = len(st.session_state.s3_documents)
if st.session_state.s3_connected and doc_count > 0:
    target_desc = (
        f"`s3://{config.s3_bucket_name}/{config.s3_document_prefix}`"
        if st.session_state.s3_category == "CONNECTED"
        else f"`data/s3_storage/{config.s3_document_prefix}` (Local Sandbox Demo)"
    )
    st.info(
        f"📚 **Document Corpus Ready:** {doc_count} document(s) available for search under "
        f"{target_desc}. Ask questions below!"
    )
elif st.session_state.s3_connected and doc_count == 0:
    st.warning("📂 Connected to document storage, but no documents found under prefix. Use the sidebar to upload PDF or TXT files.")
else:
    st.warning(
        f"⚠️ **Document Storage Disconnected:** {st.session_state.s3_status_msg} "
        "Please check your `.env` configuration or review the AWS Setup section in the sidebar."
    )

# Quick Prompt Selector Chips
st.markdown("##### 💡 Example Questions:")
col1, col2, col3 = st.columns(3)
quick_prompt = None

with col1:
    if st.button("🏖️ How many annual leave days are provided?", use_container_width=True):
        quick_prompt = "How many days of annual leave does the fictional company provide?"
with col2:
    if st.button("💼 What is the monthly stipend for interns?", use_container_width=True):
        quick_prompt = "What is the monthly stipend and relocation allowance for robotics interns?"
with col3:
    if st.button("✈️ What is the daily domestic meal per diem?", use_container_width=True):
        quick_prompt = "What is the daily domestic meal reimbursement per diem in the reimbursement policy?"


def process_query(prompt: str, mode: str):
    """Execute query through orchestrator and update session state."""
    orchestrator = st.session_state.get("orchestrator")
    if not orchestrator:
        try:
            orchestrator = AgentOrchestrator(config=config, s3_service=s3_service)
        except Exception:
            from app.services.llm_service import LocalSynthesisAdapter
            from app.tools.s3_document_tool import S3DocumentRetrievalTool
            tool = S3DocumentRetrievalTool(config=config, s3_service=s3_service)
            adapter = LocalSynthesisAdapter(config)
            orchestrator = AgentOrchestrator(
                config=config, tool=tool, llm_adapter=adapter, s3_service=s3_service
            )
        st.session_state.orchestrator = orchestrator

    if mode == "compare":
        with st.spinner("Running Side-by-Side Comparison (Original Agent vs Enhanced Agent)..."):
            comparison = orchestrator.compare_modes(prompt)
            st.session_state.comparison_history.append(comparison)
    else:
        with st.spinner(f"Agent retrieving documents and synthesizing answer ({mode.upper()} mode)..."):
            response = orchestrator.ask(prompt, mode=mode)
            st.session_state.messages.append({
                "role": "user",
                "content": prompt,
            })
            st.session_state.messages.append({
                "role": "assistant",
                "response": response,
            })


# Chat input
user_input = st.chat_input("Ask a question about documents stored in your Amazon S3 bucket...")
active_prompt = quick_prompt or user_input

if active_prompt:
    process_query(active_prompt, current_mode)

# -------------------------------------------------------------
# RENDER CHAT / COMPARISON VIEWS
# -------------------------------------------------------------
if current_mode == "compare":
    st.markdown("### ⚡ Side-by-Side Comparison: Before vs. After S3 Tool")
    if not st.session_state.comparison_history:
        st.info("Ask a question above to see how the Original Agent and Enhanced Agent respond to the exact same prompt.")
    else:
        for idx, comp in enumerate(reversed(st.session_state.comparison_history)):
            st.markdown(f"#### ❓ Question: *\"{comp['query']}\"*")
            col_orig, col_enh = st.columns(2)

            with col_orig:
                st.markdown(
                    '<div class="mode-pill-original">Original Agent (Without S3 Tool)</div>',
                    unsafe_allow_html=True,
                )
                orig_res = comp["original"]
                st.markdown(f"**Answer:**\n\n{orig_res['answer']}")
                st.caption(f"⏱️ Latency: {orig_res.get('execution_time_seconds', 0)}s | Tool: None")
                st.info("ℹ️ The baseline agent has no S3 retrieval tool and explains that it cannot access internal documents.")

            with col_enh:
                st.markdown(
                    '<div class="mode-pill-enhanced">Enhanced Agent (With Amazon S3 Tool)</div>',
                    unsafe_allow_html=True,
                )
                enh_res = comp["enhanced"]
                st.markdown(f"**Answer:**\n\n{enh_res['answer']}")

                if enh_res.get("tool_execution"):
                    render_tool_telemetry(enh_res["tool_execution"])

                evidence = enh_res.get("evidence", [])
                if evidence:
                    st.markdown(f"**Supporting Evidence ({len(evidence)} passages retrieved):**")
                    for i, ev in enumerate(evidence):
                        render_evidence_card(ev, i)
                st.caption(f"⏱️ Latency: {enh_res.get('execution_time_seconds', 0)}s | Tool: `search_s3_documents`")

            st.markdown("---")

else:
    # Standard Conversational Chat Stream
    if not st.session_state.messages:
        st.info(
            "👋 Welcome to **DocuMind AI**! Ask questions about your Amazon S3 documents above, "
            "or click one of the example prompts to see how the S3 retrieval tool grounds answers with verifiable citations."
        )
    else:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    res = msg.get("response", {})
                    mode_label = res.get("mode_label", "DocuMind AI")
                    is_enhanced = res.get("agent_mode") == "enhanced"

                    # Agent Mode Pill
                    if is_enhanced:
                        st.markdown(
                            f'<div class="mode-pill-enhanced">✓ {mode_label}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div class="mode-pill-original">⚠ {mode_label}</div>',
                            unsafe_allow_html=True,
                        )

                    # Text Answer
                    st.markdown(res.get("answer", ""))

                    # Tool Telemetry
                    if res.get("tool_execution"):
                        render_tool_telemetry(res["tool_execution"])

                    # Evidence Drawer
                    evidence = res.get("evidence", [])
                    if evidence:
                        with st.expander(f"📚 Supporting Evidence ({len(evidence)} citations)", expanded=True):
                            for i, ev in enumerate(evidence):
                                render_evidence_card(ev, i)
