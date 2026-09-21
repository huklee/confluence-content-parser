from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable

from .nodes import DiagramMacro, MacroParameter, TabMacro, TabsMacro
from .parser import ConfluenceParser, ParserContext


def _parameters(element: ET.Element, context: ParserContext) -> list[MacroParameter]:
    return [
        MacroParameter(
            name=context.get_attr(parameter, "name") or "",
            value=context.extract_text(parameter),
            children=context.parse_children(parameter),
        )
        for parameter in context.iter_parameters(element)
    ]


def _parse_plaintext_diagram(element: ET.Element, context: ParserContext) -> DiagramMacro:
    macro_name = context.get_attr(element, "name") or "diagram"
    parameters = _parameters(element, context)
    parameter_values = {parameter.name: parameter.value or "" for parameter in parameters}
    body = context.find_child(element, "plain-text-body")
    source = context.extract_text(body) if body is not None else ""
    return DiagramMacro(
        engine=macro_name,
        macro_name=macro_name,
        title=parameter_values.get("title") or None,
        source=source,
        parameters=parameters,
    )


def register_plaintext_diagrams(
    parser: ConfluenceParser,
    names: Iterable[str] = ("plantuml",),
    *,
    replace: bool = False,
) -> None:
    """Register opaque plaintext diagram macros without executing their DSL."""
    for name in names:
        parser.register_macro(name, _parse_plaintext_diagram, replace=replace)


def _parse_tab(element: ET.Element, context: ParserContext) -> TabMacro:
    parameters = {parameter.name: parameter.value or "" for parameter in _parameters(element, context)}
    title = parameters.get("title", "").strip()
    if not title:
        title = "Untitled tab"
        context.add_diagnostic(
            code="missing_tab_title",
            severity="warning",
            message="Legacy tab macro has no title; using 'Untitled tab'",
            local_name="tab",
        )
    body = context.find_child(element, "rich-text-body")
    children = context.parse_children(body) if body is not None else []
    return TabMacro(title=title, children=children)


def _parse_tabs(element: ET.Element, context: ParserContext) -> TabsMacro:
    parameters = {parameter.name: parameter.value or "" for parameter in _parameters(element, context)}
    body = context.find_child(element, "rich-text-body")
    children = context.parse_children(body) if body is not None else []
    return TabsMacro(orientation=parameters.get("type") or None, children=children)


def register_legacy_tabs(parser: ConfluenceParser, *, replace: bool = False) -> None:
    """Register the nested rich-body `tabs` and `tab` representation."""
    parser.register_macro("tabs", _parse_tabs, replace=replace)
    parser.register_macro("tab", _parse_tab, replace=replace)
