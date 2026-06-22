# coding: utf-8
# virtualBufferTableBraille.py - Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush CLAUSE, released under GPL.
"""Display virtual-buffer table rows on one braille line, one region per cell."""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any, Literal

import addonHandler
import api
import braille
import config
import core
import louis
import textInfos
import ui
from config.configFlags import ReportTableHeaders, TetherTo
from logHandler import log
from virtualBuffers import VirtualBuffer

from .documentformatting import (
	apply_braille_region_post_translation_extras,
	build_text_with_fields_format_config,
)
from .autoscroll import stop_nvda_core_autoscroll

try:
	from .objectpresentation import get_roleLabel
except ImportError:
	get_roleLabel = None  # type: ignore[assignment,misc]

try:
	from documentBase import DocumentWithTableNavigation
except ImportError:
	DocumentWithTableNavigation = None  # type: ignore[assignment,misc]

try:
	from virtualBuffers.gecko_ia2 import Gecko_ia2
except ImportError:
	Gecko_ia2 = None  # type: ignore[assignment,misc]

from .utils import get_control_type

addonHandler.initTranslation()

ROW_CELL_SEPARATOR = " | "
ROW_LINE_START = "(| "
ROW_LINE_END = " |)"


def _virtualDocumentConf():
	return config.conf["brailleExtender"]["virtualDocument"]


def _tableRowBrailleMarkers() -> tuple[str, str, str]:
	vd = _virtualDocumentConf()
	cellSeparator = vd["cellSeparator"]
	lineStart = vd["lineStart"]
	lineEnd = vd["lineEnd"]
	if not cellSeparator:
		cellSeparator = ROW_CELL_SEPARATOR
	if lineStart is None:
		lineStart = ROW_LINE_START
	if lineEnd is None:
		lineEnd = ROW_LINE_END
	return cellSeparator, lineStart, lineEnd


def _cellBrailleFormatConfig() -> dict[str, Any]:
	return build_text_with_fields_format_config(suppress_table_cell_coords=True)


def _tableRowCount(
	virtualBuffer,
	cellInfo: textInfos.TextInfo,
	*,
	tableID: int | None,
) -> int | None:
	dims = _getVirtualBufferTableDimensions(virtualBuffer, cellInfo, tableID=tableID)
	return dims[0] if dims is not None else None


TableRowRoutingZone = Literal["content", "row", "column"]


@dataclass(frozen=True)
class _TableRowCellBrailleLayout:
	"""Non-content markers around one table-row cell segment (Excel-style)."""

	tableBoundaryPrefix: str = ""
	lineStart: str = ""
	cellSeparator: str = ""
	lineEnd: str = ""
	tableBoundarySuffix: str = ""

	@property
	def displayPrefix(self) -> str:
		return self.tableBoundaryPrefix + (self.lineStart or self.cellSeparator)

	@property
	def displaySuffix(self) -> str:
		return self.lineEnd + self.tableBoundarySuffix

	def routingZoneAt(self, rawPos: int, contentLen: int) -> TableRowRoutingZone:
		prefixLen = len(self.displayPrefix)
		if rawPos < prefixLen:
			if rawPos < len(self.tableBoundaryPrefix):
				return "content"
			if self.lineStart or self.cellSeparator:
				return "column"
			return "content"
		if rawPos >= prefixLen + contentLen:
			if rawPos < prefixLen + contentLen + len(self.lineEnd):
				return "row"
			return "content"
		return "content"


_TABLE_ROW_COORD_FLASH_ATTR = "_beTableRowCoordFlash"


def _queueTableRowCoordFlash(message: str) -> None:
	"""Queue a coordinate flash for ui.message after BrailleHandler.routeTo completes."""
	handler = braille.handler
	if handler is None:
		return
	setattr(handler, _TABLE_ROW_COORD_FLASH_ATTR, message)


def _clearTableRowCoordFlash() -> None:
	handler = braille.handler
	if handler is None:
		return
	try:
		delattr(handler, _TABLE_ROW_COORD_FLASH_ATTR)
	except AttributeError:
		pass


def _virtualBufferTableBraille_routeTo(self, windowPos) -> None:
	"""Show table-row coordinate flashes via ui.message after NVDA's routing dismiss step."""
	stop_nvda_core_autoscroll(self)
	_clearTableRowCoordFlash()
	self.buffer.routeTo(windowPos)
	pending = getattr(self, _TABLE_ROW_COORD_FLASH_ATTR, None)
	_clearTableRowCoordFlash()
	if self.buffer is self.messageBuffer:
		self._dismissMessage()
	if pending:
		ui.message(pending)


def _resyncTableRowBrailleAfterMessageDismiss() -> None:
	"""After ui.message times out, re-scroll the table row on mainBuffer (not messageBuffer)."""
	handler = braille.handler
	if handler is None or not handler.enabled or handler.buffer is not handler.mainBuffer:
		return
	virtualBuffer = _virtualBufferForActiveTableRowBraille(handler)
	if virtualBuffer is None:
		return
	tableRegions = _cellRegionsForBuffer(handler.mainBuffer.regions, virtualBuffer)
	primaryFocus = _primaryTableRowFocusRegion(tableRegions, virtualBuffer)
	if primaryFocus is None:
		handler.update()
		return
	_focusAndScrollTableRowRegion(handler, handler.mainBuffer, primaryFocus)
	handler.update()


def _appendFlashDetail(message: str, detail: str) -> str:
	detail = detail.strip()
	if not detail:
		return message
	# Translators: Extra detail appended to a table coordinate flash (e.g. row 2 (column 3)).
	return _("{main} ({detail})").format(main=message, detail=detail)


def _normalizeTableHeaderText(text: str | None) -> str | None:
	if not text:
		return None
	normalized = " ".join(line.strip() for line in text.splitlines() if line.strip())
	return normalized or None


def _tableCellControlFieldAttrs(cellInfo: textInfos.TextInfo) -> dict[str, Any]:
	"""Innermost table-cell control field attrs at a cell (same stack NVDA speech uses)."""
	info = cellInfo.copy()
	info.expand(textInfos.UNIT_CONTROLFIELD)
	try:
		fields = list(info.getTextWithFields())
	except (LookupError, NotImplementedError, RuntimeError):
		return {}
	for field in reversed(fields):
		if not isinstance(field, textInfos.FieldCommand) or field.command != "controlStart":
			continue
		attrs = field.field
		if attrs.get("table-layout"):
			continue
		if "table-columnnumber" in attrs:
			return attrs
	return {}


def _cellIsColumnHeaderRow(cellInfo: textInfos.TextInfo) -> bool:
	return _tableCellControlFieldAttrs(cellInfo).get("role") == get_control_type("ROLE_TABLECOLUMNHEADER")


def _tableHeaderTextsForFlash(cellInfo: textInfos.TextInfo) -> tuple[str | None, str | None]:
	"""Column/row header text respecting document formatting ``reportTableHeaders``."""
	report = config.conf["documentFormatting"]["reportTableHeaders"]
	attrs = _tableCellControlFieldAttrs(cellInfo)
	columnHeader = rowHeader = None
	if report in (ReportTableHeaders.ROWS_AND_COLUMNS, ReportTableHeaders.COLUMNS):
		columnHeader = _normalizeTableHeaderText(attrs.get("table-columnheadertext"))
	if report in (ReportTableHeaders.ROWS_AND_COLUMNS, ReportTableHeaders.ROWS):
		rowHeader = _normalizeTableHeaderText(attrs.get("table-rowheadertext"))
	return columnHeader, rowHeader


def _columnRangeLabel(column: int, colSpan: int) -> str:
	if colSpan > 1:
		# Translators: Merged table columns in a braille routing flash (e.g. columns 1-3).
		return _("columns {start}-{end}").format(start=column, end=column + colSpan - 1)
	# Translators: A single table column in a braille routing flash (e.g. column 2).
	return _("column {column}").format(column=column)


def _rowRangeLabel(row: int, rowSpan: int) -> str:
	if rowSpan > 1:
		# Translators: Merged table rows in a braille routing flash (e.g. rows 2-4).
		return _("rows {start}-{end}").format(start=row, end=row + rowSpan - 1)
	# Translators: A single table row in a braille routing flash (e.g. row 2).
	return _("row {row}").format(row=row)


def _columnBoundaryCoordFlashMessage(
	row: int,
	column: int,
	*,
	rowSpan: int = 1,
	colSpan: int = 1,
	columnHeaderText: str | None = None,
	rowHeaderText: str | None = None,
) -> str:
	"""Unified flash for column boundaries (row-start marker and `` | `` separators)."""
	rowSpan = max(1, rowSpan or 1)
	colSpan = max(1, colSpan or 1)
	message = _columnRangeLabel(column, colSpan)
	if columnHeaderText:
		message = _appendFlashDetail(message, columnHeaderText)
	if row > 0:
		message = _appendFlashDetail(message, _rowRangeLabel(row, rowSpan))
	if rowHeaderText:
		message = _appendFlashDetail(message, rowHeaderText)
	return message


