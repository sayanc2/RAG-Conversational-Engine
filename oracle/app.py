"""
ORACLE — Streamlit Frontend
Run from rag-claude/ root:
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python -m streamlit run oracle/app.py
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

# Ensure project root on path + protobuf compat
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import streamlit as st
from streamlit.components.v1 import html as st_html

# ── page config (MUST be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="ORACLE - Conversational Engine",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "**ORACLE** — Orchestrated Retrieval and Conversational Logic Engine",
    },
)

from oracle.models import OracleSessionContext, ConductorResponse, GroundednessReport, Source

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"))

# ── custom CSS ────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
/* ── globals ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    border-right: 1px solid rgba(139,92,246,0.3);
}
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
[data-testid="stSidebar"] .stMetric label { color: #a78bfa !important; font-size: 0.72rem !important; }
[data-testid="stSidebar"] .stMetric [data-testid="stMetricValue"] { color: #f8fafc !important; font-size: 1.1rem !important; }

/* ── main area ── */
.main .block-container { padding: 1.5rem 2rem 5rem; max-width: 900px; margin: 0 auto; }

/* ── oracle header ── */
.oracle-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(102,126,234,0.3);
}
.oracle-header h1 { color: white !important; font-size: 2rem !important; font-weight: 700 !important; margin: 0 !important; }
.oracle-header p  { color: rgba(255,255,255,0.85) !important; margin: 0.3rem 0 0 !important; font-size: 0.9rem !important; }

/* ── chat messages ── */
[data-testid="stChatMessage"] {
    border-radius: 12px !important;
    margin: 0.5rem 0 !important;
    border: 1px solid rgba(148,163,184,0.1) !important;
}

/* ── source cards ── */
.source-card {
    background: linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(139,92,246,0.08) 100%);
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin: 0.4rem 0;
    font-size: 0.82rem;
}
.source-card .source-type {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.source-type.sql    { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
.source-type.tavily { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.source-type.chroma { background: rgba(99,102,241,0.15); color: #6366f1; border: 1px solid rgba(99,102,241,0.3); }

/* ── groundedness meter ── */
.g-bar-wrap { background: rgba(30,27,75,0.4); border-radius: 20px; height: 8px; overflow: hidden; margin: 0.3rem 0; }
.g-bar-fill { height: 100%; border-radius: 20px; transition: width 0.5s ease; }
.g-pass  { background: linear-gradient(90deg,#10b981,#34d399); }
.g-warn  { background: linear-gradient(90deg,#f59e0b,#fbbf24); }
.g-fail  { background: linear-gradient(90deg,#ef4444,#f87171); }

/* ── HITL panel ── */
.hitl-panel {
    background: linear-gradient(135deg, rgba(239,68,68,0.08) 0%, rgba(245,158,11,0.08) 100%);
    border: 1px solid rgba(239,68,68,0.35);
    border-radius: 14px;
    padding: 1.25rem 1.5rem;
    margin: 1rem 0;
}
.hitl-title { color: #ef4444 !important; font-size: 1.1rem !important; font-weight: 700 !important; }
.hitl-score { font-family: 'JetBrains Mono', monospace; font-size: 2rem; font-weight: 700; }

/* ── confidence badge ── */
.conf-badge {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.2rem 0.7rem; border-radius: 20px; font-size: 0.78rem; font-weight: 600;
}
.conf-high { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); }
.conf-med  { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.conf-low  { background: rgba(239,68,68,0.15);  color: #ef4444;  border: 1px solid rgba(239,68,68,0.3); }

/* ── query type badge ── */
.qtype-badge {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.2rem 0.7rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600;
    background: rgba(139,92,246,0.15); color: #a78bfa; border: 1px solid rgba(139,92,246,0.3);
}

/* ── suggestion chips ── */
.suggestion-chip {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    margin: 0.25rem 0.25rem 0 0;
    border-radius: 20px;
    font-size: 0.78rem;
    background: rgba(99,102,241,0.1);
    border: 1px solid rgba(99,102,241,0.25);
    color: #818cf8;
    cursor: pointer;
}

/* ── spinner ── */
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
.dot-live   { background: #10b981; animation: pulse 1.5s infinite; }
.dot-hitl   { background: #ef4444; animation: pulse 0.8s infinite; }
.dot-idle   { background: #6b7280; }
@keyframes pulse {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.5; transform: scale(1.3); }
}

/* ── scrollable chat ── */
.chat-container { max-height: 62vh; overflow-y: auto; padding-right: 4px; }
.chat-container::-webkit-scrollbar { width: 4px; }
.chat-container::-webkit-scrollbar-track { background: transparent; }
.chat-container::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.4); border-radius: 2px; }
</style>
"""

