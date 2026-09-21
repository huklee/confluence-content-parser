from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator, Mapping

from .diagnostics import Diagnostic, ParserLimits, UnknownContentPolicy
from .document import ConfluenceDocument
from .nodes import (
    AnchorMacro,
    AttachmentsMacro,
    CodeMacro,
    DecisionList,
    DecisionListItem,
    DecisionListItemState,
    DetailsMacro,
    Emoticon,
    ExcerptIncludeMacro,
    ExcerptMacro,
    ExpandMacro,
    Fragment,
    GenericElement,
    GenericMacro,
    HeadingElement,
    HeadingType,
    Image,
    IncludeMacro,
    JiraMacro,
    LayoutCell,
    LayoutElement,
    LayoutSection,
    LayoutSectionType,
    LinkElement,
    LinkType,
    ListElement,
    ListItem,
    ListType,
    MacroBodyKind,
    MacroParameter,
    Node,
    PanelMacro,
    PanelMacroType,
    PlaceholderElement,
    ProfileMacro,
    ResourceIdentifier,
    ResourceIdentifierType,
    StatusMacro,
    Table,
    TableCell,
    TableRow,
    TableSection,
    TableSectionType,
    TaskListItemStatus,
    TasksReportMacro,
    Text,
    TextBreakElement,
    TextBreakType,
    TextEffectElement,
    TextEffectType,
    Time,
    TocMacro,
    ViewFileMacro,
    ViewPdfMacro,
)

type ElementParser = Callable[[ET.Element, ParserContext], Node | None]
type MacroParser = Callable[[ET.Element, ParserContext], Node | None]


class ParsingError(Exception):
    """Raised when parsing fails with diagnostics."""

    def __init__(self, diagnostics: list[str], structured_diagnostics: list[Diagnostic] | None = None):
        self.diagnostics = diagnostics
        self.structured_diagnostics = structured_diagnostics or []
        super().__init__("; ".join(diagnostics) if diagnostics else "ParsingError")


class ParserContext:
    """Public, limited parser operations available to extension callbacks."""

    def __init__(self, parser: ConfluenceParser) -> None:
        self._parser = parser

    def parse_children(self, element: ET.Element) -> list[Node]:
        return self._parser._parse_children(element)

    def parse_element(self, element: ET.Element) -> Node | None:
        return self._parser._parse_element(element)

    def get_tag_name(self, element: ET.Element) -> str:
        return self._parser._get_tag_name(element)

    def get_attr(self, element: ET.Element, name: str) -> str | None:
        return self._parser._get_attr(element, name)

    def find_child(self, element: ET.Element, tag_name: str) -> ET.Element | None:
        return self._parser._find_child_by_tag(element, tag_name)

    def extract_text(self, element: ET.Element) -> str:
        return self._parser._extract_text_content(element)

    def iter_parameters(self, element: ET.Element) -> Iterator[ET.Element]:
        return self._parser._iter_parameters(element)

    def add_diagnostic(
        self,
        *,
        code: str,
        severity: str,
        message: str,
        local_name: str | None = None,
        namespace: str | None = None,
    ) -> None:
        self._parser._add_diagnostic(
            code=code,
            severity=severity,
            message=message,
            local_name=local_name,
            namespace=namespace,
        )


