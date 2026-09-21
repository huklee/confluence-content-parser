from __future__ import annotations

import html
from abc import ABC
from collections.abc import Iterator
from enum import Enum
from typing import Any, TypeVar, overload

from pydantic import BaseModel, Field

T1 = TypeVar("T1", bound="Node")
T2 = TypeVar("T2", bound="Node")
T3 = TypeVar("T3", bound="Node")
T4 = TypeVar("T4", bound="Node")
T5 = TypeVar("T5", bound="Node")


class Node(BaseModel, ABC):
    """Base class for all content nodes in the Confluence document tree."""

    is_block_level: bool = False

    def walk(self) -> Iterator[Node]:
        """Walk through this node and all its descendants."""
        yield self
        for child in self.get_children():
            yield from child.walk()

    def get_children(self) -> list[Node]:
        """Get direct children of this node. Override in subclasses."""
        return []

    def to_text(self) -> str:
        """Get text representation of this node. Override in subclasses."""
        return ""

    @overload
    def find_all(self) -> list[Node]: ...

    @overload
    def find_all(self, node_type: type[T1]) -> list[T1]: ...

    @overload
    def find_all(self, t1: type[T1], t2: type[T2]) -> tuple[list[T1], list[T2]]: ...

    @overload
    def find_all(self, t1: type[T1], t2: type[T2], t3: type[T3]) -> tuple[list[T1], list[T2], list[T3]]: ...

    @overload
    def find_all(
        self, t1: type[T1], t2: type[T2], t3: type[T3], t4: type[T4]
    ) -> tuple[list[T1], list[T2], list[T3], list[T4]]: ...

    @overload
    def find_all(
        self, t1: type[T1], t2: type[T2], t3: type[T3], t4: type[T4], t5: type[T5]
    ) -> tuple[list[T1], list[T2], list[T3], list[T4], list[T5]]: ...

    def find_all(self, *node_types) -> Any:  # type: ignore[no-untyped-def,misc]
        """Find all nodes of specific type(s) in this subtree with modern variadic generics.

        Args:
            *node_types: Either no arguments (all nodes), a single node class, or multiple node classes.

        Returns:
            - No arguments: list[Node] (all nodes)
            - Single type: list[T] where T is the requested type
            - Multiple types: tuple of lists with proper typing for each type

        Examples:
            # All nodes
            all_nodes = node.find_all()

            # Single type - returns list[HeadingElement]
            headings = node.find_all(HeadingElement)

            # Multiple types - returns tuple with proper typing
            headings, panels = node.find_all(HeadingElement, PanelMacro)
            headings, panels, links = node.find_all(HeadingElement, PanelMacro, LinkElement)
        """
        if len(node_types) == 0:
            return list(self.walk())

        if len(node_types) == 1:
            node_type = node_types[0]
            results = []
            for node in self.walk():
                if isinstance(node, node_type):
                    results.append(node)
            return results

        result_lists: list[list[Node]] = [[] for _ in node_types]
        for node in self.walk():
            for i, node_type in enumerate(node_types):
                if isinstance(node, node_type):
                    result_lists[i].append(node)

        return tuple(result_lists)


class ContainerElement(Node):
    """Base for container elements."""

    children: list[Node] = Field(default_factory=list)
    styles: dict[str, str] = Field(default_factory=dict)

    def get_children(self) -> list[Node]:
        return self.children

    def to_text(self) -> str:
        parts = []
        for child in self.children:
            child_text = child.to_text()
            if clean_child_text := child_text.strip():
                parts.append(clean_child_text)

        if self._has_block_children():
            return "\n\n".join(parts)
        else:
            return " ".join(parts)

    def _has_block_children(self) -> bool:
        """Check if this container has block-level children that should be separated by newlines."""
        return any(child.is_block_level for child in self.children)


class Fragment(ContainerElement):
    """Neutral container for multiple top-level nodes (non-rendering)."""

    pass


