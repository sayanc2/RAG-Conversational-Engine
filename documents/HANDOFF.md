# ORACLE — HANDOFF.md
## Orchestrated Retrieval and Conversational Logic Engine
### Complete Code-Session Briefing Document
**Version:** 1.0 | **Date:** 2026-06-09 | **Status:** Ready for Implementation

---

## SYSTEM IDENTITY

| Field | Value |
|---|---|
| System Name | **ORACLE** |
| Full Name | Orchestrated Retrieval and Conversational Logic Engine |
| Purpose | RAG-based conversational engine fusing structured (SQL) + unstructured (vector/web) data |
| Primary LLM | Claude via `claude-sonnet-4-5` |
| Fallback LLM | OpenAI GPT-4o |
| Orchestration | OpenAI Agents SDK (Python) |
| Frontend | Streamlit |
| Vector Store | ChromaDB |
| Relational DB | SQLAlchemy + SQLite (aiosqlite async) |
| Live Data | Tavily API (news + weather) |
| Phase 2 | MCP server extension |

---

## AGENT ROSTER — 5 AGENTS

### Agent 1: ORACLE Conductor *(The Triage & Composition Brain)*
- **File:** `agents/conductor.py`
- **Model:** `claude-sonnet-4-5` (primary) | `gpt-4o` (RunConfig fallback)
- **Role:** Receives every user query. Understands intent. Routes via handoffs or calls specialist agents as tools. Composes final blended answers.
- **SDK Features:**
  - `Runner.run()` entry point
  - `RunContext[OracleSessionContext]`
  - `handoffs=[handoff_to_herald, handoff_to_archivist]`
  - `tools=[herald_as_tool, archivist_as_tool]`
  - `output_type=ConductorResponse`
  - `input_guardrails=[sentinel_input_guardrail]`
  - `output_guardrails=[sentinel_output_guardrail, validator_guardrail]`
  - `hooks=OracleAgentHooks()`
- **Routing Rules (embedded in system prompt):**
  1. Pure weather/news query → `escalate_to_herald` (full handoff)
  2. Pure employee query → `escalate_to_archivist` (full handoff)
  3. Blended query (employee + weather) → call both `fetch_live_context` + `lookup_employee_data` as tools, compose answer
  4. Never hallucinate — if data not in sources, say so explicitly
  5. If sensitive PII combination detected → set `hitl_required=True`

---

### Agent 2: HERALD *(Live News & Weather Specialist)*
- **File:** `agents/herald.py`
- **Model:** `claude-sonnet-4-5`
- **Role:** Fetches live weather and news from Tavily. Embeds results. Stores in Chroma. Performs similarity search.
- **SDK Features:**
  - `function_tool` on all Tavily + Chroma tools
  - `output_type=WeatherNewsResult`
  - `handoff_description` set for Conductor triage guidance
  - `as_tool()` export: `herald_as_tool = herald_agent.as_tool(tool_name="fetch_live_context", ...)`
- **Dual Mode:**
  - As **full Agent** (via Handoff): owns the LLM turn for pure weather/news queries
  - As **Tool** (`herald_as_tool`): called inline by Conductor for blended queries
- **Tools:** `tavily_news_search`, `tavily_weather_fetch`, `embed_and_store_live_context`, `chroma_similarity_search`
- **Output:** `WeatherNewsResult` — weather + news + Chroma doc IDs + `location_matched` bool

---

### Agent 3: ARCHIVIST *(SQL & Employee Knowledge Specialist)*
- **File:** `agents/archivist.py`
- **Model:** `claude-sonnet-4-5`
- **Role:** Queries SQLAlchemy employee database. Performs semantic location mapping between employee `office_location` and Tavily weather location strings.
- **SDK Features:**
  - `function_tool` on all SQL + Chroma tools
  - `output_type=EmployeeQueryResult`
  - `on_handoff` callback pre-loads employee schema info into context
  - `input_filter` on handoff strips weather-only conversation turns
  - `as_tool()` export: `archivist_as_tool = archivist_agent.as_tool(tool_name="lookup_employee_data", ...)`
