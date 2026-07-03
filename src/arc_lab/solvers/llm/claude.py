"""A Claude-backed solver: prompt the model to induce the rule and emit the grid.

The grids are serialised to a compact digit-matrix text form, the training pairs
are shown as demonstrations, and the model is asked to return the test output as
JSON. This is the simplest useful "LLM-based" solver and a scaffold for richer
ones (rule-then-code, self-consistency sampling, tool use, ...).

The ``anthropic`` package is imported lazily so the rest of arc-lab works without
it. Credentials are resolved by the SDK (``ANTHROPIC_API_KEY`` or an
``ant auth login`` profile); we never take a key as an argument.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.solvers.base import Prediction, Solver

if TYPE_CHECKING:
    from anthropic import Anthropic

# Default to the most capable current model; override per-instance if desired.
DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM = (
    "You are an expert at solving ARC-AGI abstraction puzzles. Each task gives "
    "input/output grid pairs that share one transformation rule. Grids are "
    "matrices of digits 0-9, where each digit is a color. Infer the single rule "
    "from the demonstrations, then apply it to the test input."
)

_INSTRUCTION = (
    "Return ONLY the test output grid, as a JSON array of arrays of integers, "
    "inside a ```json code block. Reason first if helpful, but end with the "
    "code block and nothing after it."
)


class ClaudeSolver(Solver):
    """Solve ARC tasks by prompting a Claude model for the output grid."""

    name = "llm"

    def __init__(self, model: str = DEFAULT_MODEL, *, max_tokens: int = 8000) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client: Anthropic | None = None

    def _get_client(self) -> Anthropic:
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise RuntimeError(
                    "The llm solver needs the 'anthropic' package. "
                    "Install it with: uv sync --extra llm"
                ) from exc
            self._client = Anthropic()
        return self._client

    def predict(self, task: Task) -> Prediction:
        client = self._get_client()
        predictions: Prediction = []
        for example in task.test:
            prompt = _build_prompt(task, example)
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": prompt}],
            )
            text = _response_text(response)
            grid = _parse_grid(text)
            # Fall back to the input if parsing fails, so the shape stays valid.
            predictions.append([grid] if grid is not None else [example.input])
        return predictions


def _build_prompt(task: Task, test: Example) -> str:
    parts: list[str] = ["Here are the demonstration pairs:\n"]
    for i, ex in enumerate(task.train, start=1):
        assert ex.output is not None
        parts.append(f"Example {i} input:\n{ex.input.to_text()}\n")
        parts.append(f"Example {i} output:\n{ex.output.to_text()}\n")
    parts.append(f"Test input:\n{test.input.to_text()}\n")
    parts.append(_INSTRUCTION)
    return "\n".join(parts)


def _response_text(response: Any) -> str:
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)


def _parse_grid(text: str) -> Grid | None:
    """Extract the last JSON grid from the model's response, tolerantly."""
    candidates = _JSON_BLOCK.findall(text)
    if not candidates:
        # Fall back to the last bare ``[[...]]`` structure in the text.
        bare = re.findall(r"\[\s*\[.*?\]\s*\]", text, re.DOTALL)
        candidates = bare
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
            return Grid.from_list(data)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None
