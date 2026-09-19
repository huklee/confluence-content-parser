from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class UnknownContentPolicy(str, Enum):
    """How the parser handles well-formed elements and macros it does not know."""

    PRESERVE = "preserve"
    ERROR = "error"
    DROP = "drop"


class Diagnostic(BaseModel):
    """A machine-readable parser diagnostic."""

    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    path: str | None = None
    local_name: str | None = None
    namespace: str | None = None

    @property
    def legacy(self) -> str:
        """Return the 0.2.x string representation used in document metadata."""
        if self.local_name and self.code in {
            "unknown_element",
            "unknown_macro",
            "unknown_adf_node_type",
            "preserved_unknown_element",
            "preserved_unknown_macro",
            "dropped_unknown_element",
            "dropped_unknown_macro",
        }:
            legacy_code = self.code.removeprefix("preserved_").removeprefix("dropped_")
            return f"{legacy_code}:{self.local_name}"
        return self.message


class ParserLimits(BaseModel):
    """Resource limits applied before building the document AST."""

    max_xml_bytes: int = Field(default=10_000_000, gt=0)
    max_depth: int = Field(default=100, gt=0)
    max_nodes: int = Field(default=100_000, gt=0)
    max_parameters: int = Field(default=10_000, gt=0)
    max_plain_text_bytes: int = Field(default=5_000_000, gt=0)