- **Dual Mode:** Same pattern as HERALD — full Agent or inline Tool
- **Tools:** `sql_query_employee`, `semantic_location_mapper`, `chroma_similarity_search`
- **Output:** `EmployeeQueryResult` — employee records + SQL executed + semantic location match

---

### Agent 4: VALIDATOR *(Groundedness Critic — Zero Hallucination Gate)*
- **File:** `agents/validator.py`
- **Model:** `gpt-4o` (deliberately different from primary — avoids confirmation bias)
- **Role:** Post-generation critic. Verifies every factual claim in Conductor's draft against retrieved source chunks. Triggers HITL if score < 0.70.
- **SDK Features:**
  - Implemented as `@output_guardrail` on Conductor
  - Uses `GuardrailFunctionOutput(tripwire_triggered=True)` when score < 0.70
  - Also exportable as `validator_agent.as_tool(tool_name="validate_groundedness")` for on-demand re-validation
  - `output_type=GroundednessReport`
- **Thresholds:**
  - `score >= 0.85` → pass (proceed)
  - `0.70 <= score < 0.85` → warn (proceed with warning log)
  - `score < 0.70` → FAIL → `tripwire_triggered=True` → HITL activation
- **This guardrail is MANDATORY — never disabled**

---

### Agent 5: SENTINEL *(Input & Output Security Guard)*
- **File:** `agents/sentinel.py`
- **Model:** `gpt-4o-mini` (fast + cheap — appropriate for guardrail role per SDK design philosophy)
- **Role:** Dual-purpose security. Input: detects prompt injection, off-topic queries, PII extraction attempts. Output: detects PII leakage in agent responses.
- **SDK Features:**
  - `@input_guardrail` on Conductor: `run_in_parallel=True` (runs concurrently with Conductor startup for low latency)
  - `@output_guardrail` on Conductor (output side)
  - `output_type=SecurityCheck`
  - Fires `InputGuardrailTripwireTriggered` or `OutputGuardrailTripwireTriggered`

---

## AGENT <-> TOOL TRANSFORMATION MATRIX

| Entity | Primary Form | Transformed Form | When Used |
|---|---|---|---|
| HERALD | Full Agent (Handoff) | `herald_agent.as_tool("fetch_live_context")` | Blended queries |
| ARCHIVIST | Full Agent (Handoff) | `archivist_agent.as_tool("lookup_employee_data")` | Blended queries |
| VALIDATOR | Output Guardrail | `validator_agent.as_tool("validate_groundedness")` | On-demand re-validation |
| `tavily_weather_fetch` | `function_tool` | Consumed inside HERALD agent loop | HERALD acts as agent over it |
| `sql_query_employee` | `function_tool` | Consumed inside ARCHIVIST agent loop | ARCHIVIST acts as agent over it |
| `semantic_location_mapper` | `function_tool` | Cross-source bridge tool | Called by ARCHIVIST |

---

## COMPLETE PYDANTIC CONTRACT LIBRARY