def _tableRowCoordFlashMessage(
	zone: TableRowRoutingZone,
	row: int,
	column: int,
	*,
	rowSpan: int = 1,
	colSpan: int = 1,
	columnHeaderText: str | None = None,
	rowHeaderText: str | None = None,
) -> str | None:
	if zone == "column":
		return _columnBoundaryCoordFlashMessage(
			row,
			column,
			rowSpan=rowSpan,
			colSpan=colSpan,
			columnHeaderText=columnHeaderText,
			rowHeaderText=rowHeaderText,
		)
	if zone == "row":
		rowSpan = max(1, rowSpan or 1)
		colSpan = max(1, colSpan or 1)
		message = _rowRangeLabel(row, rowSpan)
		if colSpan > 1:
			message = _appendFlashDetail(message, _columnRangeLabel(column, colSpan))
		return message
	return None


def _tableRowRoutingCoordFlash(
	zone: TableRowRoutingZone,
	cellInfo: textInfos.TextInfo,
	row: int,
	column: int,
	*,
	rowSpan: int,
	colSpan: int,
) -> str | None:
	columnHeaderText = rowHeaderText = None
	if not _cellIsColumnHeaderRow(cellInfo):
		columnHeaderText, rowHeaderText = _tableHeaderTextsForFlash(cellInfo)
	return _tableRowCoordFlashMessage(
		zone,
		row,
		column,
		rowSpan=rowSpan,
		colSpan=colSpan,
		columnHeaderText=columnHeaderText,
		rowHeaderText=rowHeaderText,
	)


def _cellSegmentDisplayState(
	layout: _TableRowCellBrailleLayout,
	contentText: str,
	contentRawToContentPos: tuple[int, ...],
) -> tuple[str, tuple[int, ...]]:
	prefix = layout.displayPrefix
	suffix = layout.displaySuffix
	text = prefix + contentText
	contentBase = contentRawToContentPos[0] if contentRawToContentPos else 0
	mapping = [contentBase] * len(prefix) + list(contentRawToContentPos)
	if suffix:
		endOffset = mapping[-1] if mapping else contentBase
		text += suffix
		mapping.extend([endOffset] * len(suffix))
	return text, tuple(mapping)


def _tableRoleBrailleLabelCandidates() -> tuple[str, ...]:
	"""Possible table-start labels (role name, tags, etc.) at the start of cell braille."""
	candidates: list[str] = []
	table_role = get_control_type("ROLE_TABLE")
	try:
		label = braille.roleLabels[table_role]
	except (KeyError, TypeError):
		label = None
	if label and label not in candidates:
		candidates.append(label)
	if get_roleLabel is not None:
		try:
			role_label = get_roleLabel(table_role)
			if role_label and role_label not in candidates:
				candidates.append(role_label)
		except (AttributeError, TypeError):
			pass
	return tuple(candidates)


def _tableRoleBrailleLabel() -> str:
	candidates = _tableRoleBrailleLabelCandidates()
	return candidates[0] if candidates else "tb"


def _tableDimensionsFromControlFields(
	virtualBuffer,
	cellInfo: textInfos.TextInfo,
	*,
	tableID: int | None = None,
) -> tuple[int, int] | None:
	"""Read row/column counts from the TABLE control field (speech uses the same attrs)."""
	info = cellInfo.copy()
	if info.isCollapsed:
		info.expand(textInfos.UNIT_CHARACTER)
	try:
		fields = info.getTextWithFields()
	except (LookupError, NotImplementedError, RuntimeError):
		return None
	layoutIDs: set = set()
	if hasattr(virtualBuffer, "_maybeGetLayoutTableIds"):
		try:
			layoutIDs = virtualBuffer._maybeGetLayoutTableIds(info)
		except (AttributeError, LookupError, NotImplementedError, RuntimeError):
			layoutIDs = set()
	table_role = get_control_type("ROLE_TABLE")
	for field in reversed(list(fields)):
		if not isinstance(field, textInfos.FieldCommand) or field.command != "controlStart":
			continue
		attrs = field.field
		if attrs.get("role") != table_role:
			continue
		field_table_id = attrs.get("table-id")
		if tableID is not None and field_table_id != tableID:
			continue
		if field_table_id is None or field_table_id in layoutIDs:
			continue
		row_count = attrs.get("table-rowcount-presentational")
		if row_count is None:
			row_count = attrs.get("table-rowcount")
		col_count = attrs.get("table-columncount-presentational")
		if col_count is None:
			col_count = attrs.get("table-columncount")
		try:
			if row_count is not None and col_count is not None:
				return int(row_count), int(col_count)
		except (TypeError, ValueError):
			continue
	return None


def _getVirtualBufferTableDimensions(
	virtualBuffer,
	cellInfo: textInfos.TextInfo,
	*,
	tableID: int | None = None,
) -> tuple[int, int] | None:
	"""Return (rowCount, columnCount) using NVDA virtual-buffer table metadata."""
	dims = _tableDimensionsFromControlFields(virtualBuffer, cellInfo, tableID=tableID)
	if dims is not None:
		return dims
	try:
		return virtualBuffer._getTableDimensions(cellInfo)
	except (LookupError, AttributeError, NotImplementedError, TypeError, ValueError):
		return None


def _tableBoundaryPrefix(
	virtualBuffer,
	cellInfo: textInfos.TextInfo,
	*,
	tableID: int | None = None,
) -> str:
	"""Table start marker for row braille, e.g. ``tb(4,10)``."""
	return _tableBoundaryMarker(virtualBuffer, cellInfo, tableID=tableID)


def _tableBoundarySuffix() -> str:
	"""Table end marker for row braille, e.g. ``tb end`` (NVDA controlEnd style)."""
	return f"{_tableRoleBrailleLabel()} end"


def _tableBoundaryMarker(
	virtualBuffer,
	cellInfo: textInfos.TextInfo,
	*,
	tableID: int | None = None,
) -> str:
	label = _tableRoleBrailleLabel()
	dims = _getVirtualBufferTableDimensions(virtualBuffer, cellInfo, tableID=tableID)
	if dims is not None:
		rows, cols = dims
		return f"{label}({rows},{cols})"
	return label


def _tableRowCellBrailleLayoutForPlacement(
	index: int,
	lastIndex: int,
	cellInfo: textInfos.TextInfo,
	*,
	cellSeparator: str,
	lineStart: str,
	lineEnd: str,
	virtualBuffer,
	tableID: int | None,
	tableRow: int,
	tableRowCount: int | None,
) -> _TableRowCellBrailleLayout:
	isFirstTableRow = tableRow == 1
	isLastTableRow = tableRowCount is not None and tableRow == tableRowCount
	if index == 0:
		layout = _TableRowCellBrailleLayout(
			tableBoundaryPrefix=(
				_tableBoundaryPrefix(virtualBuffer, cellInfo, tableID=tableID) if isFirstTableRow else ""
			),
			lineStart=lineStart or "",
		)
	else:
		layout = _TableRowCellBrailleLayout(cellSeparator=cellSeparator or "")
	if index == lastIndex:
		layout = replace(
			layout,
			lineEnd=lineEnd or "",
			tableBoundarySuffix=_tableBoundarySuffix() if isLastTableRow else "",
		)
	return layout


def is_table_row_braille_enabled() -> bool:
	return _virtualDocumentConf()["tableRowBraille"]


_virtualBufferGetBrailleRegionsInstalled = False
_originalVirtualBufferGetBrailleRegions: Any = None
_originalGetFocusContextRegions: Any = None
_originalHandleCaretMove: Any = None
_originalHandleUpdate: Any = None
_originalHandlePendingUpdate: Any = None
_originalRouteTo: Any = None
_originalHandleGainFocus: Any = None
_originalGeckoGetTableCellAt: Any = None
_originalGeckoGetNearestTableCell: Any = None
_originalTableFindNewCell: Any = None
_originalHandlerScrollBack: Any = None
_originalHandlerScrollForward: Any = None


@dataclass(frozen=True)
class _CellBrailleSnapshot:
	text: str
	rawToContentPos: tuple[int, ...]
	rawTextTypeforms: tuple[int, ...] = ()
	brlexTypeformItems: tuple[tuple[int, int], ...] = ()
	endsWithField: bool = False
	formatField: textInfos.FormatField | None = None


@dataclass(frozen=True)
class _TableRowCellData:
	column: int
	row: int
	cellInfo: textInfos.TextInfo
	cellObj: Any
	text: str
	rawToContentPos: tuple[int, ...]
	isCurrent: bool
	rowSpan: int = 1
	colSpan: int = 1
	rawTextTypeforms: tuple[int, ...] = ()
	brlexTypeformItems: tuple[tuple[int, int], ...] = ()
	endsWithField: bool = False


