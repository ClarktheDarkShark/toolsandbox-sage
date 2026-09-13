"""Request-local tool identity derived only from actor-visible OpenAI schemas.

The ToolSandbox execution context knows how opaque tool aliases map back to Python
function names.  That mapping is required when a selected call is executed, but it
must not be consulted by SAGE's policy layer: doing so would reveal the answer to
the benchmark's tool-name-scrambling condition.  This module gives policy code a
separate, fail-closed namespace built from exactly the schemas sent to the actor.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping

from sage_ts.runtime.actor_visible_inventory import _schema_derived_capabilities


def _function_payload(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    function = schema.get("function", {})
    return function if isinstance(function, Mapping) else {}


def _public_schema_text(function: Mapping[str, Any]) -> str:
    return " ".join(
        str(function.get(key) or "") for key in ("description", "parameters")
    ).lower()


def _is_publicly_generated(function: Mapping[str, Any]) -> bool:
    """Recognize SAGE tools only from metadata visible in the sent schema."""

    text = _public_schema_text(function)
    return any(
        marker in text
        for marker in (
            "generated sage tool usage",
            "this generated composite",
            "generated deterministic helper",
            "generated helper",
        )
    )


@dataclass(frozen=True)
class ActorVisiblePolicyCatalog:
    """Actor aliases and public-schema-derived semantic capability labels."""

    visible_names: frozenset[str]
    semantic_by_visible_name: Mapping[str, str]
    visible_names_by_semantic: Mapping[str, tuple[str, ...]]
    generated_visible_names: frozenset[str]

    def semantic_name(self, visible_or_semantic_name: str) -> str:
        """Return a public semantic label, or the unchanged visible name.

        Ambiguous and unknown schemas deliberately remain opaque.  Returning an
        execution-context identity here would silently reintroduce privileged
        benchmark information.
        """

        name = str(visible_or_semantic_name or "").strip()
        return str(self.semantic_by_visible_name.get(name, name))

    def visible_name(self, visible_or_semantic_name: str) -> str:
        """Resolve one unambiguous public capability to its sent actor alias."""

        name = str(visible_or_semantic_name or "").strip()
        if name in self.visible_names:
            return name
        aliases = tuple(self.visible_names_by_semantic.get(name, ()))
        return aliases[0] if len(aliases) == 1 else name

    def is_generated(self, visible_or_semantic_name: str) -> bool:
        visible_name = self.visible_name(visible_or_semantic_name)
        return visible_name in self.generated_visible_names


EMPTY_POLICY_CATALOG = ActorVisiblePolicyCatalog(
    visible_names=frozenset(),
    semantic_by_visible_name={},
    visible_names_by_semantic={},
    generated_visible_names=frozenset(),
)


def build_actor_visible_policy_catalog(
    openai_tools: object,
    *,
    known_semantic_capabilities: Iterable[str],
) -> ActorVisiblePolicyCatalog:
    """Build a policy catalog without reading runtime callables or alias maps."""

    if not isinstance(openai_tools, Iterable):
        return EMPTY_POLICY_CATALOG
    known = frozenset(str(item) for item in known_semantic_capabilities)
    visible_names: set[str] = set()
    generated_names: set[str] = set()
    semantic_by_visible: dict[str, str] = {}
    aliases_by_semantic: dict[str, list[str]] = {}

    for raw_schema in openai_tools:
        if not isinstance(raw_schema, Mapping):
            continue
        function = _function_payload(raw_schema)
        visible_name = str(function.get("name") or "").strip()
        if not visible_name:
            continue
        normalized_visible_name = (
            visible_name.split(".", 1)[1]
            if visible_name.startswith("functions.")
            else visible_name
        )
        visible_names.add(visible_name)
        is_unambiguous_owned_name = (
            normalized_visible_name not in known
            and re.fullmatch(r"[a-z][a-z0-9_]*_\d+", normalized_visible_name) is None
        )
        if _is_publicly_generated(function) or is_unambiguous_owned_name:
            # A generated schema can mention native prerequisites.  Those words
            # do not make the generated helper an alias for the native tool.
            generated_names.add(visible_name)
            semantic_by_visible[normalized_visible_name] = normalized_visible_name
            semantic_by_visible[visible_name] = normalized_visible_name
            aliases_by_semantic.setdefault(normalized_visible_name, []).append(
                visible_name
            )
            continue

        capabilities = set(_schema_derived_capabilities((raw_schema,))) & known
        if normalized_visible_name in known:
            capabilities.add(normalized_visible_name)
        # A public schema must identify exactly one known capability.  Multiple
        # matches are kept opaque instead of guessing which hidden tool it is.
        semantic_name = (
            next(iter(capabilities))
            if len(capabilities) == 1
            else normalized_visible_name
        )
        semantic_by_visible[normalized_visible_name] = semantic_name
        semantic_by_visible[visible_name] = semantic_name
        aliases_by_semantic.setdefault(semantic_name, []).append(visible_name)

    return ActorVisiblePolicyCatalog(
        visible_names=frozenset(visible_names),
        semantic_by_visible_name=semantic_by_visible,
        visible_names_by_semantic={
            semantic: tuple(aliases)
            for semantic, aliases in aliases_by_semantic.items()
        },
        generated_visible_names=frozenset(generated_names),
    )


_ACTIVE_POLICY_CATALOG: ContextVar[ActorVisiblePolicyCatalog | None] = ContextVar(
    "sage_actor_visible_policy_catalog",
    default=None,
)


def current_actor_visible_policy_catalog() -> ActorVisiblePolicyCatalog | None:
    return _ACTIVE_POLICY_CATALOG.get()


@contextmanager
def actor_visible_policy_catalog_scope(
    catalog: ActorVisiblePolicyCatalog,
) -> Iterator[ActorVisiblePolicyCatalog]:
    token = _ACTIVE_POLICY_CATALOG.set(catalog)
    try:
        yield catalog
    finally:
        _ACTIVE_POLICY_CATALOG.reset(token)