```python
# models/context.py

class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    agent_name: Optional[str] = None

class OracleSessionContext(BaseModel):
    session_id: str
    user_id: str
    conversation_history: list[ConversationTurn] = []
    last_employee_lookup: Optional[EmployeeRecord] = None
    last_weather_lookup: Optional[WeatherResult] = None
    last_queried_location: Optional[str] = None
    hitl_pending: bool = False
    hitl_draft_answer: Optional[str] = None
    groundedness_score: Optional[float] = None
    turn_count: int = 0


# models/responses.py

class Source(BaseModel):
    source_type: Literal["sql", "chroma_live", "chroma_employee", "tavily"]
    reference_id: str
    excerpt: str
    confidence: float

class ConductorResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: float
    query_type: Literal["employee_only", "weather_only", "blended", "general"]
    hitl_required: bool = False
    follow_up_suggestions: list[str] = []

class WeatherResult(BaseModel):
    location: str
    normalized_location: str          # e.g. "austin_tx"
    temperature_f: Optional[float]
    conditions: str
    forecast_summary: Optional[str]
    fetched_at: datetime
    tavily_url: str

class NewsItem(BaseModel):
    headline: str
    summary: str
    url: str
    published_at: Optional[str]

class WeatherNewsResult(BaseModel):
    weather: Optional[WeatherResult]
    news_items: list[NewsItem]
    embedding_ids: list[str]
    location_matched: bool


# models/employee.py

class EmployeeRecord(BaseModel):
    employee_id: str
    name: str
    age: int
    department: str
    office_location: str

class EmployeeQueryResult(BaseModel):
    employees: list[EmployeeRecord]
    total_count: int
    location_embedding_match: Optional[str]
    query_sql: str


# models/validation.py

class ClaimVerification(BaseModel):
    claim: str
    is_grounded: bool
    supporting_source: Optional[Source]
    reason: str

class GroundednessReport(BaseModel):
    score: float                        # 0.0-1.0
    claim_verifications: list[ClaimVerification]
    ungrounded_claims: list[str]
    verdict: Literal["pass", "warn", "fail"]
    recommendation: str


# models/security.py

class SecurityCheck(BaseModel):
    is_safe: bool
    violation_type: Optional[Literal[
        "prompt_injection", "off_topic", "pii_request",
        "pii_leak", "jailbreak", "data_exfiltration"
    ]] = None
    reason: str
    severity: Literal["low", "medium", "high"] = "low"


# Handoff input types

class HeraldHandoffInput(BaseModel):
    query: str
    location_hint: Optional[str] = None

class ArchivistHandoffInput(BaseModel):
    query: str
    employee_name_hint: Optional[str] = None
    department_hint: Optional[str] = None
    location_hint: Optional[str] = None
```

---

## FUNCTION TOOL INVENTORY

### HERALD Tools (tools/tavily_tools.py + tools/chroma_tools.py)

| Tool | Signature | Returns |
|---|---|---|
| `tavily_news_search` | `(ctx, query, max_results=5)` | `list[NewsItem]` |
| `tavily_weather_fetch` | `(ctx, location)` | `WeatherResult` |
| `embed_and_store_live_context` | `(ctx, text, metadata)` | `str` (doc_id) |
| `chroma_similarity_search` | `(ctx, query, collection_name, n_results=5)` | `list[dict]` |

### ARCHIVIST Tools (tools/sql_tools.py)

| Tool | Signature | Returns |
|---|---|---|
| `sql_query_employee` | `(ctx, name, dept, location, emp_id, limit=20)` | `EmployeeQueryResult` |
| `semantic_location_mapper` | `(ctx, weather_location_string)` | `list[EmployeeRecord]` |

### VALIDATOR Tools (tools/validation_tools.py)

| Tool | Signature | Returns |
|---|---|---|
| `extract_and_verify_claims` | `(ctx, answer_text, retrieved_sources)` | `GroundednessReport` |

### SENTINEL Tools (tools/security_tools.py)

| Tool | Signature | Returns |
|---|---|---|
| `classify_input_safety` | `(ctx, user_input)` | `SecurityCheck` |
| `classify_output_safety` | `(ctx, agent_output)` | `SecurityCheck` |

---

## CHROMA VECTOR STORE SCHEMA

### Collection: `live_context`
```
Document ID:    "tavily_{sha256(content)[:16]}"
Document text:  "{location} | {conditions} | {temp_f}F | {forecast}"
                OR "{headline} | {summary}"
Metadata:
  source_type:        "weather" | "news"
  location:           "Austin, TX"
  normalized_location:"austin_tx"
  fetched_at:         ISO timestamp
  tavily_url:         URL string
  session_id:         UUID
```

### Collection: `employee_locations`
```
Document ID:    "emp_{employee_id}"
Document text:  "{office_location}, {department} office"
Metadata:
  employee_id:     "EMP-0042"
  name:            "Raghav Sharma"
  office_location: "Austin, TX"
  department:      "Engineering"
```

### Semantic Location Bridge
When HERALD fetches weather for a location, it queries `employee_locations` with the weather location string embedded. Top cosine-similarity results (distance < 0.30) map weather data to employee records without SQL JOIN. This is the core cross-source intelligence of ORACLE.

---

## SQLALCHEMY DATABASE SCHEMA

