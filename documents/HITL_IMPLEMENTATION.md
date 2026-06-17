# Human-In-The-Loop (HITL) Implementation Guide
## ORACLE — Orchestrated Retrieval and Conversational Logic Engine

---

## Overview

This document describes the complete Human-In-The-Loop (HITL) implementation in the ORACLE system, including all hooks, lifecycle events, and integration points.

---

## 1. HITL Architecture

### 1.1 Activation Triggers

HITL can be triggered in two ways:

#### **A. Validator Groundedness Tripwire** (Primary)
When the VALIDATOR agent's output guardrail detects a low groundedness score:
- **Threshold:** `GROUNDEDNESS_TRIPWIRE_THRESHOLD` (default: 0.70)
- **Trigger:** Score < 0.70
- **Flow:**
  ```
  VALIDATOR runs _run_groundedness_check()
    → score calculated from claim verification
    → if score < 0.70, returns verdict="fail"
    → validator_guardrail() sets tripwire_triggered=True
    → OutputGuardrailTripwireTriggered exception raised
    → oracle_engine catches exception
    → HITL activated
  ```

#### **B. Conductor-Flagged PII** (Secondary)
When Conductor detects sensitive PII combinations that require human review:
- **Flag:** `ConductorResponse.hitl_required = True`
- **Use Case:** Employee + personal health data, employee + home address, etc.
- **Flow:**
  ```
  Conductor composes answer with sensitive data
    → sets hitl_required=True in output
    → oracle_engine.run() detects flag
    → HITL pending set in context
    → Human review triggered
  ```

---

## 2. Hooks System

### 2.1 Agent-Level Hooks (`OracleAgentHooks`)

Located in `agents/hooks.py`, implements the `AgentHooks` interface:

```python
class OracleAgentHooks(AgentHooks):
    async def on_start(self, ctx, agent) -> None
    async def on_end(self, ctx, agent, output) -> None
    async def on_tool_start(self, ctx, agent, tool) -> None
    async def on_tool_end(self, ctx, agent, tool, result) -> None
    async def on_handoff(self, ctx, from_agent, to_agent) -> None
```

**HITL-Specific Behavior:**
- `on_start()`: Logs warning if HITL is pending from previous turn
- `on_end()`: Logs warning if output triggered HITL

**Usage:**
Attached to all agents via the `hooks=OracleAgentHooks()` parameter:
```python
conductor_agent = Agent(
    name="ORACLE Conductor",
    ...
    hooks=OracleAgentHooks(),  # → All lifecycle events logged
)
```

---

### 2.2 Run-Level Hooks (`OracleRunHooks`)

Implements the `RunHooks` interface with full HITL lifecycle tracking:

```python
class OracleRunHooks(RunHooks):
    async def on_agent_start(self, ctx, agent) -> None
    async def on_agent_end(self, ctx, agent, output) -> None
    async def on_tool_start(self, ctx, agent, tool) -> None
    async def on_tool_end(self, ctx, agent, tool, result) -> None
    async def on_handoff(self, ctx, from_agent, to_agent) -> None
    
    # HITL Tracking
    def get_hitl_metadata(self) -> dict
```

**HITL Metadata Tracked:**
- `hitl_triggered`: bool — whether HITL was activated in this run
- `hitl_triggered_at`: ISO timestamp — when tripwire fired
- `hitl_triggered_by_agent`: str — which agent triggered it (e.g., "VALIDATOR")

**Usage:**
Instantiated in `OracleEngine.__init__()` and passed to `Runner.run()`:
```python
self._run_hooks = OracleRunHooks()
result = await Runner.run(
    ...,
    hooks=self._run_hooks,
)
```

---

### 2.3 Specialized HITL Hooks (`OracleHITLHooks`)

New class implementing the complete HITL lifecycle:

```python
class OracleHITLHooks:
    async def on_hitl_triggered(
        ctx: OracleSessionContext,
        reason: str,
        draft_answer: str,
        groundedness_score: float,
    ) -> None
    
    async def on_hitl_approved(
        ctx: OracleSessionContext,
        final_answer: str,
        was_edited: bool,
        groundedness_score: float,
    ) -> None
    
    async def on_hitl_rejected(
        ctx: OracleSessionContext,
        reason: str,
        groundedness_score: float,
    ) -> None
    
    async def on_hitl_timeout(
        ctx: OracleSessionContext,
        timeout_seconds: int,
    ) -> None
    
    def get_review_metrics(self) -> dict
```

**Lifecycle Events:**

#### `on_hitl_triggered()`
Called immediately when HITL panel is activated (validator or conductor tripwire).

**Log Entry:**
```
[HITL PANEL ACTIVATED] Session: a1b2c3d4 | Turn: 3 | Reason: Validator groundedness check failed | Score: 0.62
[HITL DRAFT] "Raghav Sharma works in Austin, TX. The weather there is......"
```

**Context:**
- Reason can be: `"Validator groundedness check failed"` or `"Conductor flagged sensitive PII context"`
- Draft answer is logged for audit trail

#### `on_hitl_approved()`
Called when human clicks ✅ or ✏️ buttons.

**Parameters:**
- `was_edited`: bool — True if human modified the answer before approving

**Log Entry (no edit):**
```
[HITL APPROVED] Session: a1b2c3d4 | Turn: 3 | Review time: 45.3s | Score: 0.62
```

**Log Entry (edited):**
```
[HITL APPROVED (EDITED)] Session: a1b2c3d4 | Turn: 3 | Review time: 45.3s | Score: 0.62
```

#### `on_hitl_rejected()`
Called when human clicks 🔄 to regenerate.

**Log Entry:**
```
[HITL REJECTED] Session: a1b2c3d4 | Turn: 3 | Review time: 23.1s | Reason: Human requested low-confidence answer to be regenerated | Score: 0.62
```

#### `on_hitl_timeout()` (Future)
Called if HITL review window expires without human action (Phase 2).

**Metrics Tracked:**
- Human action taken: `"approved" | "rejected" | "timeout"`
- Review duration in seconds
- Review window start/end times

**Usage in `OracleEngine`:**
```python
self._hitl_hooks = OracleHITLHooks()

# On validator tripwire
await self._hitl_hooks.on_hitl_triggered(
    ctx, "Validator groundedness check failed",
    ctx.hitl_draft_answer or "(no draft)",
    ctx.groundedness_score or 0.0
)

# On human approval
await engine.process_hitl_approval(ctx, final_answer, was_edited=True)
```

---

## 3. Integration Points

### 3.1 Validator → Engine → HITL Hooks

**File:** `agents/validator.py`

```python
@output_guardrail
async def validator_guardrail(ctx, agent, output) -> GuardrailFunctionOutput:
    report = _run_groundedness_check(answer_text, sources_dicts)
    ctx.context.groundedness_score = report.score
    
    should_trip = report.verdict == "fail"
    if should_trip:
        ctx.context.hitl_pending = True
        ctx.context.hitl_draft_answer = answer_text
    
    return GuardrailFunctionOutput(
        output_info=report,
        tripwire_triggered=should_trip,
    )
```

**State Mutation:**
- Sets `ctx.groundedness_score`
- Sets `ctx.hitl_pending = True`
- Sets `ctx.hitl_draft_answer = answer_text`

**Exception:**
When `tripwire_triggered=True`, the OpenAI Agents SDK raises `OutputGuardrailTripwireTriggered`.

---

### 3.2 Oracle Engine → HITL Hooks → UI

**File:** `oracle_engine.py`

**On Validator Tripwire:**
```python
except OutputGuardrailTripwireTriggered as e:
    logger.warning(f"Output guardrail triggered: {e}")
    ctx.hitl_pending = True
    
    # Trigger HITL hook
    await self._hitl_hooks.on_hitl_triggered(
        ctx, "Validator groundedness check failed",
        ctx.hitl_draft_answer or "(no draft)",
        ctx.groundedness_score or 0.0
    )
    
    result_dict["hitl_triggered"] = True
    result_dict["answer"] = "⚠️ This response requires human review..."
```