class _CellBrailleTextBuilder(braille.TextInfoRegion):
	"""Build cell braille like ``TextInfoRegion``; row layout supplies table boundary markers."""

	suppressTableCellCoords = True
	suppressTableRowLayoutMarkers = True

	def __init__(self, virtualBuffer) -> None:
		super().__init__(virtualBuffer)
		self.rawText = ""
		self.rawTextTypeforms = []
		self.brlex_typeforms = {}
		self._len_brlex_typeforms = 0
		self.cursorPos = None
		self._rawToContentPos = []
		self._currentContentPos = 0
		self.selectionStart = self.selectionEnd = None
		self._isFormatFieldAtStart = True
		self._skipFieldsNotAtStartOfNode = False
		self._endsWithField = False


def _isCurrentTableCell(currentCell, cellCoords) -> bool:
	return (
		currentCell.tableID == cellCoords.tableID
		and currentCell.row == cellCoords.row
		and currentCell.col == cellCoords.col
	)


def _currentTableCell(virtualBuffer) -> Any | None:
	try:
		return virtualBuffer._getTableCellCoords(virtualBuffer.selection)
	except LookupError:
		return None


def _navigateVirtualBufferTableRow(virtualBuffer, *, forward: bool) -> bool:
	"""Move to the next/previous row using NVDA virtual-buffer table navigation."""
	cell = _currentTableCell(virtualBuffer)
	if cell is None:
		return False
	movement = "next" if forward else "previous"
	try:
		cellInfo = virtualBuffer._getNearestTableCell(
			virtualBuffer.selection,
			cell,
			movement,
			"row",
		)
	except LookupError:
		return False
	dest = cellInfo.copy()
	dest.collapse()
	virtualBuffer.selection = dest
	return True


def _tableCellTextInfo(cellInfo: textInfos.TextInfo) -> textInfos.TextInfo:
	"""Span the full table cell.

	Virtual-buffer table iteration already bounds ``cellInfo`` to the cell node.
	``UNIT_CONTROLFIELD`` would shrink to an inner control (link, list, paragraph, …).
	"""
	info = cellInfo.copy()
	if info.isCollapsed:
		info.expand(textInfos.UNIT_CHARACTER)
	return info


def _populateCellBrailleBuilder(
	builder: _CellBrailleTextBuilder,
	cellInfo: textInfos.TextInfo,
	caret: textInfos.TextInfo | None = None,
	*,
	virtualBuffer=None,
	currentCell=None,
) -> int | None:
	"""Fill builder with cell braille; return raw ``cursorPos`` (NVDA three-chunk algorithm)."""
	formatConfig = _cellBrailleFormatConfig()
	cellField = _tableCellTextInfo(cellInfo)
	inCell = False
	if caret is not None and virtualBuffer is not None and currentCell is not None:
		try:
			cellCoords = virtualBuffer._getTableCellCoords(cellInfo)
		except LookupError:
			inCell = False
		else:
			inCell = _isCurrentTableCell(currentCell, cellCoords)
	if caret is None or not inCell:
		builder._addTextWithFields(cellField, formatConfig)
		return None

	readingInfo = cellField.copy()
	sel = caret.copy()
	sel.collapse()
	chunk = readingInfo.copy()
	chunk.collapse()
	chunk.setEndPoint(sel, "endToStart")
	builder._addTextWithFields(chunk, formatConfig)
	builder._addTextWithFields(sel, formatConfig, isSelection=True)
	cursorPos = builder.cursorPos
	chunk.setEndPoint(readingInfo, "endToEnd")
	chunk.setEndPoint(sel, "startToEnd")
	builder._addTextWithFields(chunk, formatConfig)
	return cursorPos


def _snapRawCursorOffFieldLabels(rawPos: int, rawToContentPos: tuple[int, ...]) -> int:
	"""Skip NVDA field-label characters (``_addFieldText`` duplicate mappings)."""
	while rawPos + 1 < len(rawToContentPos) and rawToContentPos[rawPos] == rawToContentPos[rawPos + 1]:
		rawPos += 1
	return rawPos


def _padRawToContentPos(
	rawToContentPos: list[int] | tuple[int, ...],
	textLen: int,
) -> tuple[int, ...]:
	"""Ensure ``_rawToContentPos`` has one entry per character of ``rawText`` (NVDA parity)."""
	if textLen <= 0:
		return ()
	if not rawToContentPos:
		return tuple(range(textLen))
	mapping = list(rawToContentPos[:textLen])
	if len(mapping) < textLen:
		nextOffset = mapping[-1] + 1 if mapping else 0
		mapping.extend(range(nextOffset, nextOffset + (textLen - len(mapping))))
	return tuple(mapping)


def _rawPosForContentOffset(rawToContentPos: tuple[int, ...], contentOffset: int) -> int:
	"""First raw index whose mapped reading-unit offset is at least ``contentOffset``."""
	if not rawToContentPos:
		return max(0, contentOffset)
	for rawIndex, mappedOffset in enumerate(rawToContentPos):
		if mappedOffset >= contentOffset:
			return rawIndex
	return len(rawToContentPos) - 1


def _builderCursorToContentDisplayIndex(
	builder: _CellBrailleTextBuilder,
	builderCursorPos: int,
	contentText: str,
	contentRawToContentPos: tuple[int, ...],
) -> int:
	"""Map NVDA builder ``cursorPos`` to an index in displayed cell content."""
	contentLen = len(contentText)
	if contentLen <= 0:
		return 0
	builderText = builder.rawText.rstrip("\r\n\0\v\f")
	if not builderText:
		return 0
	cursorPos = min(max(0, builderCursorPos), len(builderText) - 1)
	builderMapping = _padRawToContentPos(builder._rawToContentPos, len(builderText))
	cursorPos = _snapRawCursorOffFieldLabels(cursorPos, builderMapping)
	if builderText == contentText:
		return min(cursorPos, contentLen - 1)
	contentOffset = (
		builderMapping[cursorPos]
		if cursorPos < len(builderMapping)
		else (builderMapping[-1] if builderMapping else 0)
	)
	if contentRawToContentPos and len(contentRawToContentPos) == contentLen:
		return min(_rawPosForContentOffset(contentRawToContentPos, contentOffset), contentLen - 1)
	return min(cursorPos, contentLen - 1)


def _snapshotFromCellBuilder(builder: _CellBrailleTextBuilder) -> _CellBrailleSnapshot:
	text = builder.rawText.rstrip("\r\n\0\v\f")
	textLen = len(text)
	typeforms = builder.rawTextTypeforms
	if len(typeforms) > textLen:
		typeforms = typeforms[:textLen]
	elif len(typeforms) < textLen:
		typeforms = typeforms + [louis.plain_text] * (textLen - len(typeforms))
	return _CellBrailleSnapshot(
		text,
		_padRawToContentPos(builder._rawToContentPos, textLen),
		tuple(typeforms),
		tuple(builder.brlex_typeforms.items()),
		builder._endsWithField,
		getattr(builder, "formatField", None),
	)


def _buildCellBrailleWithCursor(
	cellInfo: textInfos.TextInfo,
	caret: textInfos.TextInfo | None = None,
	*,
	virtualBuffer=None,
	currentCell=None,
) -> tuple[_CellBrailleSnapshot, int | None]:
	"""Build cell braille and map the caret in one ``TextInfoRegion`` pass."""
	builder = _CellBrailleTextBuilder(cellInfo.obj)
	builderCursorPos = _populateCellBrailleBuilder(
		builder,
		cellInfo,
		caret,
		virtualBuffer=virtualBuffer,
		currentCell=currentCell,
	)
	snapshot = _snapshotFromCellBuilder(builder)
	if builderCursorPos is None or caret is None:
		return snapshot, None
	return snapshot, _builderCursorToContentDisplayIndex(
		builder,
		builderCursorPos,
		snapshot.text,
		snapshot.rawToContentPos,
	)


def _applyCellSnapshotToRegion(
	region: "VirtualBufferTableCellBrailleRegion",
	snapshot: _CellBrailleSnapshot,
) -> None:
	region._contentText = snapshot.text
	region._contentRawToContentPos = snapshot.rawToContentPos
	region._contentRawTextTypeforms = snapshot.rawTextTypeforms
	region._brlexTypeformItems = snapshot.brlexTypeformItems
	region._endsWithField = snapshot.endsWithField
	region.formatField = snapshot.formatField or textInfos.FormatField()


def _cellReadingInfo(cellInfo: textInfos.TextInfo) -> textInfos.TextInfo:
	return _tableCellTextInfo(cellInfo)