### Table: `employees` (500 rows)
```python
class Employee(Base):
    __tablename__ = "employees"
    employee_id     = Column(String(10), primary_key=True)  # "EMP-0001" to "EMP-0500"
    name            = Column(String(100), nullable=False)
    age             = Column(Integer, nullable=False)         # 22-65
    department      = Column(String(50), nullable=False)
    office_location = Column(String(100), nullable=False)
```

### Departments (8):
Engineering, Product, Marketing, Sales, Finance, HR, Operations, Legal

### Office Locations (10 cities — all Tavily-queryable):
```
"New York, NY"       "San Francisco, CA"   "Austin, TX"
"Seattle, WA"        "Chicago, IL"          "Boston, MA"
"Denver, CO"         "Atlanta, GA"          "Miami, FL"
"Portland, OR"
```

### Seeding:
- Use `faker` with `random.seed(42)` for reproducibility
- `employee_id` = `f"EMP-{i:04d}"` for i in 1..500
- **Row 42 is hardcoded: Raghav Sharma, age 34, Engineering, Austin TX** (guaranteed demo)
- After seeding SQL: run `embed_employee_locations()` to embed all 500 locations into Chroma `employee_locations`

---

## SESSION STATE DESIGN

### In-session (within `Runner.run()`):
`OracleSessionContext` passed as `context=` argument. All agents, tools, hooks read/write to it via `RunContextWrapper[OracleSessionContext]`.

### Cross-turn within Streamlit:
`st.session_state["oracle_ctx"]` holds `OracleSessionContext`. Each new user message re-calls `Runner.run()` with the same context — `conversation_history` grows naturally.

### Cross-session persistence (SQLite — Phase 1):
```sql
CREATE TABLE session_memory (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT,
    context_json TEXT,      -- OracleSessionContext.model_dump_json()
    updated_at   TIMESTAMP
);
```
On app start: load prior context if `user_id` matches. On each turn: upsert serialized context.

### Cross-session persistence (Redis — Phase 2):
`pip install 'openai-agents[redis]'`. Same `session_id` key, TTL = 24h. Drop-in replacement in `memory/` module.

---

## HITL (HUMAN-IN-THE-LOOP) FLOW

```
VALIDATOR fires tripwire (score < 0.70)
    |
OutputGuardrailTripwireTriggered caught in oracle_engine.py
    |
ctx.hitl_pending = True
ctx.hitl_draft_answer = draft_answer
ctx.groundedness_score = report.score
st.session_state["hitl_pending"] = True
    |
Streamlit re-renders: HITL panel appears
    |
Human sees: draft answer + ungrounded claims + score
Human chooses: [Approve] [Edit & Approve] [Regenerate]
    |
Approve:     publish draft as-is
Edit:        publish edited version, log as human-corrected
Regenerate:  Runner.run() with "Previous answer rejected: {reason}" prepended
```

HITL also triggers when `ConductorResponse.hitl_required == True` (sensitive PII combination in answer).

---

## HANDOFF CONTRACTS

```
HANDOFF REGISTRY

escalate_to_herald
  From -> To:    Conductor -> HERALD
  Trigger:       Pure weather/news query
  input_type:    HeraldHandoffInput
  on_handoff:    pre-warm Tavily connection, set location in context
  input_filter:  strips employee-only turns from history

escalate_to_archivist
  From -> To:    Conductor -> ARCHIVIST
  Trigger:       Pure employee/HR query
  input_type:    ArchivistHandoffInput
  on_handoff:    pre-load employee schema into context
  input_filter:  strips weather-only turns from history

as_tool() forms (blended queries — parallel tool calls within same Conductor turn):
  herald_as_tool    = herald_agent.as_tool("fetch_live_context")
  archivist_as_tool = archivist_agent.as_tool("lookup_employee_data")
```

---

## RUNNER CONFIGURATION

```python
oracle_run_config = RunConfig(
    workflow_name="oracle_rag_session",
    model="gpt-4o",                        # fallback model
    trace_include_sensitive_data=False,
    tracing_disabled=False,
)

result = await Runner.run(
    starting_agent=conductor,
    input=user_query,
    context=session_ctx,
    run_config=oracle_run_config,
    max_turns=15,
)
```

