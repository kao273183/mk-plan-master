"""Family-bridge layer. Produces markdown consumable by mk-spec-master.parse_spec.

generate_spec_draft is the single MCP tool exposed here; the formatter is
kept in spec_draft.py so it stays unit-testable without the tool wrapper.
"""

from .spec_draft import render_spec_draft, TEMPLATES

__all__ = ["render_spec_draft", "TEMPLATES"]