def _getTableRowCellData(
	virtualBuffer,
	caretInfo: textInfos.TextInfo,
	*,
	withText: bool = True,
) -> list[_TableRowCellData] | None:
	try:
		currentCell = virtualBuffer._getTableCellCoords(caretInfo)
	except LookupError:
		return None

	tableID = currentCell.tableID
	row = currentCell.row
	cells: list[_TableRowCellData] = []

	for info in virtualBuffer._iterTableCells(tableID, row=row):
		try:
			coords = virtualBuffer._getTableCellCoords(info)
		except LookupError:
			continue
		if coords.tableID != tableID or coords.row != row:
			continue
		if withText:
			snapshot, _ = _buildCellBrailleWithCursor(info)
		else:
			snapshot = _CellBrailleSnapshot("", ())
		cells.append(
			_TableRowCellData(
				column=coords.col,
				row=coords.row,
				cellInfo=info,
				cellObj=info.NVDAObjectAtStart,
				text=snapshot.text,
				rawToContentPos=snapshot.rawToContentPos,
				isCurrent=_isCurrentTableCell(currentCell, coords),
				rowSpan=coords.rowSpan,
				colSpan=coords.colSpan,
				rawTextTypeforms=snapshot.rawTextTypeforms,
				brlexTypeformItems=snapshot.brlexTypeformItems,
				endsWithField=snapshot.endsWithField,
			)
		)

	if not cells:
		return None
	cells.sort(key=lambda item: item.column)
	return cells


def _caretInTableRow(virtualBuffer, caretInfo: textInfos.TextInfo | None = None) -> bool:
	if virtualBuffer.passThrough or not virtualBuffer.isReady:
		return False
	if caretInfo is None:
		caretInfo = virtualBuffer.selection
	try:
		virtualBuffer._getTableCellCoords(caretInfo)
	except LookupError:
		return False
	return True


def usesTableRowBrailleRegions(virtualBuffer, caretInfo: textInfos.TextInfo | None = None) -> bool:
	if not is_table_row_braille_enabled():
		return False
	return _caretInTableRow(virtualBuffer, caretInfo)


class VirtualBufferTableCellBrailleRegion(braille.CursorManagerRegion):
	"""One table cell on a row braille line; routing uses NVDA TextInfoRegion logic."""

	allowPageTurns = True

	def __init__(
		self,
		virtualBuffer,
		cellInfo: textInfos.TextInfo,
		cellObj: Any,
		contentText: str,
		*,
		rawToContentPos: tuple[int, ...] = (),
		rawTextTypeforms: tuple[int, ...] = (),
		brlexTypeformItems: tuple[tuple[int, int], ...] = (),
		endsWithField: bool = False,
		isCurrentCell: bool = False,
		tableID: int = 0,
		row: int = 0,
		column: int = 0,
		rowSpan: int = 1,
		colSpan: int = 1,
		layout: _TableRowCellBrailleLayout | None = None,
		isRowEndCell: bool = False,
	) -> None:
		super().__init__(virtualBuffer)
		self._virtualBuffer = virtualBuffer
		self._cellInfo = cellInfo
		self._cellNvdaObject = cellObj
		self._layout = layout or _TableRowCellBrailleLayout()
		self._isRowEndCell = isRowEndCell
		self._rowBackwardCell: VirtualBufferTableCellBrailleRegion | None = None
		self.formatField = textInfos.FormatField()
		self._contentText = contentText
		self._contentRawToContentPos = rawToContentPos
		self._contentRawTextTypeforms = rawTextTypeforms
		self._brlexTypeformItems = brlexTypeformItems
		self._endsWithField = endsWithField
		self.isCurrentCell = isCurrentCell
		self._tableID = tableID
		self._row = row
		self._column = column
		self._rowSpan = max(1, rowSpan or 1)
		self._colSpan = max(1, colSpan or 1)

	def _isMultiline(self) -> bool:
		return False

	def _syncReadingInfo(self) -> None:
		self._readingInfo = _cellReadingInfo(self._cellInfo)

	def _prepareBrailleTranslationState(self) -> None:
		content, rawToContentPos = _cellSegmentDisplayState(
			self._layout,
			self._contentText,
			self._contentRawToContentPos,
		)
		prefixLen = len(self._layout.displayPrefix)
		suffixLen = len(self._layout.displaySuffix)
		contentLen = len(self._contentText)
		contentTypeforms = list(self._contentRawTextTypeforms)
		if len(contentTypeforms) > contentLen:
			contentTypeforms = contentTypeforms[:contentLen]
		elif len(contentTypeforms) < contentLen:
			contentTypeforms.extend([louis.plain_text] * (contentLen - len(contentTypeforms)))
		self.rawText = content
		self.rawTextTypeforms = (
			[louis.plain_text] * prefixLen + contentTypeforms + [louis.plain_text] * suffixLen
		)
		self.brlex_typeforms = {raw_pos + prefixLen: mask for raw_pos, mask in self._brlexTypeformItems}
		self._len_brlex_typeforms = 0
		self._rawToContentPos = list(
			_padRawToContentPos(rawToContentPos, len(content)),
		)
		if contentLen:
			self._currentContentPos = self._rawToContentPos[prefixLen + contentLen - 1]
		elif self._rawToContentPos:
			self._currentContentPos = self._rawToContentPos[min(prefixLen, len(self._rawToContentPos) - 1)]
		else:
			self._currentContentPos = 0

	def getTextInfoForBraillePos(self, braillePos: int) -> textInfos.TextInfo:
		self._syncReadingInfo()
		return braille.TextInfoRegion.getTextInfoForBraillePos(self, braillePos)

	def update(self, *, rebuildContent: bool = False) -> None:
		contentCursor: int | None = None
		caret = self._virtualBuffer.selection if self.isCurrentCell else None
		currentCell = _currentTableCell(self._virtualBuffer) if self.isCurrentCell else None
		if rebuildContent:
			snapshot, contentCursor = _buildCellBrailleWithCursor(
				self._cellInfo,
				caret,
				virtualBuffer=self._virtualBuffer,
				currentCell=currentCell,
			)
			_applyCellSnapshotToRegion(self, snapshot)
		elif self.isCurrentCell:
			_, contentCursor = _buildCellBrailleWithCursor(
				self._cellInfo,
				caret,
				virtualBuffer=self._virtualBuffer,
				currentCell=currentCell,
			)
		self._syncReadingInfo()
		self._prepareBrailleTranslationState()
		prefixLen = len(self._layout.displayPrefix)
		contentLen = len(self._contentText)
		self.focusToHardLeft = False
		if self.isCurrentCell:
			cursorPos = contentCursor
			if cursorPos is not None:
				cursorPos += prefixLen
			self.cursorPos = cursorPos
			if contentLen == 0 or not self._endsWithField:
				self.rawText += braille.TEXT_SEPARATOR
				self.rawTextTypeforms.append(louis.plain_text)
				self._rawToContentPos.append(self._currentContentPos)
			rawTextLen = len(self.rawText)
			if self.cursorPos is not None and self.cursorPos >= rawTextLen:
				self.cursorPos = rawTextLen - 1
		else:
			self.cursorPos = None
			self.selectionStart = self.selectionEnd = None
			self.brailleCursorPos = None
		braille.Region.update(self)
		apply_braille_region_post_translation_extras(self)

	def _routeToCell(self) -> None:
		dest = self._cellInfo.copy()
		dest.collapse()
		try:
			self._virtualBuffer.selection = dest
		except (AttributeError, NotImplementedError, RuntimeError):
			try:
				dest.updateCaret()
			except NotImplementedError:
				log.debugWarning("virtual buffer table row cell routing failed", exc_info=True)

	def _rawPosForBraillePos(self, braillePos: int) -> int:
		try:
			return self.brailleToRawPos[braillePos]
		except IndexError:
			return max(0, len(self.rawText) - 1)

	def routeTo(self, braillePos: int) -> None:
		rawPos = self._rawPosForBraillePos(braillePos)
		zone = self._layout.routingZoneAt(rawPos, len(self._contentText))
		if zone != "content":
			message = _tableRowRoutingCoordFlash(
				zone,
				self._cellInfo,
				self._row,
				self._column,
				rowSpan=self._rowSpan,
				colSpan=self._colSpan,
			)
			if message:
				_queueTableRowCoordFlash(message)
			self._routeToCell()
			handler = braille.handler
			if handler is not None and handler.enabled:
				_updateExistingTableRowRegions(handler, self._virtualBuffer, scrollToCaret=True)
			return
		_clearTableRowCoordFlash()
		self._routeToTextInfo(self.getTextInfoForBraillePos(braillePos))
		handler = braille.handler
		if handler is not None and handler.enabled:
			_updateExistingTableRowRegions(handler, self._virtualBuffer, scrollToCaret=True)

	def _syncReadingInfoForCaretLineNav(self) -> None:
		"""Reading unit at the virtual-buffer caret, like TextInfoRegion.update."""
		unit = self._getReadingUnit()
		self._readingInfo = self._virtualBuffer.selection.copy()
		if self._readingInfo.isCollapsed:
			self._readingInfo.expand(unit)

	def _refreshAfterLineNav(self) -> None:
		handler = braille.handler
		if handler is not None and handler.enabled:
			_updateExistingTableRowRegions(handler, self._virtualBuffer)

	def _documentLineNav(self, *, forward: bool, start: bool = False) -> None:
		"""Document-level line navigation (NVDA ``TextInfoRegion``) from the caret."""
		helper = braille.TextInfoRegion(self._virtualBuffer)
		helper._readingInfo = self._virtualBuffer.selection.copy()
		unit = helper._getReadingUnit()
		if helper._readingInfo.isCollapsed:
			helper._readingInfo.expand(unit)
		if forward:
			braille.TextInfoRegion.nextLine(helper)
		else:
			braille.TextInfoRegion.previousLine(helper, start)

	def _lineNavNextFromEnd(self) -> None:
		"""Leave the current row when braille scroll reaches the row end."""
		if _navigateVirtualBufferTableRow(self._virtualBuffer, forward=True):
			try:
				braille._speakOnNavigatingByUnit(
					self._virtualBuffer.selection,
					self._getReadingUnit(),
				)
			except AttributeError:
				pass
			self._refreshAfterLineNav()
			return
		self._documentLineNav(forward=True)
		self._refreshAfterLineNav()

	def _lineNavPreviousFromStart(self, *, start: bool = False) -> None:
		"""Leave the current row when braille scroll reaches the row start."""
		if _navigateVirtualBufferTableRow(self._virtualBuffer, forward=False):
			try:
				braille._speakOnNavigatingByUnit(
					self._virtualBuffer.selection,
					self._getReadingUnit(),
				)
			except AttributeError:
				pass
			self._refreshAfterLineNav()
			return
		self._documentLineNav(forward=False, start=start)
		self._refreshAfterLineNav()

	def nextLine(self) -> None:
		if self._isRowEndCell:
			self._lineNavNextFromEnd()
			return
		if not self.isCurrentCell:
			return
		self._syncReadingInfoForCaretLineNav()
		braille.TextInfoRegion.nextLine(self)
		self._refreshAfterLineNav()

	def previousLine(self, start: bool = False) -> None:
		if self._isRowEndCell and self._rowBackwardCell is not None:
			self._rowBackwardCell._lineNavPreviousFromStart(start=start)
			return
		if not self.isCurrentCell:
			return
		self._syncReadingInfoForCaretLineNav()
		braille.TextInfoRegion.previousLine(self, start)
		self._refreshAfterLineNav()