### Exception Handling (oracle_engine.py):
```python
try:
    result = await Runner.run(...)
except InputGuardrailTripwireTriggered as e:
    # Return friendly rejection; log SecurityCheck
except OutputGuardrailTripwireTriggered as e:
    # Activate HITL panel; serialize state to SQLite
except MaxTurnsExceeded:
    # Return graceful degradation message
except AnthropicAPIError:
    # Already fallen back to GPT-4o via RunConfig; log
```

---

## ENVIRONMENT VARIABLES (.env.example)

```bash
# LLM PROVIDERS
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENAI_DEFAULT_MODEL=gpt-4o

# TAVILY
TAVILY_API_KEY=tvly-...

# DATABASE
DATABASE_URL=sqlite+aiosqlite:///./data/oracle.db
CHROMA_PERSIST_DIR=./data/chroma

# EMBEDDING
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# ORACLE THRESHOLDS
GROUNDEDNESS_TRIPWIRE_THRESHOLD=0.70
GROUNDEDNESS_WARN_THRESHOLD=0.85
MAX_TURNS=15
CHROMA_N_RESULTS=5
SEMANTIC_LOCATION_DISTANCE_THRESHOLD=0.30

# SESSION
SESSION_BACKEND=sqlite
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_HOURS=24

# OBSERVABILITY
LOG_LEVEL=INFO
TRACE_SENSITIVE_DATA=false
LOGFIRE_TOKEN=
```

---

## REQUIREMENTS (requirements.txt)

```
openai-agents>=0.1.0
openai-agents[redis]
anthropic>=0.25.0
openai>=1.30.0
streamlit>=1.35.0
sqlalchemy[asyncio]>=2.0.0
aiosqlite>=0.20.0
chromadb>=0.5.0
tavily-python>=0.5.0
pydantic>=2.7.0
pydantic-settings>=2.0.0
faker>=25.0.0
tenacity>=8.3.0
python-dotenv>=1.0.0
httpx>=0.27.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

---

## PROJECT FOLDER STRUCTURE

```
oracle/
├── app.py                          # Streamlit entrypoint
├── oracle_engine.py                # Runner.run() wrapper + exception handling
├── settings.py                     # Pydantic BaseSettings — all env vars
├── seed_db.py                      # One-time: create DB + seed 500 rows + embed locations
|
├── agents/
│   ├── __init__.py
│   ├── conductor.py                # ORACLE Conductor agent definition
│   ├── herald.py                   # HERALD agent + as_tool() export
│   ├── archivist.py                # ARCHIVIST agent + as_tool() export
│   ├── validator.py                # VALIDATOR agent + output_guardrail definition
│   ├── sentinel.py                 # SENTINEL agent + input/output guardrail definitions
│   └── hooks.py                    # OracleAgentHooks, OracleRunHooks
|
├── tools/
│   ├── __init__.py
│   ├── tavily_tools.py             # tavily_news_search, tavily_weather_fetch
│   ├── chroma_tools.py             # embed_and_store, chroma_similarity_search
│   ├── sql_tools.py                # sql_query_employee, semantic_location_mapper
│   ├── security_tools.py           # classify_input_safety, classify_output_safety
│   ├── validation_tools.py         # extract_and_verify_claims
│   └── embedding.py                # get_embedding() — OpenAI text-embedding-3-small
|
├── models/
│   ├── __init__.py
│   ├── context.py                  # OracleSessionContext, ConversationTurn
│   ├── responses.py                # ConductorResponse, WeatherNewsResult, Source, etc.
│   ├── employee.py                 # EmployeeRecord, EmployeeQueryResult
│   ├── validation.py               # GroundednessReport, ClaimVerification
│   └── security.py                 # SecurityCheck
|
├── db/
│   ├── __init__.py
│   ├── engine.py                   # SQLAlchemy async engine + session factory
│   ├── models.py                   # Employee ORM model
│   └── queries.py                  # build_employee_query(), batch_fetch_by_ids()
|
├── memory/
│   ├── __init__.py
│   ├── session_store.py            # SQLite cross-session persistence (Phase 1)
│   └── redis_store.py              # Redis drop-in (Phase 2)
|
├── prompts/
│   ├── conductor.md                # ORACLE Conductor system prompt
│   ├── herald.md                   # HERALD system prompt
│   ├── archivist.md                # ARCHIVIST system prompt
│   ├── validator.md                # VALIDATOR critic prompt
│   └── sentinel.md                 # SENTINEL security prompt
|
├── data/
│   ├── oracle.db                   # SQLite (git-ignored)
│   └── chroma/                     # Chroma persistent storage (git-ignored)
|
├── logs/                           # Structured JSONL logs (git-ignored)
|
├── tests/
│   ├── test_tools.py               # Unit tests: all function_tools
│   ├── test_agents.py              # Integration: each agent standalone
│   ├── test_guardrails.py          # Guardrail + tripwire tests
│   ├── test_blended_query.py       # E2E: "weather where Raghav works"
│   └── fixtures.py                 # Shared test data, mock Tavily responses
|
├── requirements.txt
├── .env.example
└── HANDOFF.md                      # this file
```

---

## STREAMLIT UI LAYOUT

### Three-panel design:
- **Left sidebar:** Session ID, turn count, last location queried, groundedness score, sources used (SQL row IDs, Chroma doc IDs, distances)
- **Main panel:** `st.chat_message` conversation history + input box at bottom
- **HITL panel:** Conditionally rendered when `st.session_state["hitl_pending"] == True` — shows draft answer + ungrounded claims + score + [Approve / Edit & Approve / Regenerate] buttons

### st.session_state keys:
```
oracle_ctx           OracleSessionContext   persisted across turns
chat_history         list[dict]             rendered by st.chat_message
hitl_pending         bool                   controls HITL panel visibility
hitl_draft           str                    draft answer for human review
groundedness_report  GroundednessReport     shown in HITL panel
sources_used         list[Source]           shown in left sidebar
```

---

## IMPLEMENTATION ORDER (Critical Path)

```
Phase 1A — Foundation (no agents yet, verify all primitives work)
  1.  settings.py + .env.example
  2.  db/models.py + db/engine.py (async SQLAlchemy + aiosqlite)
  3.  seed_db.py -> SQLite 500 rows (Raghav Sharma hardcoded at row 42, Austin TX)
  4.  tools/embedding.py (OpenAI text-embedding-3-small wrapper)
  5.  tools/chroma_tools.py (collections + upsert + similarity search)
  6.  seed_employee_embeddings() -> embeds all 500 locations into Chroma

