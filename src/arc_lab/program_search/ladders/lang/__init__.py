"""The `.ladder` surface language: text <-> substrate data.

Implements `docs/abstraction_ladders/LADDER-FORMAT.md` -- the normative spec, which governs this
package (where the two disagree, the spec wins). Layers:

- ``errors`` -- :class:`LadderFormatError`, the one load-time failure (spec VAL-1).
- ``names`` -- what may be spelled where (spec LEX-6, NAM-1, NAM-2).
- ``type_syntax`` -- types and signatures (spec FLR-8, RNG-2).
- ``expr`` -- expression elaboration text -> :class:`Program` and back (spec EXP-1..7).

The language deliberately covers only the ``Apply | Param | Const | Input`` fragment of the
substrate's nine node kinds (spec EXP-7): every ladder template in the batch lives there.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.expr import elaborate_expression, render_expression
from arc_lab.program_search.ladders.lang.names import (
    RESERVED_WORDS,
    check_identifier,
    check_task_id,
)
from arc_lab.program_search.ladders.lang.type_syntax import (
    DefinitionHeader,
    PrimitiveSignature,
    parse_definition_header,
    parse_primitive_signature,
    parse_type,
    render_primitive_signature,
    render_type,
)

__all__ = [
    "RESERVED_WORDS",
    "DefinitionHeader",
    "LadderFormatError",
    "PrimitiveSignature",
    "check_identifier",
    "check_task_id",
    "elaborate_expression",
    "parse_definition_header",
    "parse_primitive_signature",
    "parse_type",
    "render_expression",
    "render_primitive_signature",
    "render_type",
]