def _updateTableRowRegion(region: braille.Region, *, rebuildContent: bool = False) -> None:
	if isinstance(region, VirtualBufferTableCellBrailleRegion):
		region.update(rebuildContent=rebuildContent)
	else:
		region.update()


def _cellRegionsForBuffer(regions: list, virtualBuffer) -> list[VirtualBufferTableCellBrailleRegion]:
	return [
		region
		for region in regions
		if isinstance(region, VirtualBufferTableCellBrailleRegion) and region._virtualBuffer is virtualBuffer
	]


def _clearTableRowFocusToHardLeft(mainBuffer: braille.BrailleBuffer) -> None:
	"""Table-row cells must not keep ``focusToHardLeft`` (NVDA clamps scrollBack via ``windowEndPos``)."""
	for region in mainBuffer.regions:
		if isinstance(region, VirtualBufferTableCellBrailleRegion):
			region.focusToHardLeft = False


def _tableRowBrailleRegionsFromCells(
	virtualBuffer,
	rowCells: list[_TableRowCellData],
	currentCell,
) -> list[braille.Region]:
	regions: list[braille.Region] = []
	cellSeparator, lineStart, lineEnd = _tableRowBrailleMarkers()
	tableRowCount = _tableRowCount(
		virtualBuffer,
		rowCells[0].cellInfo,
		tableID=currentCell.tableID,
	)
	lastIndex = len(rowCells) - 1
	firstCellRegion: VirtualBufferTableCellBrailleRegion | None = None
	lastCellRegion: VirtualBufferTableCellBrailleRegion | None = None
	for index, cellData in enumerate(rowCells):
		layout = _tableRowCellBrailleLayoutForPlacement(
			index,
			lastIndex,
			cellData.cellInfo,
			cellSeparator=cellSeparator or "",
			lineStart=lineStart or "",
			lineEnd=lineEnd or "",
			virtualBuffer=virtualBuffer,
			tableID=currentCell.tableID,
			tableRow=currentCell.row,
			tableRowCount=tableRowCount,
		)
		cellRegion = VirtualBufferTableCellBrailleRegion(
			virtualBuffer,
			cellData.cellInfo,
			cellData.cellObj,
			cellData.text,
			rawToContentPos=cellData.rawToContentPos,
			rawTextTypeforms=cellData.rawTextTypeforms,
			brlexTypeformItems=cellData.brlexTypeformItems,
			endsWithField=cellData.endsWithField,
			isCurrentCell=cellData.isCurrent,
			tableID=currentCell.tableID,
			row=cellData.row,
			column=cellData.column,
			rowSpan=cellData.rowSpan,
			colSpan=cellData.colSpan,
			layout=layout,
			isRowEndCell=index == lastIndex,
		)
		regions.append(cellRegion)
		if index == 0:
			firstCellRegion = cellRegion
		lastCellRegion = cellRegion
	if firstCellRegion is not None and lastCellRegion is not None:
		lastCellRegion._rowBackwardCell = firstCellRegion
	for region in regions:
		region.focusToHardLeft = False
	return regions


def _shouldUseTableRowBrailleRegions(obj, review: bool = False) -> bool:
	if not is_table_row_braille_enabled():
		return False
	if review or obj.passThrough or not obj.isReady:
		return False
	return _caretInTableRow(obj)


def _buildTableRowBrailleRegions(
	obj,
) -> list[braille.Region]:
	caret = obj.selection
	rowCells = _getTableRowCellData(obj, caret)
	if not rowCells:
		raise RuntimeError("table row braille requested outside a table row")
	currentCell = obj._getTableCellCoords(caret)
	regions = _tableRowBrailleRegionsFromCells(obj, rowCells, currentCell)
	for region in regions:
		region.hidePreviousRegions = False
		_updateTableRowRegion(region, rebuildContent=False)
	return regions


def virtualBuffer_getBrailleRegions(
	obj,
	review: bool = False,
) -> Iterable[braille.Region]:
	"""Return table-row braille regions, or raise NotImplementedError for NVDA fallback.

	Must not be a generator function: NVDA only catches NotImplementedError from the
	initial call, not while iterating a generator returned after partial execution.
	"""
	if not _shouldUseTableRowBrailleRegions(obj, review):
		raise NotImplementedError
	return _buildTableRowBrailleRegions(obj)


def _getFocusContextRegionsForVirtualBufferTable(obj, oldFocusRegions=None):
	"""Skip foreground ancestor regions in table-row braille mode; keep all cell columns."""
	if isinstance(obj, VirtualBuffer) and usesTableRowBrailleRegions(obj):
		return iter(())
	return _originalGetFocusContextRegions(obj, oldFocusRegions=oldFocusRegions)


def _clearStaleVirtualBufferTextInfoPendingUpdates(handler: braille.BrailleHandler, virtualBuffer) -> None:
	"""Drop queued TextInfoRegion caret scrolls for a buffer we replaced with table-row regions."""
	stale = {
		region
		for region in handler._regionsPendingUpdate
		if isinstance(region, braille.TextInfoRegion) and region.obj is virtualBuffer
	}
	if not stale:
		return
	handler._regionsPendingUpdate -= stale
	for region in stale:
		region.pendingCaretUpdate = False


def _regionMatchesTableCell(
	region: VirtualBufferTableCellBrailleRegion,
	currentCell,
) -> bool:
	return (
		region._tableID == currentCell.tableID
		and region._row == currentCell.row
		and region._column == currentCell.col
	)


def _primaryTableRowFocusRegion(
	tableRegions: list,
	virtualBuffer=None,
) -> VirtualBufferTableCellBrailleRegion | None:
	for region in tableRegions:
		if isinstance(region, VirtualBufferTableCellBrailleRegion) and region.isCurrentCell:
			return region
	if virtualBuffer is not None:
		currentCell = _currentTableCell(virtualBuffer)
		if currentCell is not None:
			for region in tableRegions:
				if isinstance(region, VirtualBufferTableCellBrailleRegion) and _regionMatchesTableCell(
					region, currentCell
				):
					return region
	for region in tableRegions:
		if isinstance(region, VirtualBufferTableCellBrailleRegion):
			return region
	return None


