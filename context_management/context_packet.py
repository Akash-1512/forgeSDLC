from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class ContextPacket(BaseModel):
    """The trimmed, agent-specific view of SDLCState.

    included_fields:  full content — always present at original size
    compressed_fields: summarised — reduced size via ContextCompressor
    excluded_fields:  audit log only — these keys are ABSENT from included and compressed

    CRITICAL INVARIANT: excluded fields are completely absent from the packet.
    NOT set to None. NOT set to []. NOT compressed. The key does not exist.
    test_build_packet_excludes_fields_completely verifies key absence, not value equality.
    """

    model_config = ConfigDict(strict=True)

    agent_name: str
    included_fields: dict[str, object]  # full content
    compressed_fields: dict[str, str]  # summarised
    excluded_fields: list[str]  # absent from packet — stored for audit only
    total_tokens_estimated: int = Field(ge=0)
    compression_applied: bool
    compression_model: str | None
    original_state_tokens: int = Field(ge=0)


class AgentContextSpec(BaseModel):
    """Per-agent definition of which fields to include, compress, or exclude.

    Pydantic validator enforces: required_fields ∩ excluded_fields = ∅
    A field cannot be both required and excluded — that is a spec authoring error.

    Cross-field validator uses Pydantic v2 syntax (ValidationInfo, info.data.get).
    Do NOT use Pydantic v1 syntax (values["required_fields"]) — raises KeyError.
    """

    model_config = ConfigDict(strict=True)

    agent_name: str
    required_fields: list[str]  # always included at full size
    optional_fields: list[str]  # included if space; compressed if large
    excluded_fields: list[str]  # NEVER included — absent from packet
    max_context_tokens: int = Field(ge=1_000)
    summarise_threshold_tokens: int = Field(ge=100)
    memory_layers: list[int]  # which memory layers to include (1-5)
    priority_order: list[str]  # field order when token budget is tight

    @field_validator("excluded_fields")
    @classmethod
    def excluded_cannot_overlap_required(cls, v: list[str], info: ValidationInfo) -> list[str]:
        """Raise ValueError if any field appears in both required and excluded."""
        # info.data contains fields validated before excluded_fields (Pydantic v2)
        required = set(info.data.get("required_fields", []))
        overlap = required & set(v)
        if overlap:
            raise ValueError(
                f"required_fields and excluded_fields overlap: {sorted(overlap)}. "
                "A field cannot be both required and excluded — fix the AgentContextSpec."
            )
        return v
