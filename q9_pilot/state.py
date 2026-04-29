from dataclasses import dataclass, field
from typing import Any


@dataclass
class Goal:
    question: str
    expected_form: str
    status: str = "open"


@dataclass
class Hypothesis:
    label: str
    source_type: str
    value: Any
    scope_operator: str | None = None
    support: list[str] = field(default_factory=list)
    active: bool = True


@dataclass
class ThoughtState:
    K: dict[str, dict] = field(default_factory=dict)
    G: list[Goal] = field(default_factory=list)
    Ex: str = ""
    H: list[Hypothesis] = field(default_factory=list)
    E: str = "unknown"
    T: dict[str, str] = field(default_factory=dict)
    P: dict[str, list[str]] = field(default_factory=dict)
    intent: str = ""
    trace: list[str] = field(default_factory=list)

    def log(self, step: str) -> None:
        self.trace.append(step)
