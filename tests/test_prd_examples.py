from confluence_content_parser import (
    ConfluenceParser,
    DiagramMacro,
    TableCell,
    TableSection,
    TabMacro,
    TabsMacro,
    register_legacy_tabs,
    register_plaintext_diagrams,
)


def configured_parser() -> ConfluenceParser:
    parser = ConfluenceParser(unknown_content="preserve")
    register_legacy_tabs(parser)
    register_plaintext_diagrams(parser)
    return parser


def test_example_12_tabbed_container() -> None:
    xml = """
    <p>
      <ac:structured-macro ac:name="tabs" ac:schema-version="1">
        <ac:parameter ac:name="type">horizontal</ac:parameter>
        <ac:rich-text-body>
          <ac:structured-macro ac:name="tab" ac:schema-version="1">
            <ac:parameter ac:name="title">Overview</ac:parameter>
            <ac:rich-text-body>
              <p>This is the content inside <strong>Tab 1</strong>.</p>
            </ac:rich-text-body>
          </ac:structured-macro>
          <ac:structured-macro ac:name="tab" ac:schema-version="1">
            <ac:parameter ac:name="title">Configuration</ac:parameter>
            <ac:rich-text-body>
              <p>This is the content inside <strong>Tab 2</strong>.</p>
            </ac:rich-text-body>
          </ac:structured-macro>
        </ac:rich-text-body>
      </ac:structured-macro>
    </p>
    """
    document = configured_parser().parse(xml)

    tabs = document.find_all(TabsMacro)
    tab_items = document.find_all(TabMacro)
    assert len(tabs) == 1
    assert tabs[0].orientation == "horizontal"
    assert [tab.title for tab in tab_items] == ["Overview", "Configuration"]
    assert "Tab 1" in document.text
    assert "Tab 2" in document.text


def test_example_13_complex_table() -> None:
    xml = """
    <table>
      <thead>
        <tr>
          <th colspan="2">Module Name</th>
          <th>Status</th>
          <th>Owner</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td rowspan="2">Backend API</td>
          <td>Auth Service</td>
          <td>
            <ac:structured-macro ac:name="status" ac:schema-version="1">
              <ac:parameter ac:name="title">ACTIVE</ac:parameter>
              <ac:parameter ac:name="colour">Green</ac:parameter>
            </ac:structured-macro>
          </td>
          <td><ac:link><ri:user ri:userkey="8a7f80824b260021014b26002e210000" /></ac:link></td>
        </tr>
        <tr>
          <td>Payment Gateway</td>
          <td>
            <ac:structured-macro ac:name="status" ac:schema-version="1">
              <ac:parameter ac:name="title">BLOCKED</ac:parameter>
              <ac:parameter ac:name="colour">Red</ac:parameter>
            </ac:structured-macro>
          </td>
          <td><ac:link><ri:user ri:userkey="8a7f80824b260021014b26002e210001" /></ac:link></td>
        </tr>
      </tbody>
    </table>
    """
    document = configured_parser().parse(xml)

    assert document.metadata["diagnostics"] == []
    assert len(document.find_all(TableSection)) == 2
    cells = document.find_all(TableCell)
    assert any(cell.colspan == 2 for cell in cells)
    assert any(cell.rowspan == 2 for cell in cells)
    assert "ACTIVE" in document.text
    assert "BLOCKED" in document.text


def test_example_14_nested_expand_inside_layout() -> None:
    xml = """
    <ac:layout>
      <ac:layout-section ac:type="two_equal">
        <ac:layout-cell>
          <p>
            <ac:structured-macro ac:name="expand" ac:schema-version="1">
              <ac:parameter ac:name="title">View Technical Architecture</ac:parameter>
              <ac:rich-text-body>
                <p>Here are the primary architectural details for the left column.</p>
                <ac:structured-macro ac:name="code" ac:schema-version="1">
                  <ac:parameter ac:name="language">yaml</ac:parameter>
                  <ac:plain-text-body><![CDATA[version: '3.8'
services:
  web:
    image: nginx:latest
]]></ac:plain-text-body>
                </ac:structured-macro>
              </ac:rich-text-body>
            </ac:structured-macro>
          </p>
        </ac:layout-cell>
        <ac:layout-cell>
          <p>
            <ac:structured-macro ac:name="info" ac:schema-version="1">
              <ac:rich-text-body><p>Right column notice block.</p></ac:rich-text-body>
            </ac:structured-macro>
          </p>
        </ac:layout-cell>
      </ac:layout-section>
    </ac:layout>
    """
    document = configured_parser().parse(xml)

    assert document.metadata["diagnostics"] == []
    assert "View Technical Architecture" in document.text
    assert "image: nginx:latest" in document.text
    assert "Right column notice block." in document.text


def test_example_15_plantuml_plaintext_diagram() -> None:
    xml = """
    <p>
      <ac:structured-macro ac:name="plantuml" ac:schema-version="1">
        <ac:parameter ac:name="title">Sequence Diagram</ac:parameter>
        <ac:plain-text-body><![CDATA[@startuml
User -> Client: Click Button
Client -> Server: POST /api/v1/process
Server --> Client: 200 OK
@enduml
]]></ac:plain-text-body>
      </ac:structured-macro>
    </p>
    """
    document = configured_parser().parse(xml)

    diagrams = document.find_all(DiagramMacro)
    assert len(diagrams) == 1
    assert diagrams[0].title == "Sequence Diagram"
    assert diagrams[0].source.startswith("@startuml\n")
    assert diagrams[0].source.endswith("@enduml\n")
    assert "POST /api/v1/process" in diagrams[0].source