def _apply_braille_buffer_focus_regions(
	handler: braille.BrailleHandler,
	mainBuffer: braille.BrailleBuffer,
	contextRegions: list,
	focusRegions: list,
	*,
	regionsAlreadyUpdated: bool = False,
) -> bool:
	for region in contextRegions:
		region.focusToHardLeft = False
		region.update()
	if not regionsAlreadyUpdated:
		for region in focusRegions:
			_updateTableRowRegion(region, rebuildContent=False)
	mainBuffer.regions = contextRegions + focusRegions
	mainBuffer.update()
	rowVirtualBuffer = next(
		(r._virtualBuffer for r in focusRegions if isinstance(r, VirtualBufferTableCellBrailleRegion)),
		None,
	)
	primaryFocus = _primaryTableRowFocusRegion(focusRegions, rowVirtualBuffer)
	if primaryFocus is None:
		if handler.buffer is mainBuffer:
			handler.update()
		return bool(focusRegions)
	_focusAndScrollTableRowRegion(handler, mainBuffer, primaryFocus)
	if handler.buffer is mainBuffer:
		handler.update()
	if primaryFocus is not None:
		_clearStaleVirtualBufferTextInfoPendingUpdates(handler, primaryFocus._virtualBuffer)
	return True


def _currentTableRowColumn(
	tableRegions: list[VirtualBufferTableCellBrailleRegion],
) -> int | None:
	for region in tableRegions:
		if region.isCurrentCell:
			return region._column
	return None


def _focusAndScrollTableRowRegion(
	handler: braille.BrailleHandler,
	mainBuffer: braille.BrailleBuffer,
	region: VirtualBufferTableCellBrailleRegion | None,
) -> None:
	"""Show the active table cell without anchoring to column 1.

	NVDA ``BrailleBuffer.focus`` plus ``focusToHardLeft`` on the first cell prevents
	``scrollBack`` (``windowEndPos`` is clamped) and ``scrollToCursorOrSelection`` pulls
	the window back to the caret column while the user is panning across the row.
	"""
	if region is None:
		return
	_clearTableRowFocusToHardLeft(mainBuffer)
	try:
		handler.scrollToCursorOrSelection(region)
	except LookupError:
		log.debugWarning("virtual buffer table braille column scroll failed", exc_info=True)


def _onVirtualBufferTableRowCaretMove(
	handler: braille.BrailleHandler,
	virtualBuffer,
	*,
	caretOnly: bool = False,
) -> None:
	"""Refresh table-row regions for the current caret; drop stale NVDA pending scrolls."""
	_updateExistingTableRowRegions(handler, virtualBuffer, caretOnly=caretOnly)
	_clearStaleVirtualBufferTextInfoPendingUpdates(handler, virtualBuffer)


def _refreshTableRowBrailleCursorDisplay(
	handler: braille.BrailleHandler,
	virtualBuffer,
	changedRegions: Iterable[VirtualBufferTableCellBrailleRegion],
	*,
	repositionWindow: bool,
	rebuildContent: bool = False,
) -> None:
	"""Update cell regions and optionally reposition the braille window.

	When ``repositionWindow`` is false, only ``saveWindow`` / ``restoreWindow`` runs.
	Do not call ``scrollToCursorOrSelection`` here: with one region per cell, that would
	move the window back to the caret column while the user pans across the row.
	"""
	mainBuffer = handler.mainBuffer
	tableRegions = _cellRegionsForBuffer(mainBuffer.regions, virtualBuffer)
	if not repositionWindow:
		mainBuffer.saveWindow()
	rebuildSet = set(changedRegions) if rebuildContent else set()
	for region in tableRegions:
		region.hidePreviousRegions = False
		_updateTableRowRegion(region, rebuildContent=region in rebuildSet)
	mainBuffer.update()
	primaryFocus = _primaryTableRowFocusRegion(tableRegions, virtualBuffer)
	if repositionWindow:
		if primaryFocus is not None:
			_focusAndScrollTableRowRegion(handler, mainBuffer, primaryFocus)
	elif not repositionWindow:
		mainBuffer.restoreWindow()
	_clearStaleVirtualBufferTextInfoPendingUpdates(handler, virtualBuffer)
	if handler.buffer is handler.mainBuffer:
		handler.update()


def _refreshTableRowBrailleContent(
	handler: braille.BrailleHandler,
	virtualBuffer,
) -> bool:
	"""Rebuild all table-row cell regions after document formatting changes."""
	tableRegions = _cellRegionsForBuffer(handler.mainBuffer.regions, virtualBuffer)
	if not tableRegions:
		return False
	_refreshTableRowBrailleCursorDisplay(
		handler,
		virtualBuffer,
		tableRegions,
		repositionWindow=False,
		rebuildContent=True,
	)
	return True


def _virtualBufferForBrailleRefresh() -> VirtualBuffer | None:
	focus = api.getFocusObject()
	treeInterceptor = focus.treeInterceptor
	if (
		isinstance(treeInterceptor, VirtualBuffer)
		and not treeInterceptor.passThrough
		and treeInterceptor.isReady
	):
		return treeInterceptor
	return None


def refresh_document_formatting_braille_display() -> None:
	"""Refresh braille after document formatting settings change.

	Table-row mode rebuilds existing cell regions (like NVDA ``_handlePendingUpdate``).
	Otherwise uses ``handleUpdate`` + ``_handlePendingUpdate`` on the focus object, not
	``handleGainFocus`` (which would replace regions via ``_doNewObject``).
	"""
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	virtualBuffer = _virtualBufferForBrailleRefresh()
	if (
		virtualBuffer is not None
		and is_table_row_braille_enabled()
		and usesTableRowBrailleRegions(virtualBuffer)
		and _refreshTableRowBrailleContent(handler, virtualBuffer)
	):
		return
	regionObj = virtualBuffer if virtualBuffer is not None else api.getFocusObject()
	handler.handleUpdate(regionObj)
	handler._handlePendingUpdate()


def schedule_document_formatting_braille_refresh() -> None:
	# Defer until the settings dialog closes; focus is not on the document during onSave.
	core.callLater(0, refresh_document_formatting_braille_display)


def _sameTableCell(
	a: textInfos.TextInfo,
	b: textInfos.TextInfo,
	virtualBuffer=None,
) -> bool:
	vb = virtualBuffer
	if vb is None:
		vb = getattr(a, "obj", None)
	if vb is not None and hasattr(vb, "_getTableCellCoords"):
		try:
			return vb._getTableCellCoords(a) == vb._getTableCellCoords(b)
		except LookupError:
			pass
	try:
		if a.bookmark == b.bookmark:
			return True
	except (AttributeError, NotImplementedError, TypeError):
		pass
	aInfo = _tableCellTextInfo(a)
	bInfo = _tableCellTextInfo(b)
	return (
		aInfo.compareEndPoints(bInfo, "startToStart") == 0 and aInfo.compareEndPoints(bInfo, "endToEnd") == 0
	)


def _tableRowLayoutChanged(
	tableRegions: list[VirtualBufferTableCellBrailleRegion],
	currentCell,
) -> bool:
	return any(
		region._tableID != currentCell.tableID or region._row != currentCell.row for region in tableRegions
	)


def _applyCurrentCellHighlight(
	tableRegions: list[VirtualBufferTableCellBrailleRegion],
	rowCells: list[_TableRowCellData],
	currentCell,
	*,
	includeCurrentCellCursor: bool = False,
) -> set[VirtualBufferTableCellBrailleRegion]:
	changed: set[VirtualBufferTableCellBrailleRegion] = set()
	for region, cellData in zip(tableRegions, rowCells):
		if region.isCurrentCell != cellData.isCurrent:
			changed.add(region)
		region.isCurrentCell = cellData.isCurrent
		region._cellInfo = cellData.cellInfo
		region._cellNvdaObject = cellData.cellObj
		region._tableID = currentCell.tableID
		region._row = cellData.row
		region._column = cellData.column
		region._rowSpan = max(1, cellData.rowSpan or 1)
		region._colSpan = max(1, cellData.colSpan or 1)
	if includeCurrentCellCursor:
		for region in tableRegions:
			if region.isCurrentCell:
				changed.add(region)
	return changed