Phase 1B — Tools (verify each tool independently)
  7.  tools/sql_tools.py
  8.  tools/tavily_tools.py
  9.  tests/test_tools.py  <-- VERIFY ALL TOOLS PASS before building agents

Phase 1C — Agents (bottom-up: guards first, specialists next, conductor last)
  10. agents/sentinel.py + guardrails
  11. agents/validator.py + output_guardrail
  12. agents/herald.py + as_tool() export
  13. agents/archivist.py + as_tool() export
  14. agents/conductor.py (wires everything together)
  15. agents/hooks.py

Phase 1D — Engine + UI
  16. oracle_engine.py (Runner.run() wrapper + all exception handling)
  17. memory/session_store.py (SQLite cross-session persistence)
  18. app.py (Streamlit: chat UI + HITL panel)

Phase 1E — Testing
  19. tests/test_guardrails.py
  20. tests/test_agents.py
  21. tests/test_blended_query.py  <-- CANONICAL ACCEPTANCE TEST

Phase 2 — MCP Extension
  22. oracle_mcp_server.py (exposes tools as MCP resources)
  23. herald_agent_v2 + archivist_agent_v2 with MCPServerStdio
```

---

## CANONICAL DEMO QUERY (Acceptance Test)

**Query:** `"What is the weather like where Raghav works?"`

**Expected ORACLE flow:**
1. SENTINEL input guardrail (parallel) -> `is_safe: True`
2. Conductor receives query -> intent detected: blended (employee + weather)
3. Conductor calls `archivist_as_tool("lookup_employee_data")` -> SQL returns Raghav Sharma, Austin TX, Engineering, EMP-0042
4. Conductor calls `herald_as_tool("fetch_live_context")` with `location="Austin, TX"` -> Tavily returns weather, stored in Chroma
5. Chroma `employee_locations` semantic match confirms EMP-0042 <-> "Austin, TX" weather (distance < 0.30)
6. Conductor composes: `"Raghav Sharma (EMP-0042) works in Austin, TX in the Engineering department. Current weather: 94F, Partly Cloudy."`
7. VALIDATOR output guardrail -> all claims traceable to SQL row + Tavily chunk -> `score: 0.97, verdict: pass`
8. SENTINEL output guardrail -> `is_safe: True`
9. Final answer delivered with sources: `[SQL: EMP-0042, Tavily: weather Austin TX]`

---

## ERROR TAXONOMY

| Error | Source | Handler |
|---|---|---|
| `InputGuardrailTripwireTriggered` | SENTINEL | Friendly rejection message to user |
| `OutputGuardrailTripwireTriggered` | VALIDATOR | Activate HITL panel; serialize state |
| `MaxTurnsExceeded` | Runner | Graceful degradation message |
| `TavilyAPIError` | Tavily | Retry 3x via tenacity -> cached Chroma fallback |
| `SQLAlchemyError` | DB | Log + "employee data unavailable" message |
| `ChromaException` | Vector DB | Log + SQL-only answer fallback |
| `AnthropicAPIError` | Claude | RunConfig falls back to GPT-4o |
| `OpenAIAPIError` | GPT-4o | Log + raise (terminal, no further fallback) |
| `ValidationError` | Pydantic | Log full payload + return error Source |
| Semantic match not found | Chroma | `location_embedding_match=None`; Conductor states location not matched |

---

## MCP PHASE-2 BRIDGE

ORACLE is designed so Phase 2 requires zero architectural rewiring.
- All `function_tool` functions have stable typed signatures
- `oracle_mcp_server.py` wraps those same functions as MCP resources
- A `MCP_ENABLED` env flag in `settings.py` toggles Phase 2 — no agent code changes
- HERALD v2 and ARCHIVIST v2 add `MCPServerStdio` to their `tools=[]` list alongside existing function tools

```
MCP Endpoints:
  oracle/search_employees  -> sql_query_employee
  oracle/get_weather       -> tavily_weather_fetch
  oracle/blended_query     -> full Conductor pipeline
  oracle/session/{id}      -> OracleSessionContext JSON
