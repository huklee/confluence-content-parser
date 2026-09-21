import xml.etree.ElementTree as ET

import pytest

from confluence_content_parser import (
    ConfluenceParser,
    DiagramMacro,
    GenericElement,
    GenericMacro,
    MacroBodyKind,
    ParserLimits,
    TableSection,
    TableSectionType,
    TabMacro,
    TabsMacro,
    Text,
    UnknownContentPolicy,
    register_legacy_tabs,
    register_plaintext_diagrams,
)
from confluence_content_parser.parser import ParserContext, ParsingError


def test_preserve_unknown_element_retains_subtree_and_diagnostic() -> None:
    parser = ConfluenceParser(unknown_content="preserve")
    document = parser.parse("<vendor:box xmlns:vendor='urn:vendor'><p>Keep me</p></vendor:box>")

    assert isinstance(document.root, GenericElement)
    assert document.root.local_name == "box"
    assert document.root.namespace == "urn:vendor"
    assert document.text == "Keep me"
    assert document.metadata["diagnostics"] == ["unknown_element:box"]
    structured = document.metadata["structured_diagnostics"][0]
    assert structured["code"] == "preserved_unknown_element"
    assert structured["severity"] == "warning"
    assert structured["path"] == "/box"


def test_preserve_unknown_rich_macro_retains_ordered_duplicate_parameters() -> None:
    parser = ConfluenceParser(unknown_content=UnknownContentPolicy.PRESERVE)
    document = parser.parse(
        """
        <ac:structured-macro ac:name="vendor-box" ac:schema-version="2" ac:macro-id="macro-1">
          <ac:parameter ac:name="option">first</ac:parameter>
          <ac:parameter ac:name="option">second</ac:parameter>
          <ac:rich-text-body><p>Preserved body</p></ac:rich-text-body>
        </ac:structured-macro>
        """
    )

    assert isinstance(document.root, GenericMacro)
    assert document.root.name == "vendor-box"
    assert document.root.schema_version == "2"
    assert document.root.macro_id == "macro-1"
    assert document.root.body_kind == MacroBodyKind.RICH_TEXT
    assert [(parameter.name, parameter.value) for parameter in document.root.parameters] == [
        ("option", "first"),
        ("option", "second"),
    ]
    assert document.text == "Preserved body"