def _tableRowRegionsNeedRebuild(
	virtualBuffer,
	tableRegions: list[VirtualBufferTableCellBrailleRegion],
	rowCells: list[_TableRowCellData],
) -> bool:
	if len(tableRegions) != len(rowCells):
		return True
	cellSeparator, lineStart, lineEnd = _tableRowBrailleMarkers()
	lastIndex = len(rowCells) - 1
	try:
		currentCell = virtualBuffer._getTableCellCoords(virtualBuffer.selection)
	except LookupError:
		return True
	tableRowCount = _tableRowCount(
		virtualBuffer,
		rowCells[0].cellInfo,
		tableID=currentCell.tableID,
	)
	for index, (region, cellData) in enumerate(zip(tableRegions, rowCells)):
		expectedLayout = _tableRowCellBrailleLayoutForPlacement(
			index,
			lastIndex,
			cellData.cellInfo,
			cellSeparator=cellSeparator or "",
			lineStart=lineStart or "",
			lineEnd=lineEnd or "",
			virtualBuffer=virtualBuffer,
			tableID=currentCell.tableID,
			tableRow=currentCell.row,
			tableRowCount=tableRowCount,
		)
		if region._layout != expectedLayout:
			return True
	for region, cellData in zip(tableRegions, rowCells):
		if region._tableID != currentCell.tableID or region._row != currentCell.row:
			return True
		if region._column != cellData.column:
			return True
		if not _sameTableCell(region._cellInfo, cellData.cellInfo, virtualBuffer):
			return True
	return False


def _restoreNormalVirtualBufferBraille(handler: braille.BrailleHandler, virtualBuffer) -> None:
	if handler.buffer is handler.messageBuffer:
		handler._dismissMessage(shouldUpdate=False)
	oldRegions = list(handler.mainBuffer.regions)
	handler._doNewObject(
		itertools.chain(
			braille.getFocusContextRegions(virtualBuffer, oldFocusRegions=oldRegions),
			braille.getFocusRegions(virtualBuffer),
		)
	)


def _updateExistingTableRowRegions(
	handler: braille.BrailleHandler,
	virtualBuffer,
	*,
	scrollToCaret: bool = False,
	caretOnly: bool = False,
) -> None:
	allRegions = handler.mainBuffer.regions
	tableRegions = _cellRegionsForBuffer(allRegions, virtualBuffer)
	if not tableRegions:
		if _caretInTableRow(virtualBuffer):
			refresh_virtual_buffer_table_braille(virtualBuffer)
		return

	try:
		currentCell = virtualBuffer._getTableCellCoords(virtualBuffer.selection)
	except LookupError:
		if tableRegions:
			_restoreNormalVirtualBufferBraille(handler, virtualBuffer)
		return

	if _tableRowLayoutChanged(tableRegions, currentCell):
		refresh_virtual_buffer_table_braille(virtualBuffer)
		return

	caret = virtualBuffer.selection
	rowCells = _getTableRowCellData(virtualBuffer, caret, withText=False)
	if rowCells is None:
		if tableRegions:
			_restoreNormalVirtualBufferBraille(handler, virtualBuffer)
		return

	if _tableRowRegionsNeedRebuild(virtualBuffer, tableRegions, rowCells):
		refresh_virtual_buffer_table_braille(virtualBuffer)
		return

	oldCurrentColumn = _currentTableRowColumn(tableRegions)
	newCurrentColumn = next((cell.column for cell in rowCells if cell.isCurrent), None)
	repositionWindow = scrollToCaret or newCurrentColumn != oldCurrentColumn
	if (
		caretOnly
		and not repositionWindow
		and newCurrentColumn == oldCurrentColumn
		and all(region.isCurrentCell == cell.isCurrent for region, cell in zip(tableRegions, rowCells))
	):
		currentRegion = next((region for region in tableRegions if region.isCurrentCell), None)
		if currentRegion is not None:
			_refreshTableRowBrailleCursorDisplay(
				handler,
				virtualBuffer,
				{currentRegion},
				repositionWindow=False,
			)
			return
	changedRegions = _applyCurrentCellHighlight(
		tableRegions,
		rowCells,
		currentCell,
		includeCurrentCellCursor=repositionWindow,
	)
	_refreshTableRowBrailleCursorDisplay(
		handler,
		virtualBuffer,
		changedRegions,
		repositionWindow=repositionWindow,
	)


def _buffer_has_table_row_regions(regions: list) -> bool:
	return any(isinstance(region, VirtualBufferTableCellBrailleRegion) for region in regions)


def _virtualBufferForActiveTableRowBraille(handler: braille.BrailleHandler) -> Any | None:
	"""Return the virtual buffer when table-row regions are active on the main buffer."""
	if not is_table_row_braille_enabled():
		return None
	for region in handler.mainBuffer.regions:
		if not isinstance(region, VirtualBufferTableCellBrailleRegion):
			continue
		virtualBuffer = region._virtualBuffer
		if (
			not virtualBuffer.passThrough
			and virtualBuffer.isReady
			and usesTableRowBrailleRegions(virtualBuffer)
		):
			return virtualBuffer
	return None


def _virtualBufferTableBraille_handlePendingUpdate(self) -> None:
	"""Refresh table-row regions using NVDA's window save/restore when updates were deferred."""
	virtualBuffer = _virtualBufferForActiveTableRowBraille(self)
	if virtualBuffer is not None and self._regionsPendingUpdate:
		try:
			pending = set(self._regionsPendingUpdate)
			self._regionsPendingUpdate.clear()
			for region in pending:
				region.pendingCaretUpdate = False
			_updateExistingTableRowRegions(self, virtualBuffer)
		finally:
			self._regionsPendingUpdate.clear()
		return
	_originalHandlePendingUpdate(self)


def _virtualBufferTableBraille_handleGainFocus(self, obj, shouldAutoTether: bool = True) -> None:
	# Coordinate flashes use messageBuffer; do not leave them visible after focus moves elsewhere.
	if self.buffer is self.messageBuffer:
		self._dismissMessage(shouldUpdate=False)
	_originalHandleGainFocus(self, obj, shouldAutoTether=shouldAutoTether)


def _virtualBufferTableBraille_handleCaretMove(self, obj, shouldAutoTether: bool = True) -> None:
	if self is None or not self.enabled:
		return

	tableRowActive = (
		is_table_row_braille_enabled()
		and isinstance(obj, VirtualBuffer)
		and not obj.passThrough
		and obj.isReady
	)
	if tableRowActive:
		if shouldAutoTether:
			self.setTether(TetherTo.FOCUS.value, auto=True)
		if self._tether != TetherTo.FOCUS.value:
			return
		_onVirtualBufferTableRowCaretMove(self, obj, caretOnly=True)
		if _buffer_has_table_row_regions(self.mainBuffer.regions):
			_clearStaleVirtualBufferTextInfoPendingUpdates(self, obj)
			return
	_originalHandleCaretMove(self, obj, shouldAutoTether=shouldAutoTether)
	if tableRowActive and _buffer_has_table_row_regions(self.mainBuffer.regions):
		_clearStaleVirtualBufferTextInfoPendingUpdates(self, obj)


def _virtualBufferTableBraille_handleUpdate(self, obj) -> None:
	if not isinstance(obj, VirtualBuffer):
		_originalHandleUpdate(self, obj)
		return
	if not _buffer_has_table_row_regions(self.mainBuffer.regions):
		_originalHandleUpdate(self, obj)
		return
	if not is_table_row_braille_enabled() or not usesTableRowBrailleRegions(obj):
		_restoreNormalVirtualBufferBraille(self, obj)
		return
	_onVirtualBufferTableRowCaretMove(self, obj)
	_clearStaleVirtualBufferTextInfoPendingUpdates(self, obj)


def schedule_virtual_document_braille_refresh() -> None:
	"""Apply virtual document settings to the current braille display."""
	core.callLater(0, _apply_virtual_document_braille_settings)


def _apply_virtual_document_braille_settings() -> None:
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	for region in handler.mainBuffer.regions:
		if isinstance(region, VirtualBufferTableCellBrailleRegion):
			virtualBuffer = region._virtualBuffer
			if is_table_row_braille_enabled():
				refresh_virtual_buffer_table_braille(virtualBuffer)
			else:
				_restoreNormalVirtualBufferBraille(handler, virtualBuffer)
			return


def refresh_virtual_buffer_table_braille(virtualBuffer) -> None:
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	if not usesTableRowBrailleRegions(virtualBuffer):
		return
	if handler.buffer is not handler.mainBuffer:
		handler.buffer = handler.mainBuffer
	mainBuffer = handler.mainBuffer
	newFocusRegions = _buildTableRowBrailleRegions(virtualBuffer)
	if _apply_braille_buffer_focus_regions(
		handler,
		mainBuffer,
		[],
		newFocusRegions,
		regionsAlreadyUpdated=True,
	):
		return
	handler._doNewObject(_buildTableRowBrailleRegions(virtualBuffer))
	_clearStaleVirtualBufferTextInfoPendingUpdates(handler, virtualBuffer)