**Return Value:**
```python
{
    "answer": "⚠️ This response requires human review...",
    "response": None,
    "error": None,
    "hitl_triggered": True,
    "security_blocked": False,
    "groundedness_score": 0.62,
    "hitl_metadata": {
        "hitl_triggered": True,
        "hitl_triggered_at": "2026-06-16T14:32:45.123456",
        "hitl_triggered_by_agent": "VALIDATOR",
        "human_action": None,
        "review_duration_seconds": None,
        ...
    }
}
```

---

### 3.3 Streamlit UI → HITL Hooks → Engine

**File:** `app.py`

**Human Approves:**
```python
def _hitl_approve(answer: str, is_edited: bool = False):
    engine = get_engine()
    
    # Call HITL approval hook
    _run_async(engine.process_hitl_approval(ctx, answer, is_edited))
    
    # Add to chat history and re-render
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "meta": {"hitl_reviewed": True, "is_edited": is_edited},
    })
```

**Engine Method:**
```python
async def process_hitl_approval(
    self,
    ctx: OracleSessionContext,
    final_answer: str,
    was_edited: bool,
) -> None:
    await self._hitl_hooks.on_hitl_approved(
        ctx, final_answer, was_edited,
        ctx.groundedness_score or 0.0
    )
    ctx.hitl_pending = False
```

**Human Rejects (Regenerate):**
```python
def _hitl_regenerate():
    engine = get_engine()
    
    # Call HITL rejection hook
    _run_async(engine.process_hitl_rejection(
        ctx,
        "Human requested low-confidence answer to be regenerated"
    ))
    
    # Re-run with rejection context
    _run_query(f"Previous answer rejected. Please try again: {last_user}")
```

---

## 4. Session State Changes

### 4.1 OracleSessionContext (`models/context.py`)

HITL fields in the session context:

```python
class OracleSessionContext(BaseModel):
    session_id: str
    user_id: str
    conversation_history: list[ConversationTurn] = []
    
    # HITL fields
    hitl_pending: bool = False
    hitl_draft_answer: Optional[str] = None
    groundedness_score: Optional[float] = None
    
    turn_count: int = 0
```

**State Lifecycle:**
1. **Initial:** `hitl_pending=False, hitl_draft_answer=None, groundedness_score=None`
2. **Validator Triggers:** `hitl_pending=True, hitl_draft_answer="...", groundedness_score=0.62`
3. **Human Approves:** `hitl_pending=False, hitl_draft_answer=None` (answer in chat_history)
4. **Human Rejects:** `hitl_pending=False, hitl_draft_answer=None` (re-runs query)

---

### 4.2 Streamlit Session State (`app.py`)

HITL-related session keys:

```python
st.session_state.hitl_pending          # bool: HITL panel visible?
st.session_state.hitl_draft            # str: draft for review
st.session_state.groundedness_report   # GroundednessReport: full report
st.session_state.sources_used          # list[Source]: for sidebar
```

---

## 5. Logging & Observability

### 5.1 Log Levels

| Event | Level | Logger |
|---|---|---|
| Agent start/end | INFO | oracle.hooks |
| Agent tool call | INFO/DEBUG | oracle.hooks |
| Handoff | INFO | oracle.hooks |
| HITL triggered | WARNING | oracle.hooks |
| HITL approved | WARNING | oracle.hooks |
| HITL rejected | WARNING | oracle.hooks |
| Guardrail error | WARNING | oracle.engine |
| Unexpected error | ERROR | oracle.engine |

### 5.2 Sample Log Stream