class GenericElement(ContainerElement):
    """Lossless container for a well-formed element without a typed parser."""

    local_name: str
    namespace: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class LayoutSectionType(Enum):
    """Type of layout section."""

    SINGLE = "single"
    FIXED_WIDTH = "fixed-width"
    TWO_EQUAL = "two_equal"
    TWO_LEFT_SIDEBAR = "two_left_sidebar"
    TWO_RIGHT_SIDEBAR = "two_right_sidebar"
    THREE_EQUAL = "three_equal"
    THREE_WITH_SIDEBARS = "three_with_sidebars"
    THREE_LEFT_SIDEBARS = "three_left_sidebars"
    THREE_RIGHT_SIDEBARS = "three_right_sidebars"
    FOUR_EQUAL = "four_equal"
    FIVE_EQUAL = "five_equal"


class LayoutElement(ContainerElement):
    """A page layout container containing sections."""

    is_block_level: bool = True


class LayoutSection(ContainerElement):
    """A layout section (row) containing cells."""

    section_type: LayoutSectionType
    breakout_mode: str | None = None
    breakout_width: str | None = None
    is_block_level: bool = True


class LayoutCell(ContainerElement):
    """A layout cell (column) containing content."""

    is_block_level: bool = True


class HeadingType(Enum):
    """Type of heading element."""

    H1 = "h1"
    H2 = "h2"
    H3 = "h3"
    H4 = "h4"
    H5 = "h5"
    H6 = "h6"


class HeadingElement(ContainerElement):
    """A heading element."""

    type: HeadingType
    is_block_level: bool = True


class TextEffectType(Enum):
    """Type of inline element."""

    STRONG = "strong"
    EMPHASIS = "em"
    UNDERLINE = "u"
    STRIKETHROUGH = "del"
    MONOSPACE = "code"
    SUBSCRIPT = "sub"
    SUPERSCRIPT = "sup"
    BLOCKQUOTE = "blockquote"
    SPAN = "span"


class TextEffectElement(ContainerElement):
    """Base for inline formatting elements like bold, italic, etc."""

    type: TextEffectType


class TextBreakType(Enum):
    """Type of text break element."""

    PARAGRAPH = "p"
    LINE_BREAK = "br"
    HORIZONTAL_RULE = "hr"


class TextBreakElement(ContainerElement):
    """A text break element."""

    type: TextBreakType
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of text break elements."""
        if self.type == TextBreakType.HORIZONTAL_RULE:
            return "---"
        elif self.type == TextBreakType.LINE_BREAK:
            return "\n"
        else:
            return super().to_text()


class ListType(Enum):
    """Type of list element."""

    UNORDERED = "ul"
    ORDERED = "ol"
    TASK = "task-list"


class ListElement(ContainerElement):
    """A list element."""

    type: ListType
    start: int | None = None
    is_block_level: bool = True

    def to_text(self, indent_level: int = 0) -> str:
        """Convert list to text with appropriate markers and indentation."""
        if not self.children:
            return ""

        return self._format_items(self.children, indent_level)

    def _format_items(self, items: list[ListItem | ListElement | Node], indent_level: int) -> str:
        """Recursively format list items with proper indentation."""
        parts = []
        item_number = self.start or 1
        indent = "  " * indent_level

        for item in items:
            if isinstance(item, ListItem):
                content_parts = []
                nested_lists = []

                for child in item.children:
                    if isinstance(child, ListElement):
                        nested_lists.append(child)
                    else:
                        child_text = child.to_text().strip()
                        if child_text:
                            content_parts.append(child_text)

                content = " ".join(content_parts)

                if item.status is not None:
                    marker = "✓" if item.status == TaskListItemStatus.COMPLETE else "○"
                    parts.append(f"{indent}{marker} {content}")
                elif self.type == ListType.UNORDERED:
                    parts.append(f"{indent}• {content}")
                elif self.type == ListType.ORDERED:
                    parts.append(f"{indent}{item_number}. {content}")
                    item_number += 1
                else:
                    parts.append(f"{indent}{content}")

                for nested_list in nested_lists:
                    nested_text = nested_list.to_text(indent_level + 1)
                    if nested_text:
                        parts.append(nested_text)

            elif isinstance(item, ListElement):
                nested_text = item.to_text(indent_level + 1)
                if nested_text:
                    parts.append(nested_text)
            else:
                child_text = item.to_text().strip()
                if child_text:
                    parts.append(f"{indent}{child_text}")

        return "\n".join(parts)


class TaskListItemStatus(Enum):
    """Type of task list item status."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class ListItem(ContainerElement):
    """A list item element that can be regular or task item."""

    task_id: str | None = None
    uuid: str | None = None
    status: TaskListItemStatus | None = None
    is_block_level: bool = True