def _gecko_getTableCellAt_vbuf_fallback(self, tableID, startPos, destRow, destCol):
	"""Use virtual-buffer table lookup when Gecko IA2 table access fails."""
	try:
		return _originalGeckoGetTableCellAt(self, tableID, startPos, destRow, destCol)
	except LookupError:
		return VirtualBuffer._getTableCellAt(self, tableID, startPos, destRow, destCol)


def _gecko_getNearestTableCell_vbuf_when_row_braille(self, startPos, cell, movement, axis):
	"""Align column/row navigation with virtual-buffer cells shown on the braille display."""
	if is_table_row_braille_enabled():
		return VirtualBuffer._getNearestTableCell(self, startPos, cell, movement, axis)
	return _originalGeckoGetNearestTableCell(self, startPos, cell, movement, axis)


def _tableFindNewCell_safe_recovery(
	self,
	movement=None,
	axis=None,
	selection=None,
	raiseOnEdge=False,
):
	try:
		return _originalTableFindNewCell(self, movement, axis, selection, raiseOnEdge)
	except RuntimeError as e:
		# NVDA raises this when IA2 cannot re-locate the current cell after hitting the table edge.
		if e.args and e.args[0] == "Unable to find current cell.":
			raise LookupError from e
		raise


def _install_virtual_buffer_table_navigation_patches() -> None:
	global _originalGeckoGetTableCellAt, _originalGeckoGetNearestTableCell, _originalTableFindNewCell
	if Gecko_ia2 is not None:
		if _originalGeckoGetTableCellAt is None:
			_originalGeckoGetTableCellAt = Gecko_ia2._getTableCellAt
			Gecko_ia2._getTableCellAt = _gecko_getTableCellAt_vbuf_fallback
		if _originalGeckoGetNearestTableCell is None:
			_originalGeckoGetNearestTableCell = Gecko_ia2._getNearestTableCell
			Gecko_ia2._getNearestTableCell = _gecko_getNearestTableCell_vbuf_when_row_braille
	else:
		log.debug("Gecko virtual buffer unavailable; table navigation patches skipped")
	if DocumentWithTableNavigation is not None:
		if _originalTableFindNewCell is None:
			_originalTableFindNewCell = DocumentWithTableNavigation._tableFindNewCell
			DocumentWithTableNavigation._tableFindNewCell = _tableFindNewCell_safe_recovery
	else:
		log.debug("DocumentWithTableNavigation unavailable; table recovery patch skipped")


def _uninstall_virtual_buffer_table_navigation_patches() -> None:
	global _originalGeckoGetTableCellAt, _originalGeckoGetNearestTableCell, _originalTableFindNewCell
	if Gecko_ia2 is not None:
		if _originalGeckoGetTableCellAt is not None:
			Gecko_ia2._getTableCellAt = _originalGeckoGetTableCellAt
			_originalGeckoGetTableCellAt = None
		if _originalGeckoGetNearestTableCell is not None:
			Gecko_ia2._getNearestTableCell = _originalGeckoGetNearestTableCell
			_originalGeckoGetNearestTableCell = None
	if DocumentWithTableNavigation is not None and _originalTableFindNewCell is not None:
		DocumentWithTableNavigation._tableFindNewCell = _originalTableFindNewCell
		_originalTableFindNewCell = None


def _tableRowBraille_handlerScrollBack(self) -> None:
	if _virtualBufferForActiveTableRowBraille(self):
		_clearTableRowFocusToHardLeft(self.mainBuffer)
	_originalHandlerScrollBack(self)


def _tableRowBraille_handlerScrollForward(self) -> None:
	if _virtualBufferForActiveTableRowBraille(self):
		_clearTableRowFocusToHardLeft(self.mainBuffer)
	_originalHandlerScrollForward(self)


def _install_table_row_braille_scroll_patches() -> None:
	global _originalHandlerScrollBack, _originalHandlerScrollForward
	if _originalHandlerScrollBack is None:
		_originalHandlerScrollBack = braille.BrailleHandler.scrollBack
		braille.BrailleHandler.scrollBack = _tableRowBraille_handlerScrollBack
	if _originalHandlerScrollForward is None:
		_originalHandlerScrollForward = braille.BrailleHandler.scrollForward
		braille.BrailleHandler.scrollForward = _tableRowBraille_handlerScrollForward


def _uninstall_table_row_braille_scroll_patches() -> None:
	global _originalHandlerScrollBack, _originalHandlerScrollForward
	if _originalHandlerScrollBack is not None:
		braille.BrailleHandler.scrollBack = _originalHandlerScrollBack
		_originalHandlerScrollBack = None
	if _originalHandlerScrollForward is not None:
		braille.BrailleHandler.scrollForward = _originalHandlerScrollForward
		_originalHandlerScrollForward = None


def install_virtual_buffer_table_braille() -> None:
	global _virtualBufferGetBrailleRegionsInstalled, _originalVirtualBufferGetBrailleRegions
	global _originalGetFocusContextRegions, _originalHandleCaretMove, _originalHandleUpdate
	global _originalHandlePendingUpdate, _originalRouteTo, _originalHandleGainFocus
	global _originalHandlerScrollBack, _originalHandlerScrollForward
	if _virtualBufferGetBrailleRegionsInstalled:
		return

	_originalVirtualBufferGetBrailleRegions = getattr(VirtualBuffer, "getBrailleRegions", None)
	VirtualBuffer.getBrailleRegions = virtualBuffer_getBrailleRegions
	_originalGetFocusContextRegions = braille.getFocusContextRegions
	braille.getFocusContextRegions = _getFocusContextRegionsForVirtualBufferTable
	_originalHandleCaretMove = braille.BrailleHandler.handleCaretMove
	_originalHandleUpdate = braille.BrailleHandler.handleUpdate
	_originalHandlePendingUpdate = braille.BrailleHandler._handlePendingUpdate
	_originalHandleGainFocus = braille.BrailleHandler.handleGainFocus
	_originalRouteTo = braille.BrailleHandler.routeTo
	braille.BrailleHandler.handleCaretMove = _virtualBufferTableBraille_handleCaretMove
	braille.BrailleHandler.handleUpdate = _virtualBufferTableBraille_handleUpdate
	braille.BrailleHandler._handlePendingUpdate = _virtualBufferTableBraille_handlePendingUpdate
	braille.BrailleHandler.handleGainFocus = _virtualBufferTableBraille_handleGainFocus
	braille.BrailleHandler.routeTo = _virtualBufferTableBraille_routeTo
	braille._post_dismissBrailleMessage.register(_resyncTableRowBrailleAfterMessageDismiss)
	_install_virtual_buffer_table_navigation_patches()
	_install_table_row_braille_scroll_patches()
	_virtualBufferGetBrailleRegionsInstalled = True
	log.debug("Virtual buffer table row braille regions installed")


def uninstall_virtual_buffer_table_braille() -> None:
	global _virtualBufferGetBrailleRegionsInstalled, _originalVirtualBufferGetBrailleRegions
	global _originalGetFocusContextRegions, _originalHandleCaretMove, _originalHandleUpdate
	global _originalHandlePendingUpdate, _originalRouteTo, _originalHandleGainFocus
	if not _virtualBufferGetBrailleRegionsInstalled:
		return
	_uninstall_virtual_buffer_table_navigation_patches()
	_uninstall_table_row_braille_scroll_patches()
	try:
		braille._post_dismissBrailleMessage.unregister(_resyncTableRowBrailleAfterMessageDismiss)
	except Exception:
		pass

	if _originalVirtualBufferGetBrailleRegions is not None:
		VirtualBuffer.getBrailleRegions = _originalVirtualBufferGetBrailleRegions
	else:
		try:
			del VirtualBuffer.getBrailleRegions
		except AttributeError:
			pass
	if _originalGetFocusContextRegions is not None:
		braille.getFocusContextRegions = _originalGetFocusContextRegions
	if _originalHandleCaretMove is not None:
		braille.BrailleHandler.handleCaretMove = _originalHandleCaretMove
	if _originalHandleUpdate is not None:
		braille.BrailleHandler.handleUpdate = _originalHandleUpdate
	if _originalHandlePendingUpdate is not None:
		braille.BrailleHandler._handlePendingUpdate = _originalHandlePendingUpdate
	if _originalHandleGainFocus is not None:
		braille.BrailleHandler.handleGainFocus = _originalHandleGainFocus
	if _originalRouteTo is not None:
		braille.BrailleHandler.routeTo = _originalRouteTo
	_originalVirtualBufferGetBrailleRegions = None
	_originalGetFocusContextRegions = None
	_originalHandleCaretMove = None
	_originalHandleUpdate = None
	_originalHandlePendingUpdate = None
	_originalHandleGainFocus = None
	_originalRouteTo = None
	_originalHandlerScrollBack = None
	_originalHandlerScrollForward = None
	_virtualBufferGetBrailleRegionsInstalled = False
