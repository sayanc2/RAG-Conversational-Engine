# Lazy imports to prevent circular import with the `agents` SDK namespace.
# Import individual modules directly: `from oracle.agents.conductor import conductor_agent`

__all__ = [
    "conductor_agent",
    "herald_agent", "herald_as_tool", "handoff_to_herald",
    "archivist_agent", "archivist_as_tool", "handoff_to_archivist",
    "validator_agent", "validator_as_tool", "validator_guardrail",
    "sentinel_agent", "sentinel_input_guardrail", "sentinel_output_guardrail",
    "OracleAgentHooks", "OracleRunHooks",
]


def __getattr__(name):
    if name in ("conductor_agent",):
        from oracle.agents.conductor import conductor_agent
        return conductor_agent
    if name in ("herald_agent", "herald_as_tool", "handoff_to_herald"):
        import oracle.agents.herald as m
        return getattr(m, name)
    if name in ("archivist_agent", "archivist_as_tool", "handoff_to_archivist"):
        import oracle.agents.archivist as m
        return getattr(m, name)
    if name in ("validator_agent", "validator_as_tool", "validator_guardrail"):
        import oracle.agents.validator as m
        return getattr(m, name)
    if name in ("sentinel_agent", "sentinel_input_guardrail", "sentinel_output_guardrail"):
        import oracle.agents.sentinel as m
        return getattr(m, name)
    if name in ("OracleAgentHooks", "OracleRunHooks"):
        import oracle.agents.hooks as m
        return getattr(m, name)
    raise AttributeError(f"module 'oracle.agents' has no attribute {name!r}")
