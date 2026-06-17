# ORACLE Presentation Guide
## Orchestrated Retrieval and Conversational Logic Engine

**File:** `ORACLE_Presentation.pptx`  
**Slides:** 23  
**Audience:** Executive/Technical Leadership  
**Duration:** 25-30 minutes (+ Q&A)

---

## Presentation Structure

### **Act 1: Problem & Vision (Slides 1-3)**

#### Slide 1: Title Slide
- **Visuals:** Gradient purple/blue background, large typography
- **Message:** Establish brand & topic
- **Talking Points:**
  - "ORACLE" = Orchestrated Retrieval and Conversational Logic Engine
  - RAG-based conversational engine combining structured + unstructured data
  - Mission: fuse enterprise knowledge with live context

#### Slide 2: System Overview
- **Key Takeaways:**
  - This is a production-ready conversational AI system
  - Combines SQL databases WITH real-time web data
  - Multi-agent orchestration ensures reliability
  - "Zero hallucination" = every claim verified against sources
  - Human oversight for edge cases
- **Engagement:** "How many of you have dealt with AI systems hallucinating incorrect data?"

#### Slide 3: Problem Statement
- **Context:** Why this system exists
  - Enterprise knowledge fragmented across sources
  - Traditional RAG suffers from hallucination
  - No unified interface for blended queries
  - Need for automated validation
  - Human review for sensitive cases
- **Connection:** "ORACLE solves all of these problems"

---

### **Act 2: Architecture & Design (Slides 4-9)**

#### Slide 4: Solution Architecture (Flow)
- **Visual:** 7-step pipeline diagram
  1. User Query → Conductor Triage → Specialist Agents → Blended Composition → Validation → HITL Review → Final Answer
- **Talking Point:** "This is the complete query journey through ORACLE"
- **Emphasis:** "Notice validation and HITL before any answer reaches the user"

#### Slide 5: Multi-Agent System (5 Agents)
- **Conductor (Triage + Composition):**
  - Central hub that receives ALL queries
  - Decides routing strategy
  - Composes final answer by blending specialist outputs
  - In charge of PII sensitivity detection

- **HERALD (Weather/News):**
  - Specialists in real-time data from Tavily API
  - Can work as full agent (handoff) or inline tool (blended)
  - Stores results in Chroma for persistence

- **ARCHIVIST (Employee Data):**
  - SQL query specialist
  - Semantic location mapping between employees and places
  - Also dual-mode: full agent or tool

- **VALIDATOR (Groundedness):**
  - Output guardrail that NEVER gets disabled
  - Verifies EVERY claim against sources
  - Can trigger human review if confidence low

- **SENTINEL (Security):**
  - Input guardrail catches prompt injection
  - Output guardrail catches PII leakage
  - Fast, cheap model (GPT-4o-mini)

**Talking Point:** "This is how we achieve reliability. Specialized agents, each with clear responsibility."

#### Slide 6: Manager Pattern (Conductor)
- **The Heart of ORACLE**
  - Implements intelligent triage routing
  - "If I see weather question → send to HERALD"
  - "If I see employee question → send to ARCHIVIST"
  - "If I see BOTH → call both and blend answers"
- **Key Innovation:** Handles context switching seamlessly
- **Fallback:** Claude primary, GPT-4o backup
- **Mandatory Guards:** SENTINEL + VALIDATOR always attached

#### Slide 7: Technology Stack (Two-Column)
- **Backend:**
  - Claude Sonnet 4-5 (primary LLM)
  - GPT-4o (validation & fallback)
  - OpenAI Agents SDK (orchestration)
  - ChromaDB (vector similarities)
  - text-embedding-3-small (embeddings)

- **Database & Storage:**
  - SQLAlchemy ORM
  - SQLite + aiosqlite (async)
  - Redis Phase 2 (distributed)

- **Frontend & APIs:**
  - Tavily (news + weather)
  - Streamlit (chat interface)

**Talking Point:** "Enterprise-grade tech stack. No experimental dependencies."

#### Slide 8: Agent Roster (Table)
- Shows all 5 agents + their roles, models, guardrails, SDK features
- Emphasizes multi-model approach (Claude vs GPT-4o)
- Highlights guardrail attachment