```
[AGENT START] ORACLE Conductor | turn=1
[TOOL START]  ORACLE Conductor -> lookup_employee_data
[TOOL END]    ORACLE Conductor -> lookup_employee_data | result=EmployeeQueryResult(employees=[...])
[TOOL START]  ORACLE Conductor -> fetch_live_context
[TOOL END]    ORACLE Conductor -> fetch_live_context | result=WeatherNewsResult(weather=WeatherResult(...))
[AGENT END]   ORACLE Conductor | output_type=ConductorResponse
[RUN] Agent started: ORACLE Conductor
[RUN] Agent ended: ORACLE Conductor | elapsed=3.45s
[HITL TRIGGERED] Agent: VALIDATOR | Score: 0.62 | Time: 2026-06-16T14:32:45.123456
[HITL PANEL ACTIVATED] Session: a1b2c3d4 | Turn: 1 | Reason: Validator groundedness check failed | Score: 0.62

... (human reviews for 45 seconds) ...

[HITL APPROVED] Session: a1b2c3d4 | Turn: 1 | Review time: 45.3s | Score: 0.62
```

---

## 6. Error Handling

### 6.1 Exception Flow

| Exception | Caught In | Handler | HITL Impact |
|---|---|---|---|
| `OutputGuardrailTripwireTriggered` | `oracle_engine.run()` | exception handler | **Activates HITL** |
| `InputGuardrailTripwireTriggered` | `oracle_engine.run()` | exception handler | None (user input blocked) |
| `MaxTurnsExceeded` | `oracle_engine.run()` | exception handler | None (graceful degradation) |

### 6.2 Graceful Degradation

If HITL approval crashes:
```python
try:
    _run_async(engine.process_hitl_approval(ctx, answer, is_edited))
except Exception as e:
    logger.error(f"HITL approval hook failed: {e}")
    # Still add to chat and proceed
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": answer,
        "meta": {"hitl_reviewed": True, "is_edited": is_edited, "hook_error": str(e)},
    })
```

---

## 7. Testing HITL Flow

### 7.1 Unit Test: Validator Tripwire

**File:** `tests/test_guardrails.py`

```python
@pytest.mark.asyncio
async def test_validator_tripwire():
    """Test validator groundedness check triggers HITL."""
    ctx = OracleSessionContext()
    answer = "Raghav works in Mars. The weather there is unknown."
    sources = []
    
    report = _run_groundedness_check(answer, sources)
    assert report.score < 0.70
    assert report.verdict == "fail"
    assert "ungrounded" in report.recommendation.lower()
```

### 7.2 Integration Test: HITL Approval Flow

**File:** `tests/test_blended_query.py`

```python
@pytest.mark.asyncio
async def test_hitl_approval_flow():
    """Test full HITL approval lifecycle."""
    ctx = OracleSessionContext()
    engine = OracleEngine()
    
    # Run query that triggers HITL
    result = await engine.run(
        "What is the weather like where Raghav works?",
        ctx
    )
    
    assert result["hitl_triggered"]
    assert ctx.hitl_pending
    assert ctx.hitl_draft_answer is not None
    
    # Simulate human approval
    await engine.process_hitl_approval(
        ctx,
        "Austin, TX has partly cloudy skies, 94F.",
        was_edited=False
    )
    
    assert not ctx.hitl_pending
    assert ctx.hitl_draft_answer is None
```

---

## 8. Configuration

### 8.1 Environment Variables

```bash
# HITL Thresholds
GROUNDEDNESS_TRIPWIRE_THRESHOLD=0.70    # Score below this triggers HITL
GROUNDEDNESS_WARN_THRESHOLD=0.85         # Score below this generates warning

# Logging
LOG_LEVEL=INFO                           # Set to DEBUG for detailed hook logs

# Max Turns
MAX_TURNS=15                             # Max agent turns before termination
```

### 8.2 Customization

To change tripwire threshold:
```bash
export GROUNDEDNESS_TRIPWIRE_THRESHOLD=0.75
```

To disable HITL entirely (not recommended):
```python
# In validator.py, modify validator_guardrail() to never trigger
should_trip = False  # Always False (breaks safety!)
```

---

## 9. Phase 2 Enhancements (Future)

### 9.1 HITL Timeout

Auto-reject if human doesn't respond in 5 minutes:
```python
async def on_hitl_timeout(ctx, timeout_seconds=300):
    await self._hitl_hooks.on_hitl_timeout(ctx, timeout_seconds)
    ctx.hitl_pending = False
    # Return degraded answer to user
```