def test_preserve_unknown_plaintext_macro_keeps_exact_whitespace() -> None:
    source = "  first line\n    second line\n"
    parser = ConfluenceParser(unknown_content="preserve")
    document = parser.parse(
        f"<ac:structured-macro ac:name='dsl'><ac:plain-text-body><![CDATA[{source}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )

    assert isinstance(document.root, GenericMacro)
    assert document.root.body_kind == MacroBodyKind.PLAIN_TEXT
    assert document.root.plain_text_body == source
    assert document.text == source


@pytest.mark.parametrize(
    ("policy", "raises", "has_root"),
    [("error", True, False), ("drop", False, False), ("preserve", False, True)],
)
def test_unknown_content_policies(policy: str, raises: bool, has_root: bool) -> None:
    parser = ConfluenceParser(unknown_content=policy)
    if raises:
        with pytest.raises(ParsingError):
            parser.parse("<unknown>text</unknown>")
        return
    document = parser.parse("<unknown>text</unknown>")
    assert (document.root is not None) is has_root


def test_table_sections_preserve_header_body_footer_and_spans() -> None:
    parser = ConfluenceParser()
    document = parser.parse(
        """
        <table>
          <thead><tr><th colspan="2">Header</th></tr></thead>
          <tbody><tr><td rowspan="2">Body</td><td>One</td></tr></tbody>
          <tfoot><tr><td colspan="2">Footer</td></tr></tfoot>
        </table>
        """
    )
    sections = document.find_all(TableSection)
    assert [section.type for section in sections] == [
        TableSectionType.HEAD,
        TableSectionType.BODY,
        TableSectionType.FOOT,
    ]
    assert "Header" in document.text
    assert "Body" in document.text
    assert "Footer" in document.text


def test_plain_text_link_body_is_supported() -> None:
    parser = ConfluenceParser()
    document = parser.parse(
        """
        <ac:link>
          <ri:page ri:content-title="Target" />
          <ac:plain-text-link-body><![CDATA[Read target]]></ac:plain-text-link-body>
        </ac:link>
        """
    )
    assert document.metadata["diagnostics"] == []
    assert "Read target" in document.text


def test_custom_parser_registration_and_instance_isolation() -> None:
    def parse_widget(element: ET.Element, context: ParserContext) -> Text:
        return Text(text=f"widget:{context.extract_text(element)}")

    first = ConfluenceParser(element_parsers={"widget": parse_widget})
    second = ConfluenceParser(raise_on_finish=False)
    assert first.parse("<widget>ok</widget>").text == "widget:ok"
    assert second.parse("<widget>ok</widget>").root is None


def test_registration_collision_and_mutation_during_parse_are_rejected() -> None:
    parser = ConfluenceParser()

    def parse_paragraph(element: ET.Element, context: ParserContext) -> Text:
        return Text(text=context.extract_text(element))

    with pytest.raises(ValueError, match="already registered"):
        parser.register_element("p", parse_paragraph)

    def mutate_registry(element: ET.Element, context: ParserContext) -> Text:
        parser.register_element("later", parse_paragraph)
        return Text(text="never")

    parser.register_element("mutating", mutate_registry)
    with pytest.raises(RuntimeError, match="during parse"):
        parser.parse("<mutating />")


@pytest.mark.parametrize(
    ("limits", "xml"),
    [
        (ParserLimits(max_xml_bytes=8), "<p>too large</p>"),
        (ParserLimits(max_depth=1), "<div><span><b>deep</b></span></div>"),
        (ParserLimits(max_nodes=2), "<p><strong>many</strong></p>"),
        (
            ParserLimits(max_parameters=1),
            "<ac:structured-macro ac:name='x'><ac:parameter ac:name='a'>1</ac:parameter><ac:parameter ac:name='b'>2</ac:parameter></ac:structured-macro>",
        ),
        (
            ParserLimits(max_plain_text_bytes=3),
            "<ac:structured-macro ac:name='x'><ac:plain-text-body>long</ac:plain-text-body></ac:structured-macro>",
        ),
    ],
)
def test_resource_limits_raise_structured_errors(limits: ParserLimits, xml: str) -> None:
    parser = ConfluenceParser(limits=limits)
    with pytest.raises(ParsingError) as raised:
        parser.parse(xml)
    assert raised.value.structured_diagnostics[0].code == "limit_exceeded"


def test_legacy_tabs_adapter_preserves_order_titles_and_content() -> None:
    parser = ConfluenceParser()
    register_legacy_tabs(parser)
    document = parser.parse(
        """
        <ac:structured-macro ac:name="tabs">
          <ac:parameter ac:name="type">horizontal</ac:parameter>
          <ac:rich-text-body>
            <ac:structured-macro ac:name="tab">
              <ac:parameter ac:name="title">Overview</ac:parameter>
              <ac:rich-text-body><p>First tab</p></ac:rich-text-body>
            </ac:structured-macro>
            <ac:structured-macro ac:name="tab">
              <ac:parameter ac:name="title">Configuration</ac:parameter>
              <ac:rich-text-body><p>Second tab</p></ac:rich-text-body>
            </ac:structured-macro>
          </ac:rich-text-body>
        </ac:structured-macro>
        """
    )
    assert isinstance(document.root, TabsMacro)
    assert document.root.orientation == "horizontal"
    assert [tab.title for tab in document.root.tabs] == ["Overview", "Configuration"]
    assert all(isinstance(tab, TabMacro) for tab in document.root.tabs)
    assert "First tab" in document.text
    assert "Second tab" in document.text


def test_plaintext_diagram_adapter_preserves_source_without_execution() -> None:
    source = "@startuml\nUser -> Server: request\n@enduml\n"
    parser = ConfluenceParser()
    register_plaintext_diagrams(parser)
    document = parser.parse(
        f"""
        <ac:structured-macro ac:name="plantuml">
          <ac:parameter ac:name="title">Sequence</ac:parameter>
          <ac:plain-text-body><![CDATA[{source}]]></ac:plain-text-body>
        </ac:structured-macro>
        """
    )
    assert isinstance(document.root, DiagramMacro)
    assert document.root.engine == "plantuml"
    assert document.root.title == "Sequence"
    assert document.root.source == source
    assert document.text == f"Sequence\n{source}"