# ── helpers ──────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Run async coroutine safely from Streamlit's sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _confidence_badge(conf: float) -> str:
    if conf >= 0.80:
        cls, label = "conf-high", f"✓ {conf:.0%}"
    elif conf >= 0.50:
        cls, label = "conf-med", f"~ {conf:.0%}"
    else:
        cls, label = "conf-low", f"! {conf:.0%}"
    return f'<span class="conf-badge {cls}">{label}</span>'


def _source_type_badge(stype: str) -> str:
    cls = {"sql": "sql", "tavily": "tavily", "chroma_live": "chroma", "chroma_employee": "chroma"}.get(stype, "chroma")
    return f'<span class="source-type {cls}">{stype}</span>'


def _groundedness_bar(score: float) -> str:
    pct = int(score * 100)
    cls = "g-pass" if score >= 0.85 else "g-warn" if score >= 0.70 else "g-fail"
    return (
        f'<div class="g-bar-wrap"><div class="g-bar-fill {cls}" style="width:{pct}%"></div></div>'
        f'<span style="font-size:0.75rem;color:#94a3b8;">{pct}% grounded</span>'
    )


def _query_type_badge(qtype: str) -> str:
    icons = {"employee_only": "👤", "weather_only": "🌤️", "blended": "🔀", "general": "💬"}
    icon = icons.get(qtype, "💬")
    return f'<span class="qtype-badge">{icon} {qtype.replace("_", " ").title()}</span>'


# ── session state init ────────────────────────────────────────────────────────

def _init_session():
    if "oracle_ctx" not in st.session_state:
        st.session_state.oracle_ctx = OracleSessionContext()
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "hitl_pending" not in st.session_state:
        st.session_state.hitl_pending = False
    if "hitl_draft" not in st.session_state:
        st.session_state.hitl_draft = ""
    if "groundedness_report" not in st.session_state:
        st.session_state.groundedness_report = None
    if "sources_used" not in st.session_state:
        st.session_state.sources_used = []
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    if "processing" not in st.session_state:
        st.session_state.processing = False


# ── sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    ctx: OracleSessionContext = st.session_state.oracle_ctx
    sources: list[Source] = st.session_state.sources_used

    with st.sidebar:
        st.markdown("## 🔮 ORACLE")
        st.markdown("*Orchestrated Retrieval &<br>Conversational Logic Engine*", unsafe_allow_html=True)
        st.divider()

        # Status dot
        if st.session_state.hitl_pending:
            dot = '<span class="status-dot dot-hitl"></span>'
            status_text = "HITL Review Pending"
        elif st.session_state.processing:
            dot = '<span class="status-dot dot-live"></span>'
            status_text = "Processing…"
        else:
            dot = '<span class="status-dot dot-idle"></span>'
            status_text = "Ready"
        st.markdown(f'{dot}<span style="font-size:0.85rem">{status_text}</span>', unsafe_allow_html=True)
        st.divider()

        # Session metrics
        st.markdown("#### Session")
        col1, col2 = st.columns(2)
        col1.metric("Turns", ctx.turn_count)
        col2.metric("Session ID", ctx.session_id[:8] + "…")

        if ctx.last_queried_location:
            st.markdown(f"📍 **Last Location:** {ctx.last_queried_location}")

        # Groundedness
        score = ctx.groundedness_score
        if score is not None:
            st.divider()
            st.markdown("#### Groundedness")
            st.markdown(_groundedness_bar(score), unsafe_allow_html=True)
            verdict_color = {"pass": "🟢", "warn": "🟡", "fail": "🔴"}
            rpt: GroundednessReport | None = st.session_state.groundedness_report
            if rpt:
                st.markdown(f"{verdict_color.get(rpt.verdict, '⚪')} **{rpt.verdict.upper()}** — {rpt.recommendation[:80]}")

        # Sources used
        if sources:
            st.divider()
            st.markdown("#### Sources Used")
            for src in sources[-8:]:  # show last 8
                badge = _source_type_badge(src.source_type)
                st.markdown(
                    f'<div class="source-card">'
                    f'{badge} <strong>{src.reference_id}</strong><br>'
                    f'<span style="color:#94a3b8;font-size:0.78rem">{src.excerpt[:80]}…</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        # Controls
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.oracle_ctx = OracleSessionContext()
            st.session_state.sources_used = []
            st.session_state.hitl_pending = False
            st.session_state.last_response = None
            st.rerun()

        if st.button("🔄 New Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.divider()
        st.markdown(
            '<span style="font-size:0.7rem;color:#64748b;">Powered by Claude claude-sonnet-4-5 + GPT-4o<br>'
            'ChromaDB · SQLite · Tavily</span>',
            unsafe_allow_html=True,
        )


# ── HITL panel ────────────────────────────────────────────────────────────────

def render_hitl_panel():
    ctx: OracleSessionContext = st.session_state.oracle_ctx
    rpt: GroundednessReport | None = st.session_state.groundedness_report

    st.markdown('<div class="hitl-panel">', unsafe_allow_html=True)
    st.markdown('<p class="hitl-title">⚠️ Human Review Required</p>', unsafe_allow_html=True)

    score = ctx.groundedness_score or 0.0
    score_color = "#ef4444" if score < 0.70 else "#f59e0b"
    st.markdown(
        f'<span class="hitl-score" style="color:{score_color}">{score:.0%}</span>'
        f'<span style="font-size:0.85rem;color:#94a3b8;margin-left:0.5rem">groundedness score</span>',
        unsafe_allow_html=True,
    )

    if rpt and rpt.ungrounded_claims:
        with st.expander(f"🔍 {len(rpt.ungrounded_claims)} ungrounded claim(s)", expanded=True):
            for claim in rpt.ungrounded_claims:
                st.markdown(f"- {claim}")

    st.markdown("**Draft Answer:**")
    edited_answer = st.text_area(
        "Edit before approving:",
        value=ctx.hitl_draft_answer or "",
        height=150,
        key="hitl_edit_box",
        label_visibility="collapsed",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ Approve", use_container_width=True, type="primary"):
            _hitl_approve(edited_answer)
    with col2:
        if st.button("✏️ Edit & Approve", use_container_width=True):
            _hitl_approve(edited_answer, is_edited=True)
    with col3:
        if st.button("🔄 Regenerate", use_container_width=True):
            _hitl_regenerate()

    st.markdown('</div>', unsafe_allow_html=True)


def _hitl_approve(answer: str, is_edited: bool = False):
    from oracle.oracle_engine import get_engine

    ctx: OracleSessionContext = st.session_state.oracle_ctx
    engine = get_engine()

    # Call HITL approval hook
    _run_async(engine.process_hitl_approval(ctx, answer, is_edited))

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "meta": {"hitl_reviewed": True, "is_edited": is_edited},
    })
    st.session_state.hitl_pending = False
    st.rerun()


def _hitl_regenerate():
    from oracle.oracle_engine import get_engine

    ctx: OracleSessionContext = st.session_state.oracle_ctx
    engine = get_engine()

    # Call HITL rejection hook
    _run_async(engine.process_hitl_rejection(
        ctx,
        "Human requested low-confidence answer to be regenerated"
    ))

    st.session_state.hitl_pending = False

    # Re-run the last user query with rejection prefix
    if st.session_state.chat_history:
        last_user = next(
            (m["content"] for m in reversed(st.session_state.chat_history) if m["role"] == "user"),
            None,
        )
        if last_user:
            _run_query(f"Previous answer rejected for low groundedness. Please try again: {last_user}")


# ── response rendering ────────────────────────────────────────────────────────

def render_response_meta(response: ConductorResponse):
    """Render badges and follow-up suggestions below an assistant message."""
    parts = []
    parts.append(_confidence_badge(response.confidence))
    parts.append(_query_type_badge(response.query_type))
    st.markdown(" ".join(parts), unsafe_allow_html=True)

    if response.sources:
        with st.expander(f"📚 {len(response.sources)} source(s)"):
            for src in response.sources:
                badge = _source_type_badge(src.source_type)
                conf_b = _confidence_badge(src.confidence)
                st.markdown(
                    f'<div class="source-card">'
                    f'{badge} {conf_b} <strong>{src.reference_id}</strong><br>'
                    f'<span style="color:#94a3b8;font-size:0.78rem">{src.excerpt[:200]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    if response.follow_up_suggestions:
        st.markdown("**💡 Follow-up ideas:**")
        chips_html = "".join(
            f'<span class="suggestion-chip">{s}</span>'
            for s in response.follow_up_suggestions[:3]
        )
        st.markdown(chips_html, unsafe_allow_html=True)


# ── query execution ───────────────────────────────────────────────────────────

def _run_query(user_input: str):
    from oracle.oracle_engine import get_engine

    ctx: OracleSessionContext = st.session_state.oracle_ctx
    engine = get_engine()

    st.session_state.processing = True
    with st.spinner("🔮 ORACLE is thinking…"):
        result = _run_async(engine.run(user_input, ctx))
    st.session_state.processing = False

    answer = result["answer"]
    response: ConductorResponse | None = result.get("response")

    # Persist sources
    if response and response.sources:
        st.session_state.sources_used.extend(response.sources)
        st.session_state.sources_used = st.session_state.sources_used[-20:]  # keep last 20

    st.session_state.last_response = response

    # Update HITL state
    if result["hitl_triggered"]:
        st.session_state.hitl_pending = True
        st.session_state.hitl_draft = ctx.hitl_draft_answer or answer
    else:
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": answer,
            "meta": {"response": response, "security_blocked": result["security_blocked"]},
        })
        # Save session async
        if not result["security_blocked"]:
            try:
                from oracle.memory.session_store import save_session
                _run_async(save_session(ctx))
            except Exception:
                pass


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    _init_session()
    render_sidebar()

    # Header
    st.markdown(
        '<div class="oracle-header">'
        '<h1>🔮 ORACLE</h1>'
        '<p>Orchestrated Retrieval and Conversational Logic Engine &nbsp;·&nbsp; '
        'Employee Intelligence + Live Weather &amp; News</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # HITL panel (if active)
    if st.session_state.hitl_pending:
        render_hitl_panel()

    # Chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🔮"):
            st.markdown(msg["content"])
            meta = msg.get("meta", {})
            if msg["role"] == "assistant":
                if meta.get("security_blocked"):
                    st.markdown(
                        '<span style="font-size:0.75rem;color:#ef4444;">🛡️ Blocked by SENTINEL</span>',
                        unsafe_allow_html=True,
                    )
                elif meta.get("hitl_reviewed"):
                    label = "✏️ Human-edited" if meta.get("is_edited") else "✅ Human-approved"
                    st.markdown(
                        f'<span style="font-size:0.75rem;color:#f59e0b;">{label}</span>',
                        unsafe_allow_html=True,
                    )
                elif meta.get("response"):
                    render_response_meta(meta["response"])

    # Suggested queries (shown when chat is empty)
    if not st.session_state.chat_history:
        st.markdown("### 💬 Try asking…")
        cols = st.columns(2)
        demo_queries = [
            "What is the weather like where Raghav works?",
            "Find all engineers in Austin, TX",
            "What's the latest news from San Francisco?",
            "Who works in the Finance department in New York?",
            "What is the weather in Seattle and who works there?",
            "Tell me about employees in the Marketing department",
        ]
        for i, q in enumerate(demo_queries):
            with cols[i % 2]:
                if st.button(q, key=f"demo_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": q})
                    _run_query(q)
                    st.rerun()

    # Chat input
    user_input = st.chat_input(
        "Ask about employees, weather, or both…",
        disabled=st.session_state.hitl_pending,
    )
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)
        _run_query(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