### 9.2 HITL Notifications

Email/Slack alert when HITL triggered:
```python
async def _notify_hitl_triggered(ctx):
    # Send alert to review_team@company.com
    pass
```

### 9.3 HITL Analytics Dashboard

Track metrics across sessions:
- Total HITL triggers per agent
- Average human review time
- Approval rate vs. rejection rate
- Most common ungrounded claims

---

## 10. Troubleshooting

### 10.1 HITL Never Triggers

**Check:**
1. Is `GROUNDEDNESS_TRIPWIRE_THRESHOLD` set correctly?
2. Does the answer have grounded claims? (Empty answer → auto-pass)
3. Are sources being passed to validator?

**Debug:**
```bash
export LOG_LEVEL=DEBUG
# Look for [HITL PANEL ACTIVATED] log line
```

### 10.2 HITL Triggered Too Often

**Solution:**
- Increase `GROUNDEDNESS_TRIPWIRE_THRESHOLD` from 0.70 → 0.75
- Check that sources are comprehensive

### 10.3 Hook Callbacks Not Firing

**Verify:**
```python
engine = get_engine()
assert hasattr(engine, '_hitl_hooks')
assert callable(engine._hitl_hooks.on_hitl_triggered)
```

---

## 11. API Reference

### OracleHITLHooks

```python
class OracleHITLHooks:
    
    async def on_hitl_triggered(
        self,
        ctx: OracleSessionContext,
        reason: str,
        draft_answer: str,
        groundedness_score: float,
    ) -> None:
        """Fired when HITL panel is activated.
        
        Args:
            ctx: Session context with hitl_pending=True
            reason: Human-readable trigger reason
            draft_answer: The answer awaiting review
            groundedness_score: Score that triggered HITL (0.0-1.0)
        """
    
    async def on_hitl_approved(
        self,
        ctx: OracleSessionContext,
        final_answer: str,
        was_edited: bool,
        groundedness_score: float,
    ) -> None:
        """Fired when human approves draft.
        
        Args:
            ctx: Session context
            final_answer: Answer as approved by human
            was_edited: True if human modified before approving
            groundedness_score: Original groundedness score
        """
    
    async def on_hitl_rejected(
        self,
        ctx: OracleSessionContext,
        reason: str,
        groundedness_score: float,
    ) -> None:
        """Fired when human rejects draft and requests regeneration.
        
        Args:
            ctx: Session context
            reason: Human-provided reason for rejection
            groundedness_score: Score of rejected answer
        """
    
    def get_review_metrics(self) -> dict:
        """Return aggregate HITL review metrics.
        
        Returns:
            {
                "human_action": "approved" | "rejected" | "timeout" | None,
                "review_duration_seconds": float | None,
                "review_start_time": float | None,
                "review_end_time": float | None,
            }
        """
```

### OracleEngine.process_hitl_approval

```python
async def process_hitl_approval(
    self,
    ctx: OracleSessionContext,
    final_answer: str,
    was_edited: bool,
) -> None:
    """Process human approval of HITL draft.
    
    Calls on_hitl_approved hook and clears HITL state.
    """
```

### OracleEngine.process_hitl_rejection

```python
async def process_hitl_rejection(
    self,
    ctx: OracleSessionContext,
    reason: str,
) -> None:
    """Process human rejection of HITL draft.
    
    Calls on_hitl_rejected hook and clears HITL state.
    """
```

---

## 12. Summary

The HITL implementation in ORACLE provides:

1. **Three-tier hook system:** Agent → Run → Specialized HITL
2. **Complete lifecycle tracking:** Triggered → Reviewed → Approved/Rejected
3. **Rich observability:** Detailed logs at each stage
4. **Seamless UI integration:** Streamlit HITL panel tied to hooks
5. **Error resilience:** Graceful degradation on hook failures
6. **Extensibility:** Ready for Phase 2 timeouts, notifications, analytics

All hooks are integrated into the validator → engine → UI flow, ensuring human review is enforced when groundedness confidence is low.

---

*Last Updated: 2026-06-16*