class LinkType(Enum):
    """Type of link element."""

    EXTERNAL = "a"
    MAILTO = "mailto"
    SPACE = "ri:space"
    PAGE = "ri:page"
    BLOG_POST = "ri:blog-post"
    USER = "ri:user"
    ATTACHMENT = "ri:attachment"
    ANCHOR = "ac:anchor"


class LinkElement(ContainerElement):
    """A link element."""

    type: LinkType
    href: str | None = None
    anchor: str | None = None

    space_key: str | None = None
    content_title: str | None = None
    posting_day: str | None = None
    version_at_save: str | None = None
    account_id: str | None = None
    filename: str | None = None

    def to_text(self) -> str:
        """Extract text from rich content or href."""
        if not self.children:
            return self.href or ""

        resource_parts = []
        content_parts = []

        for child in self.children:
            child_text = child.to_text().strip()
            if child_text:
                if hasattr(child, "type") and hasattr(child.type, "value"):
                    resource_parts.append(child_text)
                else:
                    content_parts.append(child_text)

        if resource_parts and content_parts:
            resource_text = " ".join(resource_parts)
            content_text = " ".join(content_parts)

            return f"{resource_text} {content_text}"
        elif resource_parts:
            return " ".join(resource_parts)
        elif content_parts:
            return " ".join(content_parts)
        else:
            return self.href or ""


class Image(ContainerElement):
    """An image element."""

    src: str | None = None
    alt: str | None = None
    title: str | None = None
    width: str | None = None
    height: str | None = None
    alignment: str | None = None
    layout: str | None = None
    original_height: str | None = None
    original_width: str | None = None
    custom_width: bool | None = None

    filename: str | None = None
    version_at_save: str | None = None

    url_value: str | None = None

    def to_text(self) -> str:
        """Generate text representation with caption if present."""
        image_text = f"🖼️ Image: {self.alt or self.src or self.filename or self.url_value or 'Unknown'}"

        if self.children:
            caption_text = "".join(child.to_text() for child in self.children)
            if caption_text.strip():
                return f"{image_text}\nCaption: {caption_text.strip()}"

        return image_text


class Table(ContainerElement):
    """A table element with metadata and rows."""

    width: str | None = None
    layout: str | None = None
    local_id: str | None = None
    display_mode: str | None = None

    def to_text(self) -> str:
        """Generate text representation of table."""
        if not self.children:
            return ""

        lines = []
        for row in self.children:
            row_text = row.to_text()
            if clean_row_text := row_text.strip():
                lines.append(clean_row_text)

        return "\n".join(lines)


class TableSectionType(Enum):
    """Semantic section of an HTML-like table."""

    HEAD = "head"
    BODY = "body"
    FOOT = "foot"


class TableSection(Fragment):
    """A table header, body, or footer section."""

    type: TableSectionType
    is_block_level: bool = True

    def to_text(self) -> str:
        return "\n".join(text for child in self.children if (text := child.to_text().strip()))