```

---

## OPENAI AGENTS SDK — COMPLETE COMPONENT CHECKLIST

- [x] `Agent` — all 5 agents
- [x] `Runner.run()` — async entry point in oracle_engine.py
- [x] `RunConfig` — model fallback + tracing config + workflow_name
- [x] `RunContextWrapper[T]` — OracleSessionContext dependency injection
- [x] `function_tool` decorator — all 10 tools
- [x] `handoff()` function — Conductor->HERALD and Conductor->ARCHIVIST
- [x] `handoff(input_type=...)` — typed structured handoff payloads
- [x] `handoff(on_handoff=...)` — pre-warm callbacks
- [x] `handoff(input_filter=...)` — conversation history scrubbing
- [x] `agent.as_tool()` — HERALD and ARCHIVIST transformed to tools
- [x] `InputGuardrail` + `@input_guardrail` — SENTINEL input check
- [x] `OutputGuardrail` + `@output_guardrail` — SENTINEL output + VALIDATOR
- [x] `GuardrailFunctionOutput(tripwire_triggered=...)` — tripwire mechanism
- [x] `InputGuardrailTripwireTriggered` exception — caught in oracle_engine.py
- [x] `OutputGuardrailTripwireTriggered` exception — caught, HITL activation
- [x] `output_type=` (Pydantic BaseModel) — all 5 agents produce structured output
- [x] `AgentHooks` — OracleAgentHooks on all agents (on_start, on_end, on_tool_start, on_tool_end, on_handoff)
- [x] `RunHooks` — global lifecycle logging
- [x] `MaxTurnsExceeded` exception — caught and handled gracefully
- [x] `handoff_description` — on HERALD and ARCHIVIST for Conductor triage
- [x] Built-in tracing — always enabled, trace_include_sensitive_data=False
- [x] Redis session support (`openai-agents[redis]`) — Phase 2 drop-in
- [x] `MCPServerStdio` — Phase 2 MCP integration

---

*End of HANDOFF.md — ORACLE is fully specified and ready to build.*