#### Slide 9: Semantic Join (Cross-Source Bridge)
- **The "Magic":** How we bridge SQL + APIs without SQL JOIN
  1. HERALD fetches "Austin, TX" weather from Tavily
  2. Embeds the weather location
  3. Queries Chroma's "employee_locations" collection
  4. Cosine similarity finds employees near Austin
  5. Result: "Raghav works in Austin. Weather: 94F, partly cloudy"
- **Why This Matters:** Solves impedance mismatch between structured & unstructured data
- **Insight:** "Embeddings are the universal bridge language"

---

### **Act 3: Zero Hallucination (Slides 10-13)**

#### Slide 10: Zero Hallucination Posture
- **Core Innovation:** VALIDATOR guardrail is MANDATORY
  - Cannot be disabled, bypassed, or ignored
  - Runs on EVERY answer before user sees it

- **Process:**
  1. Conductor generates answer
  2. VALIDATOR extracts factual claims
  3. VALIDATOR checks each claim against sources
  4. Score: % of grounded claims

- **Thresholds:**
  - ≥ 0.85: PASS (answer delivered)
  - 0.70-0.85: WARN (logged but delivered)
  - < 0.70: FAIL (human review required)

- **Talking Point:** "This is not a suggestion. This is enforcement. Every claim traceable to a source."

#### Slide 11: Human-In-The-Loop (HITL)
- **When It Activates:**
  - Validator score drops below 0.70
  - Conductor detects PII sensitivity (employee + home address, etc.)

- **What Humans See:**
  - Draft answer
  - Groundedness score (visual bar)
  - List of ungrounded claims
  - Editable text box

- **Human Options:**
  - ✅ Approve (answer published as-is)
  - ✏️ Edit & Approve (corrected version published)
  - 🔄 Regenerate (re-run query with rejection context)

- **Audit Trail:** Every decision logged with timestamp

**Talking Point:** "We trust humans more than algorithms for edge cases. HITL is where humans override machines."

#### Slide 12: HITL Hooks & Callbacks
- **Three-Tier Hook System:**
  - Agent-level: lifecycle events (on_start, on_end)
  - Run-level: HITL detection (triggers logged with agent name)
  - HITL-specialized: lifecycle callbacks

- **Hook Events:**
  - `[HITL TRIGGERED]` → panel activated, human notified
  - `[HITL APPROVED]` or `[HITL APPROVED (EDITED)]` → decision logged
  - `[HITL REJECTED]` → query re-run with context

- **Metrics Captured:**
  - Review duration
  - Whether human edited answer
  - Groundedness score at time of review

**Talking Point:** "Complete observability. We know exactly when humans step in, how long they deliberate, and what they decide."

#### Slide 13: Groundedness Validation
- **Two-Phase Validation:**
  1. **Extraction:** GPT-4o extracts all factual claims
  2. **Verification:** Match claims against source chunks

- **Claim Types:**
  - Grounded: explicitly in sources ✓
  - Ungrounded: not found anywhere ✗
  - Unknown: verifiable but sources incomplete ?

- **Source Types Tracked:**
  - SQL rows (employee database)
  - Chroma vectors (stored weather/news)
  - Tavily URLs (live data)

- **Why GPT-4o for Validation (Not Claude):**
  - Avoids confirmation bias
  - Different model = different perspective
  - Double-checks claims independently

---

### **Act 4: Implementation Details (Slides 14-18)**

#### Slide 14: Data Models & Schema
- **OracleSessionContext:** Session state, conversation history, HITL flags
- **ConductorResponse:** Answer + sources + confidence + query type
- **EmployeeRecord:** ID, name, department, location
- **GroundednessReport:** Score + claim verifications + verdict
- **Databases:**
  - SQLite: 500 employee rows, 10 cities, 8 departments
  - Chroma: two collections (live_context + employee_locations)

**Talking Point:** "Structured data models ensure type safety and consistency."

#### Slide 15: Handoff Contracts
- **Escalate to HERALD** → Pure weather/news query
- **Escalate to ARCHIVIST** → Pure employee query
- **Parallel Tool Calls** → Blended queries (both run simultaneously)

**Benefit:** Clear routing rules mean no ambiguity, no missed queries.