class TableRow(ContainerElement):
    """A table row."""

    is_block_level: bool = True

    def to_text(self) -> str:
        """Format row as text with | separators."""
        if not self.children:
            return ""

        cell_texts = [child.to_text() for child in self.children]
        return " | ".join(cell_texts)


class TableCell(ContainerElement):
    """A table cell."""

    is_header: bool = False
    rowspan: int | None = None
    colspan: int | None = None


class Emoticon(Node):
    """An emoticon element."""

    name: str
    emoji_shortname: str | None = None
    emoji_id: str | None = None
    emoji_fallback: str | None = None

    def to_text(self) -> str:
        """Return the best text representation of the emoticon."""
        if self.emoji_fallback:
            return self.emoji_fallback
        elif self.emoji_shortname:
            return self.emoji_shortname
        else:
            return f":{self.name}:"


class Time(Node):
    """A time element with datetime."""

    datetime: str | None = None

    def to_text(self) -> str:
        """Generate text representation of time."""
        if self.datetime:
            return f"📅 {self.datetime}"
        else:
            return "📅 Date"


class ResourceIdentifierType(Enum):
    """Type of resource identifier."""

    PAGE = "page"
    BLOG_POST = "blog-post"
    ATTACHMENT = "attachment"
    URL = "url"
    SHORTCUT = "shortcut"
    USER = "user"
    SPACE = "space"
    CONTENT_ENTITY = "content-entity"


class ResourceIdentifier(Node):
    """A resource identifier element."""

    type: ResourceIdentifierType

    space_key: str | None = None
    content_title: str | None = None
    content_id: str | None = None

    posting_day: str | None = None
    filename: str | None = None
    value: str | None = None
    key: str | None = None
    parameter: str | None = None
    account_id: str | None = None
    local_id: str | None = None
    userkey: str | None = None
    version_at_save: str | None = None

    def to_text(self) -> str:
        """Generate appropriate text representation based on type."""
        if self.type == ResourceIdentifierType.PAGE:
            return "📄 Page"
        elif self.type == ResourceIdentifierType.BLOG_POST:
            return f"📝 Blog: {self.posting_day}" if self.posting_day else "📝 Blog"
        elif self.type == ResourceIdentifierType.ATTACHMENT:
            return f"📎 Attachment: {self.filename}" if self.filename else "📎 Attachment"
        elif self.type == ResourceIdentifierType.URL:
            return f"🔗 URL: {self.value}" if self.value else "🔗 URL"
        elif self.type == ResourceIdentifierType.USER:
            if self.account_id:
                return f"👤 User: {self.account_id}"
            elif self.userkey:
                return f"👤 User: {self.userkey}"
            else:
                return "👤 User"
        elif self.type == ResourceIdentifierType.SPACE:
            return f"🏠 Space: {self.space_key}" if self.space_key else "🏠 Space"
        elif self.type == ResourceIdentifierType.SHORTCUT:
            return f"🔗 Shortcut: {self.key}@{self.parameter}" if self.key and self.parameter else "🔗 Shortcut"
        elif self.type == ResourceIdentifierType.CONTENT_ENTITY:
            return f"📄 Content: {self.content_id}" if self.content_id else "📄 Content"


class PlaceholderElement(Node):
    """A placeholder element for content hints."""

    text: str

    def to_text(self) -> str:
        """Generate text representation of placeholder."""
        return f"💭 Placeholder: {self.text}"


class PanelMacroType(Enum):
    """Type of panel macro based on visual presentation."""

    PANEL = "panel"
    NOTE = "note"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class MacroBodyKind(str, Enum):
    """Storage representation used for a macro body."""

    NONE = "none"
    RICH_TEXT = "rich-text"
    PLAIN_TEXT = "plain-text"


class MacroParameter(BaseModel):
    """An ordered macro parameter, including any structured value nodes."""

    name: str
    value: str | None = None
    children: list[Node] = Field(default_factory=list)


