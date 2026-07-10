from typing import TypeAlias

from ..substrate.library import Value

# The signature of a Program is the tuple of its outputs on a Task's training inputs.
Signature: TypeAlias = tuple[Value, ...]