#### Slide 16: Development Workflow (5 Phases)
1. **Phase 1A:** Foundation (settings, DB, embeddings)
2. **Phase 1B:** Tools (SQL, Tavily, security, validation)
3. **Phase 1C:** Agents (bottom-up: SENTINEL → specialists → Conductor)
4. **Phase 1D:** Engine + UI (oracle_engine.py, Streamlit)
5. **Phase 1E:** Testing (unit, integration, E2E)
+ **Phase 2:** MCP extension

**Key:** Each phase builds on the previous. Never skip a layer.

#### Slide 17: Validation & Testing
- **Canonical Demo:** "What is the weather like where Raghav works?"
- **Expected Flow:**
  1. SQL lookup → Raghav Sharma, Austin TX, Engineering (EMP-0042)
  2. Tavily fetch → Austin weather data
  3. Semantic match → employee ↔ location (distance < 0.30)
  4. Composition → blended answer with sources
  5. Validation → all claims verified (score: 0.97)
  6. Everything ✓ → answer delivered

**Talking Point:** "This demo proves the entire system works end-to-end."

#### Slide 18: API & Session Management
- **Engine.run(user_query, ctx) → dict**
  - answer: str
  - response: ConductorResponse
  - hitl_triggered: bool
  - groundedness_score: float
  - hitl_metadata: dict (timestamps, actions, review duration)

- **Session Persistence:**
  - Phase 1: SQLite (local development)
  - Phase 2: Redis (distributed, 24h TTL)

- **Conversation History:** Persisted across turns in OracleSessionContext

---

### **Act 5: Operations & Future (Slides 19-23)**

#### Slide 19: Error Handling & Resilience
- **Comprehensive Exception Handling:**
  - Input injection → friendly rejection
  - Low groundedness → HITL activation
  - Max turns → graceful degradation
  - Tavily down → retry + cached fallback
  - Claude down → fall back to GPT-4o
  - All errors logged for debugging

**Talking Point:** "No single point of failure. Graceful degradation everywhere."

#### Slide 20: Feature Highlights
- Semantic cross-source intelligence (embeddings bridge SQL ↔ APIs)
- Agent-as-tool transformation (dual-mode specialists)
- Zero hallucination enforcement (mandatory guardrail)
- HITL with audit trail (every decision logged)
- Multi-model strategy (avoids bias)
- Comprehensive observability (hooks everywhere)
- Production-ready (error handling + session persistence)

#### Slide 21: Deployment & Operations
- **Deployment:**
  - Docker support
  - Redis for sessions
  - SQLite for local dev

- **Configuration:**
  - .env file with API keys
  - Adjustable thresholds (groundedness tripwire, warn level)

- **Monitoring:**
  - Structured JSONL logs
  - HITL review metrics
  - Agent execution timing

- **Scaling:**
  - Max 15 turns per query
  - Session TTL configurable
  - Ready for concurrent users

#### Slide 22: Phase 2 Roadmap
- **MCP Server:** Expose tools as MCP resources
- **HITL Timeout:** Auto-reject after 5 minutes
- **Notifications:** Email/Slack alerts
- **Analytics Dashboard:** Approval rates, review times, common issues
- **Redis Sessions:** Drop-in replacement

#### Slide 23: Q&A
- Invite questions
- Offer live demo
- Discuss future enhancements

---

## Presentation Tips

### **Timing**
- Slides 1-3 (Problem): 5 minutes
- Slides 4-9 (Architecture): 6 minutes
- Slides 10-13 (Zero Hallucination): 5 minutes
- Slides 14-18 (Implementation): 5 minutes
- Slides 19-23 (Ops & Future): 4 minutes
- **Total:** 25 minutes + Q&A

### **Delivery Cadence**
1. **Problem → Empathy:** "Many of you have dealt with hallucinations"
2. **Solution → Clarity:** "ORACLE solves this through [mechanism]"
3. **Implementation → Confidence:** "We built this on enterprise tech"
4. **Impact → Vision:** "Phase 2 extends this to..."

### **Key Talking Points to Emphasize**

#### Zero Hallucination
- "VALIDATOR guardrail is MANDATORY. It cannot be disabled."
- "Every claim is verified against sources before the user sees it."
- "If we can't verify something, we say so explicitly."

#### Multi-Agent Orchestration
- "Each agent has a clear responsibility."
- "Conductor orchestrates, specialists execute."
- "Blended queries run specialists in parallel."