class GenericMacro(ContainerElement):
    """Lossless representation of an unknown or app-provided macro."""

    name: str
    storage_element: str
    schema_version: str | None = None
    macro_id: str | None = None
    parameters: list[MacroParameter] = Field(default_factory=list)
    body_kind: MacroBodyKind = MacroBodyKind.NONE
    plain_text_body: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    is_block_level: bool = True

    def to_text(self) -> str:
        if self.body_kind == MacroBodyKind.PLAIN_TEXT:
            return self.plain_text_body or ""
        content = super().to_text()
        return content or f"[{self.name} macro]"


class DiagramMacro(Node):
    """Plaintext diagram source preserved without executing a renderer."""

    engine: str
    macro_name: str
    title: str | None = None
    source: str
    parameters: list[MacroParameter] = Field(default_factory=list)
    is_block_level: bool = True

    def to_text(self) -> str:
        return f"{self.title}\n{self.source}" if self.title else self.source


class TabMacro(ContainerElement):
    """One titled tab in a legacy nested tabs macro."""

    title: str
    is_block_level: bool = True


class TabsMacro(ContainerElement):
    """A legacy tabbed container with tabs retained in source order."""

    orientation: str | None = None
    is_block_level: bool = True

    @property
    def tabs(self) -> list[TabMacro]:
        return [child for child in self.children if isinstance(child, TabMacro)]


class PanelMacro(ContainerElement):
    """A panel macro element with background color and optional icon."""

    type: PanelMacroType
    bg_color: str | None = None
    panel_icon: str | None = None
    panel_icon_id: str | None = None
    panel_icon_text: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of panel with content."""
        content = super().to_text()

        if self.type == PanelMacroType.NOTE:
            return f"📝 NOTE: {content}" if content else "📝 NOTE"
        elif self.type == PanelMacroType.SUCCESS:
            return f"✅ SUCCESS: {content}" if content else "✅ SUCCESS"
        elif self.type == PanelMacroType.WARNING:
            return f"⚠️ WARNING: {content}" if content else "⚠️ WARNING"
        elif self.type == PanelMacroType.ERROR:
            return f"❌ ERROR: {content}" if content else "❌ ERROR"
        elif self.type == PanelMacroType.INFO:
            return f"ℹ️ INFO: {content}" if content else "ℹ️ INFO"
        elif self.type == PanelMacroType.PANEL:
            if self.panel_icon_text:
                return f"{self.panel_icon_text} {content}" if content else self.panel_icon_text
            else:
                return f"📋 PANEL: {content}" if content else "📋 PANEL"


class CodeMacro(Node):
    """A code macro element with syntax highlighting."""

    language: str | None = None
    breakout_mode: str | None = None
    breakout_width: str | None = None
    code: str
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of code block."""
        if self.language:
            return f"```{self.language}\n{self.code}\n```"
        else:
            return f"```\n{self.code}\n```"


class ExpandMacro(ContainerElement):
    """An expand/collapse macro element."""

    title: str | None = None
    breakout_width: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of expand macro."""
        content = super().to_text()
        title = self.title or "Expand"
        return f"▶ {title}\n{content}" if content else f"▶ {title}"


class StatusMacro(Node):
    """A status macro element with title and color."""

    title: str | None = None
    colour: str | None = None

    def to_text(self) -> str:
        """Generate text representation of status."""
        title = self.title or "Status"
        if self.colour:
            return f"🏷️ Status: {title} ({self.colour})"
        else:
            return f"🏷️ Status: {title}"


class TocMacro(Node):
    """A table of contents macro element."""

    style: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of table of contents."""
        return "📋 Table of Contents"


class JiraMacro(Node):
    """A JIRA issue macro element."""

    key: str | None = None
    server_id: str | None = None
    server: str | None = None

    def to_text(self) -> str:
        """Generate text representation of JIRA issue."""
        if self.key:
            if self.server and self.server != "System Jira":
                return f"🎫 {self.key} ({self.server})"
            else:
                return f"🎫 {self.key}"
        else:
            return "🎫 JIRA Issue"