class ConfluenceParser:
    """Efficient Confluence storage-format XML parser with generic element handling."""

    NS_AC = "http://www.atlassian.com/schema/confluence/4/ac/"
    NS_RI = "http://www.atlassian.com/schema/confluence/4/ri/"
    NS_AT = "http://www.atlassian.com/schema/confluence/4/at/"

    def __init__(
        self,
        *,
        raise_on_finish: bool = True,
        unknown_content: UnknownContentPolicy | str = UnknownContentPolicy.ERROR,
        element_parsers: Mapping[str, ElementParser] | None = None,
        macro_parsers: Mapping[str, MacroParser] | None = None,
        limits: ParserLimits | None = None,
    ):
        self.diagnostics: list[str] = []
        self.structured_diagnostics: list[Diagnostic] = []
        self.raise_on_finish = raise_on_finish
        self.unknown_content = UnknownContentPolicy(unknown_content)
        self.limits = limits or ParserLimits()
        self._path: list[str] = []
        self._is_parsing = False
        self._custom_element_parsers: dict[str, ElementParser] = {}
        self._custom_macro_parsers: dict[str, MacroParser] = {}
        self._skipped_elements = {"colgroup", "col", "adf-fallback", "inline-comment-marker"}
        self._element_parsers: dict[str, Callable[[ET.Element], Node | None]] = {
            "macro": self._parse_macro,
            "structured-macro": self._parse_structured_macro,
            "layout": self._parse_layout,
            "layout-section": self._parse_layout_section,
            "layout-cell": self._parse_layout_cell,
            "h1": self._parse_heading,
            "h2": self._parse_heading,
            "h3": self._parse_heading,
            "h4": self._parse_heading,
            "h5": self._parse_heading,
            "h6": self._parse_heading,
            "strong": self._parse_text_effect,
            "em": self._parse_text_effect,
            "u": self._parse_text_effect,
            "del": self._parse_text_effect,
            "code": self._parse_text_effect,
            "sub": self._parse_text_effect,
            "sup": self._parse_text_effect,
            "blockquote": self._parse_text_effect,
            "span": self._parse_text_effect,
            "p": self._parse_text_break,
            "br": self._parse_text_break,
            "hr": self._parse_text_break,
            "ul": self._parse_list,
            "ol": self._parse_list,
            "li": self._parse_list_item,
            "task-list": self._parse_list,
            "task": self._parse_list_item,
            "link": self._parse_link,
            "link-body": self._parse_link_body,
            "plain-text-link-body": self._parse_link_body,
            "a": self._parse_external_link,
            "image": self._parse_image,
            "emoticon": self._parse_emoticon,
            "placeholder": self._parse_placeholder,
            "time": self._parse_time,
            "page": self._parse_resource_identifier,
            "blog-post": self._parse_resource_identifier,
            "attachment": self._parse_resource_identifier,
            "url": self._parse_resource_identifier,
            "shortcut": self._parse_resource_identifier,
            "user": self._parse_resource_identifier,
            "space": self._parse_resource_identifier,
            "content-entity": self._parse_resource_identifier,
            "table": self._parse_table,
            "tbody": self._parse_table_body,
            "thead": self._parse_table_body,
            "tfoot": self._parse_table_body,
            "tr": self._parse_table_row,
            "th": self._parse_table_cell,
            "td": self._parse_table_cell,
            "adf-extension": self._parse_adf_extension,
        }
        self._macro_parsers: dict[str, Callable[[ET.Element], Node | None]] = {
            "panel": self._parse_panel_macro,
            "tip": self._parse_panel_macro,
            "note": self._parse_panel_macro,
            "warning": self._parse_panel_macro,
            "info": self._parse_panel_macro,
            "code": self._parse_code_macro,
            "details": self._parse_details_macro,
            "expand": self._parse_expand_macro,
            "status": self._parse_status_macro,
            "toc": self._parse_toc_macro,
            "jira": self._parse_jira_macro,
            "include": self._parse_include_macro,
            "tasks-report-macro": self._parse_tasks_report_macro,
            "excerpt-include": self._parse_excerpt_include_macro,
            "attachments": self._parse_attachments_macro,
            "viewpdf": self._parse_viewpdf_macro,
            "view-file": self._parse_view_file_macro,
            "profile": self._parse_profile_macro,
            "anchor": self._parse_anchor_macro,
            "excerpt": self._parse_excerpt_macro,
        }

        for name, callback in (element_parsers or {}).items():
            self.register_element(name, callback)
        for name, callback in (macro_parsers or {}).items():
            self.register_macro(name, callback)

    def register_element(self, name: str, callback: ElementParser, *, replace: bool = False) -> None:
        """Register an element parser on this parser instance."""
        self._ensure_registration_allowed(name, self._element_parsers, self._custom_element_parsers, replace)
        self._custom_element_parsers[name] = callback

    def register_macro(self, name: str, callback: MacroParser, *, replace: bool = False) -> None:
        """Register a macro parser on this parser instance."""
        self._ensure_registration_allowed(name, self._macro_parsers, self._custom_macro_parsers, replace)
        self._custom_macro_parsers[name] = callback

    def _ensure_registration_allowed(
        self,
        name: str,
        builtins: Mapping[str, object],
        custom: Mapping[str, object],
        replace: bool,
    ) -> None:
        if self._is_parsing:
            raise RuntimeError("Parser registrations cannot change during parse()")
        if not name:
            raise ValueError("Parser registration name cannot be empty")
        if not replace and (name in builtins or name in custom):
            raise ValueError(f"A parser is already registered for {name!r}")

    def parse(self, content: str) -> ConfluenceDocument:
        """Parse Confluence storage-format XML into a ConfluenceDocument."""
        self.diagnostics.clear()
        self.structured_diagnostics.clear()
        self._path.clear()
        self._is_parsing = True

        try:
            if len(content.encode("utf-8", errors="ignore")) > self.limits.max_xml_bytes:
                self._add_diagnostic(
                    code="limit_exceeded",
                    severity="error",
                    message=f"XML exceeds max_xml_bytes={self.limits.max_xml_bytes}",
                )
                return self._finish(None)

            try:
                normalized_content = self._normalize_content(content)
                root_element = ET.fromstring(normalized_content)
            except ET.ParseError as exc:
                self._add_diagnostic(code="xml_parse_error", severity="error", message=f"XML parsing failed: {exc}")
                return self._finish(None)

            if not self._validate_limits(root_element):
                return self._finish(None)

            children = self._parse_children(root_element)
            return self._finish(self._consolidate_root(children))
        finally:
            self._is_parsing = False

    def _finish(self, root: Node | None) -> ConfluenceDocument:
        metadata = {
            "diagnostics": self.diagnostics[:],
            "structured_diagnostics": [
                diagnostic.model_dump(mode="json") for diagnostic in self.structured_diagnostics
            ],
        }
        if self.raise_on_finish and any(diagnostic.severity == "error" for diagnostic in self.structured_diagnostics):
            raise ParsingError(self.diagnostics[:], self.structured_diagnostics[:])
        return ConfluenceDocument(root=root, metadata=metadata)

    def _add_diagnostic(
        self,
        *,
        code: str,
        severity: str,
        message: str,
        local_name: str | None = None,
        namespace: str | None = None,
    ) -> None:
        diagnostic = Diagnostic(
            code=code,
            severity=severity,
            message=message,
            path="/" + "/".join(self._path) if self._path else None,
            local_name=local_name,
            namespace=namespace,
        )
        self.structured_diagnostics.append(diagnostic)
        self.diagnostics.append(diagnostic.legacy)

    def _validate_limits(self, root: ET.Element) -> bool:
        node_count = 0
        parameter_count = 0
        stack: list[tuple[ET.Element, int]] = [(root, 0)]
        while stack:
            element, depth = stack.pop()
            node_count += 1
            tag = self._get_tag_name(element)
            if tag == "parameter":
                parameter_count += 1
            if tag == "plain-text-body":
                body_bytes = len(self._extract_text_content(element).encode("utf-8"))
                if body_bytes > self.limits.max_plain_text_bytes:
                    self._add_diagnostic(
                        code="limit_exceeded",
                        severity="error",
                        message=f"Plaintext body exceeds max_plain_text_bytes={self.limits.max_plain_text_bytes}",
                        local_name=tag,
                    )
                    return False
            if depth > self.limits.max_depth:
                self._add_diagnostic(
                    code="limit_exceeded",
                    severity="error",
                    message=f"XML exceeds max_depth={self.limits.max_depth}",
                    local_name=tag,
                )
                return False
            if node_count > self.limits.max_nodes:
                self._add_diagnostic(
                    code="limit_exceeded",
                    severity="error",
                    message=f"XML exceeds max_nodes={self.limits.max_nodes}",
                )
                return False
            if parameter_count > self.limits.max_parameters:
                self._add_diagnostic(
                    code="limit_exceeded",
                    severity="error",
                    message=f"XML exceeds max_parameters={self.limits.max_parameters}",
                )
                return False
            stack.extend((child, depth + 1) for child in element)
        return True

    def _normalize_content(self, content: str) -> str:
        """Add namespace declarations and entity definitions to ensure proper XML parsing."""
        content = content.strip()

        content = self._fix_unicode_surrogates(content)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE root [
            <!ENTITY nbsp "&#160;">
            <!ENTITY ndash "&#8211;">
            <!ENTITY mdash "&#8212;">
            <!ENTITY ldquo "&#8220;">
            <!ENTITY rdquo "&#8221;">
            <!ENTITY lsquo "&#8216;">
            <!ENTITY rsquo "&#8217;">
            <!ENTITY hellip "&#8230;">
            <!ENTITY copy "&#169;">
            <!ENTITY reg "&#174;">
            <!ENTITY trade "&#8482;">
            <!ENTITY zwj "&#8205;">
            <!ENTITY zwnj "&#8204;">
        ]>
        <root xmlns:ac="{self.NS_AC}"
            xmlns:ri="{self.NS_RI}"
            xmlns:at="{self.NS_AT}">
            {content}
        </root>"""

    def _fix_unicode_surrogates(self, content: str) -> str:
        """Fix Unicode surrogate characters that can cause XML parsing issues."""
        try:
            content.encode("utf-8")
            return content
        except UnicodeEncodeError:
            result = []
            i = 0
            while i < len(content):
                char = content[i]
                try:
                    char.encode("utf-8")
                    result.append(char)
                except UnicodeEncodeError:
                    pass
                i += 1
            return "".join(result)

    def _consolidate_root(self, children: list[Node]) -> Node | None:
        """Convert parsed children into appropriate root node structure."""
        if len(children) == 0:
            return None
        elif len(children) == 1:
            return children[0]
        else:
            return Fragment(children=children)

    def _parse_children(self, element: ET.Element) -> list[Node]:
        """Parse all children of an element into nodes."""
        nodes: list[Node] = []

        if element.text and element.text.strip():
            nodes.append(Text(text=element.text.strip()))

        for child in element:
            node = self._parse_element(child)
            if node:
                nodes.append(node)

            if child.tail and child.tail.strip():
                nodes.append(Text(text=child.tail.strip()))

        return nodes

    def _parse_element(self, element: ET.Element) -> Node | None:
        """Parse a single element into appropriate node type."""
        tag = self._get_tag_name(element)
        self._path.append(tag)
        try:
            if tag in self._skipped_elements:
                return None

            custom_parser = self._custom_element_parsers.get(tag)
            if custom_parser:
                return custom_parser(element, ParserContext(self))

            parser = self._element_parsers.get(tag)
            if parser:
                return parser(element)

            return self._handle_unknown_element(element)
        finally:
            self._path.pop()

    def _handle_unknown_element(self, element: ET.Element) -> Node | None:
        local_name = self._get_tag_name(element)
        namespace = self._get_namespace(element)
        if self.unknown_content == UnknownContentPolicy.PRESERVE:
            self._add_diagnostic(
                code="preserved_unknown_element",
                severity="warning",
                message=f"Preserved unknown element {local_name!r}",
                local_name=local_name,
                namespace=namespace,
            )
            return GenericElement(
                local_name=local_name,
                namespace=namespace,
                attributes=dict(element.attrib),
                children=self._parse_children(element),
            )

        severity = "error" if self.unknown_content == UnknownContentPolicy.ERROR else "warning"
        code = "unknown_element" if severity == "error" else "dropped_unknown_element"
        self._add_diagnostic(
            code=code,
            severity=severity,
            message=f"Unknown element {local_name!r}",
            local_name=local_name,
            namespace=namespace,
        )
        return None

    def _parse_layout(self, element: ET.Element) -> LayoutElement:
        """Parse ac:layout element."""
        return LayoutElement(children=self._parse_children(element))

    def _parse_layout_section(self, element: ET.Element) -> LayoutSection:
        """Parse ac:layout-section element."""
        section_type_str = self._get_attr(element, "type") or "single"
        section_type = LayoutSectionType(section_type_str)

        breakout_mode = self._get_attr(element, "breakout-mode")
        breakout_width = self._get_attr(element, "breakout-width")

        return LayoutSection(
            section_type=section_type,
            breakout_mode=breakout_mode,
            breakout_width=breakout_width,
            children=self._parse_children(element),
        )

    def _parse_layout_cell(self, element: ET.Element) -> LayoutCell:
        """Parse ac:layout-cell element."""
        return LayoutCell(children=self._parse_children(element))

    def _parse_heading(self, element: ET.Element) -> HeadingElement:
        """Parse heading elements (h1, h2, h3, h4, h5, h6)."""
        tag = self._get_tag_name(element)
        heading_type = HeadingType(tag)
        styles = self._parse_css_styles(element)
        return HeadingElement(type=heading_type, styles=styles, children=self._parse_children(element))

    def _parse_text_effect(self, element: ET.Element) -> TextEffectElement:
        """Parse text effect elements (strong, em, span, etc.)."""
        tag = self._get_tag_name(element)
        effect_type = TextEffectType(tag)

        styles = self._parse_css_styles(element)

        return TextEffectElement(type=effect_type, styles=styles, children=self._parse_children(element))

    def _parse_text_break(self, element: ET.Element) -> TextBreakElement:
        """Parse text break elements (p, br, hr)."""
        tag = self._get_tag_name(element)
        break_type = TextBreakType(tag)

        if break_type == TextBreakType.PARAGRAPH:
            styles = self._parse_css_styles(element)
            return TextBreakElement(type=break_type, styles=styles, children=self._parse_children(element))
        else:
            return TextBreakElement(type=break_type)

    def _parse_list(self, element: ET.Element) -> ListElement:
        """Parse list elements (ul, ol, task-list)."""
        tag = self._get_tag_name(element)
        list_type = ListType(tag)

        start = None
        if list_type == ListType.ORDERED:
            start_attr = self._get_attr(element, "start")
            if start_attr:
                try:
                    start = int(start_attr)
                except ValueError:
                    pass

        return ListElement(type=list_type, start=start, children=self._parse_children(element))

    def _parse_list_item(self, element: ET.Element) -> ListItem:
        """Parse list item elements (li, ac:task)."""
        tag = self._get_tag_name(element)

        if tag == "task":
            task_id = None
            uuid = None
            status = TaskListItemStatus.INCOMPLETE
            children = []

            for child in element:
                child_tag = self._get_tag_name(child)
                if child_tag == "task-id":
                    task_id = self._extract_text_content(child)
                elif child_tag == "task-uuid":
                    uuid = self._extract_text_content(child)
                elif child_tag == "task-status":
                    status_text = self._extract_text_content(child)
                    status = TaskListItemStatus(status_text)
                elif child_tag == "task-body":
                    children = self._parse_children(child)

            return ListItem(task_id=task_id, uuid=uuid, status=status, children=children)
        else:
            return ListItem(children=self._parse_children(element))

    def _parse_external_link(self, element: ET.Element) -> LinkElement:
        """Parse external <a> links."""
        href = self._get_attr(element, "href")

        if href and href.startswith("mailto:"):
            link_type = LinkType.MAILTO
        else:
            link_type = LinkType.EXTERNAL

        return LinkElement(type=link_type, href=href, children=self._parse_children(element))

    def _parse_link(self, element: ET.Element) -> LinkElement:
        """Parse ac:link elements."""
        anchor = self._get_attr(element, "anchor")

        children = self._parse_children(element)

        link_type = LinkType.EXTERNAL
        if anchor:
            link_type = LinkType.ANCHOR
        else:
            for child in children:
                if hasattr(child, "type") and hasattr(child.type, "value"):
                    if child.type.value == "page":
                        link_type = LinkType.PAGE
                        break
                    elif child.type.value == "blog-post":
                        link_type = LinkType.BLOG_POST
                        break
                    elif child.type.value == "user":
                        link_type = LinkType.USER
                        break
                    elif child.type.value == "space":
                        link_type = LinkType.SPACE
                        break
                    elif child.type.value == "attachment":
                        link_type = LinkType.ATTACHMENT
                        break

        return LinkElement(type=link_type, anchor=anchor, children=children)

    def _parse_link_body(self, element: ET.Element) -> Fragment:
        """Parse ac:link-body elements as fragment containers for rich content."""
        return Fragment(children=self._parse_children(element))

    def _parse_image(self, element: ET.Element) -> Image:
        """Parse ac:image elements."""
        src = self._get_attr(element, "src")
        alt = self._get_attr(element, "alt")
        title = self._get_attr(element, "title")
        width = self._get_attr(element, "width")
        height = self._get_attr(element, "height")
        alignment = self._get_attr(element, "align")
        layout = self._get_attr(element, "layout")
        original_height = self._get_attr(element, "original-height")
        original_width = self._get_attr(element, "original-width")
        custom_width = self._get_attr(element, "custom-width")

        filename = None
        version_at_save = None
        url_value = None
        children = []

        for child in element:
            child_tag = self._get_tag_name(child)

            if child_tag == "attachment":
                filename = self._get_attr(child, "filename")
                version_at_save = self._get_attr(child, "version-at-save")
            elif child_tag == "url":
                url_value = self._get_attr(child, "value")
            elif child_tag == "caption":
                children = self._parse_children(child)

        return Image(
            src=src,
            alt=alt,
            title=title,
            width=width,
            height=height,
            alignment=alignment,
            layout=layout,
            original_height=original_height,
            original_width=original_width,
            custom_width=custom_width == "true" if custom_width else None,
            filename=filename,
            version_at_save=version_at_save,
            url_value=url_value,
            children=children,
        )

    def _parse_emoticon(self, element: ET.Element) -> Emoticon:
        """Parse ac:emoticon elements."""
        name = self._get_attr(element, "name")
        emoji_shortname = self._get_attr(element, "emoji-shortname")
        emoji_id = self._get_attr(element, "emoji-id")
        emoji_fallback = self._get_attr(element, "emoji-fallback")

        return Emoticon(
            name=name or "", emoji_shortname=emoji_shortname, emoji_id=emoji_id, emoji_fallback=emoji_fallback
        )

    def _parse_placeholder(self, element: ET.Element) -> PlaceholderElement:
        """Parse placeholder elements."""
        text = self._extract_text_content(element)
        return PlaceholderElement(text=text)

    def _parse_time(self, element: ET.Element) -> Time:
        """Parse time elements."""
        datetime = self._get_attr(element, "datetime")
        return Time(datetime=datetime)

    def _parse_resource_identifier(self, element: ET.Element) -> ResourceIdentifier:
        """Parse ri:* resource identifier elements."""
        tag = self._get_tag_name(element)
        resource_type = ResourceIdentifierType(tag)

        space_key = self._get_attr(element, "space-key")
        content_title = self._get_attr(element, "content-title")
        content_id = self._get_attr(element, "content-id")

        posting_day = self._get_attr(element, "posting-day")
        filename = self._get_attr(element, "filename")
        value = self._get_attr(element, "value")
        key = self._get_attr(element, "key")
        parameter = self._get_attr(element, "parameter")
        account_id = self._get_attr(element, "account-id")
        local_id = self._get_attr(element, "local-id")
        userkey = self._get_attr(element, "userkey")
        version_at_save = self._get_attr(element, "version-at-save")

        return ResourceIdentifier(
            type=resource_type,
            space_key=space_key,
            content_title=content_title,
            content_id=content_id,
            posting_day=posting_day,
            filename=filename,
            value=value,
            key=key,
            parameter=parameter,
            account_id=account_id,
            local_id=local_id,
            userkey=userkey,
            version_at_save=version_at_save,
        )

    def _parse_table(self, element: ET.Element) -> Table:
        """Parse table elements."""
        width = self._get_attr(element, "data-table-width")
        layout = self._get_attr(element, "data-layout")
        local_id = self._get_attr(element, "local-id")
        display_mode = self._get_attr(element, "data-table-display-mode")

        return Table(
            width=width,
            layout=layout,
            local_id=local_id,
            display_mode=display_mode,
            children=self._parse_children(element),
        )

    def _parse_table_body(self, element: ET.Element) -> TableSection:
        """Parse semantic table section wrappers without losing their rows."""
        section_types = {
            "thead": TableSectionType.HEAD,
            "tbody": TableSectionType.BODY,
            "tfoot": TableSectionType.FOOT,
        }
        return TableSection(type=section_types[self._get_tag_name(element)], children=self._parse_children(element))

    def _parse_table_row(self, element: ET.Element) -> TableRow:
        """Parse tr elements."""
        return TableRow(children=self._parse_children(element))

    def _parse_table_cell(self, element: ET.Element) -> TableCell:
        """Parse th/td elements."""
        tag = self._get_tag_name(element)
        rowspan = self._get_attr(element, "rowspan")
        colspan = self._get_attr(element, "colspan")
        styles = self._parse_css_styles(element)

        return TableCell(
            is_header=tag == "th",
            rowspan=int(rowspan) if rowspan else None,
            colspan=int(colspan) if colspan else None,
            styles=styles,
            children=self._parse_children(element),
        )

    def _parse_macro(self, element: ET.Element) -> Node | None:
        """Parse simple macros by dispatching to specific handlers."""
        name = self._get_attr(element, "name") or ""
        custom_parser = self._custom_macro_parsers.get(name)
        if custom_parser:
            return custom_parser(element, ParserContext(self))
        parser = self._macro_parsers.get(name)

        if parser:
            return parser(element)

        return self._handle_unknown_macro(element, name)

    def _parse_structured_macro(self, element: ET.Element) -> Node | None:
        """Parse structured macros by dispatching to specific handlers."""
        name = self._get_attr(element, "name") or ""
        custom_parser = self._custom_macro_parsers.get(name)
        if custom_parser:
            return custom_parser(element, ParserContext(self))
        parser = self._macro_parsers.get(name)

        if parser:
            return parser(element)

        return self._handle_unknown_macro(element, name)

    def _handle_unknown_macro(self, element: ET.Element, name: str) -> Node | None:
        if self.unknown_content == UnknownContentPolicy.PRESERVE:
            self._add_diagnostic(
                code="preserved_unknown_macro",
                severity="warning",
                message=f"Preserved unknown macro {name!r}",
                local_name=name,
                namespace=self.NS_AC,
            )
            return self._parse_generic_macro(element, name)

        severity = "error" if self.unknown_content == UnknownContentPolicy.ERROR else "warning"
        code = "unknown_macro" if severity == "error" else "dropped_unknown_macro"
        self._add_diagnostic(
            code=code,
            severity=severity,
            message=f"Unknown macro {name!r}",
            local_name=name,
            namespace=self.NS_AC,
        )
        return None

    def _parse_generic_macro(self, element: ET.Element, name: str) -> GenericMacro:
        parameters = [
            MacroParameter(
                name=self._get_attr(parameter, "name") or "",
                value=self._extract_text_content(parameter),
                children=self._parse_children(parameter),
            )
            for parameter in self._iter_parameters(element)
        ]

        rich_text_body = self._find_child_by_tag(element, "rich-text-body")
        plain_text_body = self._find_child_by_tag(element, "plain-text-body")
        if rich_text_body is not None:
            body_kind = MacroBodyKind.RICH_TEXT
            children = self._parse_children(rich_text_body)
            plain_text = None
        elif plain_text_body is not None:
            body_kind = MacroBodyKind.PLAIN_TEXT
            children = []
            plain_text = self._extract_text_content(plain_text_body)
        else:
            body_kind = MacroBodyKind.NONE
            children = []
            plain_text = None

        return GenericMacro(
            name=name,
            storage_element=self._get_tag_name(element),
            schema_version=self._get_attr(element, "schema-version"),
            macro_id=self._get_attr(element, "macro-id"),
            parameters=parameters,
            body_kind=body_kind,
            plain_text_body=plain_text,
            attributes=dict(element.attrib),
            children=children,
        )

    def _parse_adf_extension(self, element: ET.Element) -> Node | None:
        """Parse ADF extension elements that can contain various types of content."""
        adf_node = self._find_child_by_tag(element, "adf-node")
        if adf_node is None:
            return None

        node_type = self._get_attr(adf_node, "type")

        if node_type == "panel":
            return self._parse_adf_panel(adf_node)
        elif node_type == "decision-list":
            return self._parse_adf_decision_list(adf_node)
        elif node_type == "decision-item":
            return self._parse_adf_decision_item(adf_node)

        self._add_diagnostic(
            code="unknown_adf_node_type",
            severity="error",
            message=f"Unknown ADF node type {node_type!r}",
            local_name=node_type,
            namespace=self.NS_AC,
        )
        return None

    def _parse_adf_panel(self, adf_node: ET.Element) -> PanelMacro:
        """Parse ADF panel node into PanelMacro."""
        panel_type_name = "panel"
        bg_color = None

        for attr_elem in adf_node:
            if self._get_tag_name(attr_elem) == "adf-attribute":
                key = self._get_attr(attr_elem, "key")
                value = self._extract_text_content(attr_elem)

                if key == "panel-type":
                    panel_type_name = value
                elif key == "bg-color" or key == "bgColor":
                    bg_color = value

        if panel_type_name == "note":
            panel_type = PanelMacroType.NOTE
        else:
            panel_type = PanelMacroType.PANEL

        children = []
        adf_content = self._find_child_by_tag(adf_node, "adf-content")
        if adf_content is not None:
            children = self._parse_children(adf_content)

        return PanelMacro(
            type=panel_type,
            bg_color=bg_color,
            panel_icon=None,
            panel_icon_id=None,
            panel_icon_text=None,
            children=children,
        )

    def _parse_adf_decision_list(self, adf_node: ET.Element) -> DecisionList:
        """Parse ADF decision-list node into DecisionList."""
        local_id = None

        for attr_elem in adf_node:
            if self._get_tag_name(attr_elem) == "adf-attribute":
                key = self._get_attr(attr_elem, "key")
                value = self._extract_text_content(attr_elem)

                if key == "local-id":
                    local_id = value

        children = []
        for child in adf_node:
            if self._get_tag_name(child) == "adf-node":
                decision_item = self._parse_adf_decision_item(child)
                if decision_item:
                    children.append(decision_item)

        return DecisionList(local_id=local_id, children=children)

    def _parse_adf_decision_item(self, adf_node: ET.Element) -> DecisionListItem:
        """Parse ADF decision-item node into DecisionListItem."""
        local_id = None
        state = None

        for attr_elem in adf_node:
            if self._get_tag_name(attr_elem) == "adf-attribute":
                key = self._get_attr(attr_elem, "key")
                value = self._extract_text_content(attr_elem)

                if key == "local-id":
                    local_id = value
                elif key == "state":
                    if value in ["DECIDED", "PENDING"]:
                        state = DecisionListItemState(value)

        children = []
        adf_content = self._find_child_by_tag(adf_node, "adf-content")
        if adf_content is not None:
            children = self._parse_children(adf_content)

        return DecisionListItem(local_id=local_id, state=state, children=children)

    def _parse_panel_macro(self, element: ET.Element) -> PanelMacro:
        """Parse panel macro elements (panel, tip, note, warning, info)."""
        name = self._get_attr(element, "name") or ""

        if name == "tip":
            panel_type = PanelMacroType.SUCCESS
        elif name == "note":
            panel_type = PanelMacroType.WARNING
        elif name == "warning":
            panel_type = PanelMacroType.ERROR
        elif name == "info":
            panel_type = PanelMacroType.INFO
        else:
            panel_type = PanelMacroType.PANEL

        bg_color = None
        panel_icon = None
        panel_icon_id = None
        panel_icon_text = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "bgColor":
                bg_color = param_value
            elif param_name == "panelIcon":
                panel_icon = param_value
            elif param_name == "panelIconId":
                panel_icon_id = param_value
            elif param_name == "panelIconText":
                panel_icon_text = param_value

        children = []
        rich_text_body = self._find_child_by_tag(element, "rich-text-body")
        if rich_text_body is not None:
            children = self._parse_children(rich_text_body)

        return PanelMacro(
            type=panel_type,
            bg_color=bg_color,
            panel_icon=panel_icon,
            panel_icon_id=panel_icon_id,
            panel_icon_text=panel_icon_text,
            children=children,
        )

    def _parse_code_macro(self, element: ET.Element) -> CodeMacro:
        """Parse code macro elements."""
        language = None
        breakout_mode = None
        breakout_width = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "language":
                language = param_value
            elif param_name == "breakoutMode":
                breakout_mode = param_value
            elif param_name == "breakoutWidth":
                breakout_width = param_value

        code = ""
        plain_text_body = self._find_child_by_tag(element, "plain-text-body")
        if plain_text_body is not None:
            code = self._extract_text_content(plain_text_body)

        return CodeMacro(language=language, breakout_mode=breakout_mode, breakout_width=breakout_width, code=code)

    def _parse_details_macro(self, element: ET.Element) -> DetailsMacro:
        """Parse details macro elements."""
        children = []
        rich_text_body = self._find_child_by_tag(element, "rich-text-body")
        if rich_text_body is not None:
            children = self._parse_children(rich_text_body)

        return DetailsMacro(children=children)

    def _parse_expand_macro(self, element: ET.Element) -> ExpandMacro:
        """Parse expand macro elements."""
        title = None
        breakout_width = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "title":
                title = param_value
            elif param_name == "breakoutWidth":
                breakout_width = param_value

        children = []
        rich_text_body = self._find_child_by_tag(element, "rich-text-body")
        if rich_text_body is not None:
            children = self._parse_children(rich_text_body)

        return ExpandMacro(title=title, breakout_width=breakout_width, children=children)

    def _parse_status_macro(self, element: ET.Element) -> StatusMacro:
        """Parse status macro elements."""
        title = None
        colour = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "title":
                title = param_value
            elif param_name == "colour":
                colour = param_value

        return StatusMacro(title=title, colour=colour)

    def _parse_toc_macro(self, element: ET.Element) -> TocMacro:
        """Parse table of contents macro elements."""
        style = None
        toc_type = None
        min_level = None
        max_level = None
        printable = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "style":
                style = param_value
            elif param_name == "type":
                toc_type = param_value
            elif param_name in {"minLevel", "maxLevel"}:
                try:
                    level = min(6, max(1, int(param_value)))
                except ValueError:
                    continue
                if param_name == "minLevel":
                    min_level = level
                else:
                    max_level = level
            elif param_name == "printable":
                printable = param_value.lower() == "true"

        return TocMacro(
            style=style,
            toc_type=toc_type,
            min_level=min_level,
            max_level=max_level,
            printable=printable,
        )

    def _parse_jira_macro(self, element: ET.Element) -> JiraMacro:
        """Parse JIRA macro elements."""
        key = None
        server_id = None
        server = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "key":
                key = param_value
            elif param_name == "serverId":
                server_id = param_value
            elif param_name == "server":
                server = param_value

        return JiraMacro(key=key, server_id=server_id, server=server)

    def _parse_include_macro(self, element: ET.Element) -> IncludeMacro:
        """Parse include macro elements."""
        children = []
        space_key = None
        content_title = None
        version_at_save = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            if param_name == "":
                children = self._parse_children(param)
                for child in children:
                    if hasattr(child, "space_key"):
                        space_key = child.space_key
                    if hasattr(child, "content_title"):
                        content_title = child.content_title
                    if hasattr(child, "version_at_save"):
                        version_at_save = child.version_at_save

        return IncludeMacro(
            space_key=space_key, content_title=content_title, version_at_save=version_at_save, children=children
        )

    def _parse_tasks_report_macro(self, element: ET.Element) -> TasksReportMacro:
        """Parse tasks-report-macro elements."""
        spaces = None
        is_missing_required_parameters = False

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "spaces":
                spaces = param_value
            elif param_name == "isMissingRequiredParameters":
                is_missing_required_parameters = param_value.lower() == "true"

        return TasksReportMacro(spaces=spaces, is_missing_required_parameters=is_missing_required_parameters)

    def _parse_excerpt_include_macro(self, element: ET.Element) -> ExcerptIncludeMacro:
        """Parse excerpt-include macro elements."""
        children = []
        space_key = None
        content_title = None
        posting_day = None
        version_at_save = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            if param_name == "":
                children = self._parse_children(param)
                for child in children:
                    if hasattr(child, "space_key"):
                        space_key = child.space_key
                    if hasattr(child, "content_title"):
                        content_title = child.content_title
                    if hasattr(child, "posting_day"):
                        posting_day = child.posting_day
                    if hasattr(child, "version_at_save"):
                        version_at_save = child.version_at_save

        return ExcerptIncludeMacro(
            space_key=space_key,
            content_title=content_title,
            posting_day=posting_day,
            version_at_save=version_at_save,
            children=children,
        )

    def _parse_attachments_macro(self, element: ET.Element) -> AttachmentsMacro:
        """Parse attachments macro elements."""
        return AttachmentsMacro()

    def _parse_viewpdf_macro(self, element: ET.Element) -> ViewPdfMacro:
        """Parse viewpdf macro elements."""
        filename = None
        version_at_save = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            if param_name == "name":
                for child in param:
                    if self._get_tag_name(child) == "attachment":
                        filename = self._get_attr(child, "filename")
                        version_at_save = self._get_attr(child, "version-at-save")

        return ViewPdfMacro(filename=filename, version_at_save=version_at_save)

    def _parse_view_file_macro(self, element: ET.Element) -> ViewFileMacro:
        """Parse view-file macro elements."""
        filename = None
        version_at_save = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            if param_name == "name":
                for child in param:
                    if self._get_tag_name(child) == "attachment":
                        filename = self._get_attr(child, "filename")
                        version_at_save = self._get_attr(child, "version-at-save")

        return ViewFileMacro(filename=filename, version_at_save=version_at_save)

    def _parse_profile_macro(self, element: ET.Element) -> ProfileMacro:
        """Parse profile macro elements."""
        children = []
        account_id = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            if param_name == "user":
                children = self._parse_children(param)
                for child in children:
                    if hasattr(child, "account_id"):
                        account_id = child.account_id

        return ProfileMacro(account_id=account_id, children=children)

    def _parse_anchor_macro(self, element: ET.Element) -> AnchorMacro:
        """Parse anchor macro elements."""
        anchor_name = None

        for param in self._iter_parameters(element):
            param_name = self._get_attr(param, "name")
            param_value = self._extract_text_content(param)

            if param_name == "":
                anchor_name = param_value

        return AnchorMacro(anchor_name=anchor_name)

    def _parse_excerpt_macro(self, element: ET.Element) -> ExcerptMacro:
        """Parse excerpt macro elements."""
        children = []
        rich_text_body = self._find_child_by_tag(element, "rich-text-body")
        if rich_text_body is not None:
            children = self._parse_children(rich_text_body)

        return ExcerptMacro(children=children)

    def _get_tag_name(self, element: ET.Element) -> str:
        """Extract tag name without namespace prefix."""
        tag = element.tag
        return tag.split("}", 1)[1] if "}" in tag else tag

    def _get_namespace(self, element: ET.Element) -> str | None:
        tag = element.tag
        return tag[1:].split("}", 1)[0] if tag.startswith("{") and "}" in tag else None

    def _get_attr(self, element: ET.Element, attr_name: str) -> str | None:
        """Get attribute value handling multiple namespace variants."""
        value = element.attrib.get(attr_name)
        if value is not None:
            return value

        for ns in [self.NS_AC, self.NS_RI, self.NS_AT]:
            value = element.attrib.get(f"{{{ns}}}{attr_name}")
            if value is not None:
                return value

        return None

    def _find_child_by_tag(self, element: ET.Element, tag_name: str) -> ET.Element | None:
        """Find first direct child with given tag name."""
        for child in element:
            if self._get_tag_name(child) == tag_name:
                return child
        return None

    def _extract_text_content(self, element: ET.Element) -> str:
        """Extract all text content from element and descendants."""
        parts: list[str] = []

        if element.text:
            parts.append(element.text)

        for child in element:
            parts.append(self._extract_text_content(child))
            if child.tail:
                parts.append(child.tail)

        return "".join(parts)

    def _iter_parameters(self, element: ET.Element) -> Iterator[ET.Element]:
        """Iterate over parameter children of a macro element."""
        for child in element:
            if self._get_tag_name(child) == "parameter":
                yield child

    def _parse_css_styles(self, element: ET.Element) -> dict[str, str]:
        """Parse all CSS styles from element's style attribute."""
        style_attr = self._get_attr(element, "style") or ""
        styles = {}

        for declaration in style_attr.split(";"):
            if ":" in declaration:
                prop, value = declaration.split(":", 1)
                prop = prop.strip().lower()
                value = value.strip()

                if prop and value:
                    styles[prop] = value

        return styles