#### Human Trust
- "HITL isn't a last resort—it's part of the design."
- "When confidence drops, humans review."
- "All decisions logged for audit trail."

#### Semantic Bridge
- "Embeddings solve the impedance mismatch."
- "We bridge SQL and APIs without schema coupling."
- "This enables queries like 'weather where Raghav works' naturally."

### **Questions Likely to Be Asked**

**Q: How do you prevent prompt injection?**
A: SENTINEL input guardrail runs on every query. It detects injection patterns and rejects suspicious inputs before they reach agents.

**Q: What if the validator score is marginally low?**
A: 0.70-0.85 is a warning. Answer is still delivered but logged as "warn" for analytics. Humans only review if score < 0.70.

**Q: How fast is it?**
A: Typical blended query: 2-4 seconds. Validator adds <1 second. HITL review is human-paced. No artificial delays.

**Q: Can it work with our existing databases?**
A: Yes. ARCHIVIST uses SQLAlchemy, which supports PostgreSQL, MySQL, SQL Server, etc. Just change the connection string.

**Q: What happens if Tavily API goes down?**
A: Results are cached in Chroma. Subsequent queries for the same location use cached data. Full degradation to SQL-only answers available.

**Q: Does this work with other LLMs?**
A: Primary is Claude. Validator is GPT-4o. Fallback is GPT-4o. Custom models can be swapped via RunConfig.

---

## Design Notes

### **Color Scheme**
- Primary: Purple-Blue (#667EEA) — trust, intelligence
- Secondary: Dark Purple (#764BA2) — authority
- Accent: Orange (#F59E0B) — attention, warnings
- Text: Dark Grey (#1E1B4B) — readability
- Background: Light Grey (#F3F4F6) — clean

### **Typography**
- Titles: 40pt, bold, primary color
- Headers: 20pt, bold, primary color
- Body: 18pt, dark grey
- Code/Details: 14pt, monospace

### **Slides Layout Patterns**
1. **Title Slide:** Gradient background, centered text
2. **Content Slide:** Header bar + bullets
3. **Flow Diagram:** Horizontal pipeline with boxes & arrows
4. **Two-Column:** Side-by-side comparison
5. **Table:** Data-driven insights

---

## Live Demo Script

If doing a live demo during presentation:

1. **Open Streamlit app**
   - Show sidebar with session state
   - Explain ORACLE branding

2. **Query 1: "What is the weather like where Raghav works?"**
   - Show blended query routing
   - Explain Conductor's decision
   - Show sources panel with employee + weather data
   - Demonstrate groundedness score (should be ~0.97)

3. **Query 2: Low-confidence query (intentional)**
   - Ask something with minimal sources
   - Show HITL panel activation
   - Demonstrate human approval workflow
   - Show HITL decision logged

4. **Q&A:** Answer audience questions about specific behaviors

---

## Files Included

- `ORACLE_Presentation.pptx` — Main presentation (23 slides)
- `PRESENTATION_GUIDE.md` — This file
- `HITL_IMPLEMENTATION.md` — Detailed HITL documentation
- `IMPLEMENTATION_SUMMARY.md` — Technical summary
- `VERIFICATION_CHECKLIST.md` — Implementation checklist

---

## Next Steps

1. **Customize for Your Audience:**
   - Adjust slide 21 (Deployment) based on your infrastructure
   - Add your company logo to title slide
   - Note any Phase 2 timeline adjustments

2. **Prepare for Live Demo:**
   - Ensure Streamlit app is running smoothly
   - Pre-load a few queries to demonstrate
   - Test video playback if showing recorded demo

3. **Backup Materials:**
   - Have HITL_IMPLEMENTATION.md ready for deep-dive questions
   - Print the Verification Checklist if needed
   - Prepare live code snippets if showing agent definitions

---

## Summary

This presentation gives your audience a complete picture of ORACLE:
- **Problem:** Why we need this (hallucinations, fragmented data)
- **Solution:** How we solve it (multi-agent + validation)
- **Implementation:** Technical depth without overwhelming
- **Impact:** What this enables going forward

**Tone:** Professional, confident, visionary. This is enterprise-grade AI done right.

---

*Created: 2026-06-16*  
*Ready for large-audience demonstration*