class IncludeMacro(ContainerElement):
    """An include macro element for including other pages."""

    space_key: str | None = None
    content_title: str | None = None
    version_at_save: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of include macro."""
        if self.content_title:
            return f"📄 Include: {self.content_title}"
        else:
            return "📄 Include Page"


class TasksReportMacro(Node):
    """A tasks report macro element."""

    spaces: str | None = None
    is_missing_required_parameters: bool = False
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of tasks report."""
        if self.spaces:
            return f"📊 Tasks Report: {self.spaces}"
        else:
            return "📊 Tasks Report"


class ExcerptIncludeMacro(ContainerElement):
    """An excerpt include macro element."""

    space_key: str | None = None
    content_title: str | None = None
    posting_day: str | None = None
    version_at_save: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of excerpt include."""
        if self.content_title:
            if self.posting_day:
                return f"📝 Excerpt: {self.content_title} ({self.posting_day})"
            else:
                return f"📝 Excerpt: {self.content_title}"
        else:
            return "📝 Excerpt Include"


class AttachmentsMacro(Node):
    """An attachments macro element for listing page attachments."""

    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of attachments macro."""
        return "📎 Attachments"


class ViewPdfMacro(Node):
    """A view PDF macro element."""

    filename: str | None = None
    version_at_save: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of PDF viewer."""
        if self.filename:
            return f"📄 PDF: {self.filename}"
        else:
            return "📄 PDF Viewer"


class ViewFileMacro(Node):
    """A view file macro element for displaying files inline."""

    filename: str | None = None
    version_at_save: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of file viewer."""
        if self.filename:
            return f"📁 File: {self.filename}"
        else:
            return "📁 File Viewer"


class ProfileMacro(ContainerElement):
    """A profile macro element for displaying user profiles."""

    account_id: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of profile macro."""
        if self.account_id:
            return f"👤 Profile: {self.account_id}"
        else:
            return "👤 User Profile"


class AnchorMacro(Node):
    """An anchor macro element for creating page anchors."""

    anchor_name: str | None = None

    def to_text(self) -> str:
        """Generate text representation of anchor."""
        if self.anchor_name:
            return f"⚓ Anchor: {self.anchor_name}"
        else:
            return "⚓ Anchor"


class ExcerptMacro(ContainerElement):
    """An excerpt macro element for marking excerptable content."""

    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of excerpt."""
        content = super().to_text()
        return f"📄 Excerpt: {content}" if content else "📄 Excerpt"


class DecisionListItemState(Enum):
    """State of decision list item."""

    DECIDED = "DECIDED"
    PENDING = "PENDING"


class DecisionList(ContainerElement):
    """A decision list element containing decision items."""

    local_id: str | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of decision list."""
        if not self.children:
            return "📋 Decision List"

        parts = []
        for child in self.children:
            child_text = child.to_text().strip()
            if child_text:
                parts.append(child_text)

        return "\n".join(parts) if parts else "📋 Decision List"


class DetailsMacro(ContainerElement):
    """A details macro element for collapsible content sections."""

    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of details macro."""
        content = super().to_text()
        return f"📋 Details: {content}" if content else "📋 Details"


class DecisionListItem(ContainerElement):
    """A decision item element."""

    local_id: str | None = None
    state: DecisionListItemState | None = None
    is_block_level: bool = True

    def to_text(self) -> str:
        """Generate text representation of decision item."""
        content = super().to_text()
        if self.state == DecisionListItemState.DECIDED:
            return f"✅ {content}" if content else "✅"
        else:
            return f"⏳ {content}" if content else "⏳"


class Text(Node):
    """A node containing plain text content."""

    text: str

    def to_text(self) -> str:
        return html.unescape(self.text)
