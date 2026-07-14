# coding: utf-8
# virtualBufferTableBraille.py - Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush CLAUSE, released under GPL.
"""Display a virtual-buffer table row on one braille line as a single NVDA region.

The whole current table row is one ``braille.CursorManagerRegion`` subclass whose ``obj`` is
the virtual buffer. Because ``region.obj`` matches the focused browse-mode document, NVDA's
native braille pipeline drives updates (``handleCaretMove``/``_handlePendingUpdate``),
scrolling (``BrailleBuffer`` scroll -> ``nextLine``/``previousLine`` at the row edges) and, by
only ever touching regions already on the display, keeps background tabs/windows from leaving
stale content on the display.

Hooks: ``VirtualBuffer.getBrailleRegions``, ``getFocusContextRegions`` (suppress ancestor
context so the row uses the whole display), a thin ``handleCaretMove`` wrapper that swaps into
row mode when the caret enters a table, and Gecko table-navigation fallbacks.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
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

from . import regionhelper
from .documentformatting import build_text_with_fields_format_config

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

TableRowRoutingZone = Literal["content", "column", "row", "tableEnd"]


# Configuration helpers


def _virtualDocumentConf():
	return config.conf["brailleExtender"]["virtualDocument"]


def is_table_row_braille_enabled() -> bool:
	return _virtualDocumentConf()["tableRowBraille"]


def _tableRowBrailleMarkers() -> tuple[str, str, str]:
	vd = _virtualDocumentConf()
	cellSeparator = vd["cellSeparator"] or ROW_CELL_SEPARATOR
	lineStart = vd["lineStart"]
	lineEnd = vd["lineEnd"]
	if lineStart is None:
		lineStart = ROW_LINE_START
	if lineEnd is None:
		lineEnd = ROW_LINE_END
	return cellSeparator, lineStart, lineEnd


def _cellBrailleFormatConfig() -> dict[str, Any]:
	return build_text_with_fields_format_config(suppress_table_cell_coords=True)


# Foreground guard


def _virtualBufferFromFocusTree() -> VirtualBuffer | None:
	"""The active browse-mode document for the current focus, if any."""
	focus = api.getFocusObject()
	treeInterceptor = getattr(focus, "treeInterceptor", None)
	if (
		isinstance(treeInterceptor, VirtualBuffer)
		and not treeInterceptor.passThrough
		and treeInterceptor.isReady
	):
		return treeInterceptor
	return None


def _isForegroundVirtualBuffer(virtualBuffer) -> bool:
	"""True when ``virtualBuffer`` is the focused browse-mode document."""
	return virtualBuffer is not None and virtualBuffer is _virtualBufferFromFocusTree()


# Table metadata (rows/columns), read from NVDA virtual-buffer table fields


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


def _tableRoleBrailleLabelCandidates() -> tuple[str, ...]:
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


def _tableBoundarySuffix() -> str:
	"""Table end marker, e.g. ``tb end`` (NVDA controlEnd style)."""
	return f"{_tableRoleBrailleLabel()} end"


# Coordinate flash messages (routing onto separators / markers)


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


def _tableRowRoutingCoordFlash(
	zone: TableRowRoutingZone,
	cellInfo: textInfos.TextInfo,
	row: int,
	column: int,
	*,
	rowSpan: int,
	colSpan: int,
) -> str | None:
	rowSpan = max(1, rowSpan or 1)
	colSpan = max(1, colSpan or 1)
	if zone == "tableEnd":
		return _tableBoundarySuffix()
	columnHeaderText = rowHeaderText = None
	if not _cellIsColumnHeaderRow(cellInfo):
		columnHeaderText, rowHeaderText = _tableHeaderTextsForFlash(cellInfo)
	if zone == "column":
		message = _columnRangeLabel(column, colSpan)
		if columnHeaderText:
			message = _appendFlashDetail(message, columnHeaderText)
		if row > 0:
			message = _appendFlashDetail(message, _rowRangeLabel(row, rowSpan))
		if rowHeaderText:
			message = _appendFlashDetail(message, rowHeaderText)
		return message
	if zone == "row":
		message = _rowRangeLabel(row, rowSpan)
		if colSpan > 1:
			message = _appendFlashDetail(message, _columnRangeLabel(column, colSpan))
		return message
	return None


# Per-cell braille text building (NVDA TextInfoRegion three-chunk algorithm)


class _CellBrailleSnapshot:
	__slots__ = ("text", "rawToContentPos", "rawTextTypeforms", "brlexTypeformItems", "endsWithField")

	def __init__(
		self,
		text: str,
		rawToContentPos: tuple[int, ...],
		rawTextTypeforms: tuple[int, ...] = (),
		brlexTypeformItems: tuple[tuple[int, int], ...] = (),
		endsWithField: bool = False,
	) -> None:
		self.text = text
		self.rawToContentPos = rawToContentPos
		self.rawTextTypeforms = rawTextTypeforms
		self.brlexTypeformItems = brlexTypeformItems
		self.endsWithField = endsWithField


class _TableRowCellData:
	__slots__ = (
		"column",
		"row",
		"cellInfo",
		"cellObj",
		"text",
		"rawToContentPos",
		"isCurrent",
		"rowSpan",
		"colSpan",
		"rawTextTypeforms",
		"brlexTypeformItems",
		"contentCursor",
	)

	def __init__(self, **kwargs: Any) -> None:
		for key in self.__slots__:
			setattr(self, key, kwargs.get(key))


class _CellBrailleTextBuilder(braille.TextInfoRegion):
	"""Build cell braille like ``TextInfoRegion``; the row region supplies boundary markers."""

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
	formatConfig: dict[str, Any] | None = None,
) -> int | None:
	"""Fill builder with cell braille; return raw ``cursorPos`` (NVDA three-chunk algorithm)."""
	if formatConfig is None:
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
	while rawPos + 1 < len(rawToContentPos) and rawToContentPos[rawPos] == rawToContentPos[rawPos + 1]:
		rawPos += 1
	return rawPos


def _padRawToContentPos(rawToContentPos, textLen: int) -> tuple[int, ...]:
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
	)


def _buildCellBrailleWithCursor(
	cellInfo: textInfos.TextInfo,
	caret: textInfos.TextInfo | None = None,
	*,
	virtualBuffer=None,
	currentCell=None,
	formatConfig: dict[str, Any] | None = None,
) -> tuple[_CellBrailleSnapshot, int | None]:
	"""Build cell braille and map the caret in one ``TextInfoRegion`` pass."""
	builder = _CellBrailleTextBuilder(cellInfo.obj)
	builderCursorPos = _populateCellBrailleBuilder(
		builder,
		cellInfo,
		caret,
		virtualBuffer=virtualBuffer,
		currentCell=currentCell,
		formatConfig=formatConfig,
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


def _getTableRowCellData(
	virtualBuffer,
	caretInfo: textInfos.TextInfo,
	*,
	withText: bool = True,
	formatConfig: dict[str, Any] | None = None,
) -> list[_TableRowCellData] | None:
	try:
		currentCell = virtualBuffer._getTableCellCoords(caretInfo)
	except LookupError:
		return None

	if withText and formatConfig is None:
		formatConfig = _cellBrailleFormatConfig()
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
		isCurrent = _isCurrentTableCell(currentCell, coords)
		if withText:
			snapshot, contentCursor = _buildCellBrailleWithCursor(
				info,
				caretInfo if isCurrent else None,
				virtualBuffer=virtualBuffer if isCurrent else None,
				currentCell=currentCell if isCurrent else None,
				formatConfig=formatConfig,
			)
		else:
			snapshot = _CellBrailleSnapshot("", ())
			contentCursor = None
		cells.append(
			_TableRowCellData(
				column=coords.col,
				row=coords.row,
				cellInfo=info,
				cellObj=info.NVDAObjectAtStart,
				text=snapshot.text,
				rawToContentPos=snapshot.rawToContentPos,
				isCurrent=isCurrent,
				rowSpan=coords.rowSpan,
				colSpan=coords.colSpan,
				rawTextTypeforms=snapshot.rawTextTypeforms,
				brlexTypeformItems=snapshot.brlexTypeformItems,
				contentCursor=contentCursor,
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


# Row-to-row navigation and leaving the table


def _iterRowCellInfos(virtualBuffer, tableID: int, row: int):
	for info in virtualBuffer._iterTableCells(tableID, row=row):
		try:
			coords = virtualBuffer._getTableCellCoords(info)
		except LookupError:
			continue
		if coords.tableID == tableID and coords.row == row:
			yield coords.col, info


def _rowEdgeCellInfo(virtualBuffer, tableID: int, row: int, *, first: bool) -> textInfos.TextInfo | None:
	best: tuple[int, textInfos.TextInfo] | None = None
	for col, info in _iterRowCellInfos(virtualBuffer, tableID, row):
		if best is None or (col < best[0] if first else col > best[0]):
			best = (col, info)
	return best[1] if best is not None else None


def _lastCellInfoInTableRow(virtualBuffer, tableID: int, row: int) -> textInfos.TextInfo | None:
	return _rowEdgeCellInfo(virtualBuffer, tableID, row, first=False)


def _textInfoAfterTable(
	virtualBuffer,
	tableID: int,
	anchorInfo: textInfos.TextInfo,
) -> textInfos.TextInfo | None:
	"""Collapsed TextInfo at the first position after the given table."""
	dest = anchorInfo.copy()
	dest.collapse()
	try:
		dest.expand(textInfos.UNIT_CHARACTER)
	except (RuntimeError, NotImplementedError):
		pass
	dest.collapse(False)
	tableIdStr = str(tableID)
	for _i in range(5000):
		try:
			cell = virtualBuffer._getTableCellCoords(dest)
			if str(cell.tableID) != tableIdStr:
				dest.collapse()
				return dest
		except LookupError:
			dest.collapse()
			return dest
		if not dest.move(textInfos.UNIT_CHARACTER, 1):
			dest.collapse()
			return dest
	return None


def _speakOnNavigate(virtualBuffer) -> None:
	speak = getattr(braille, "_speakOnNavigatingByUnit", None)
	if speak is None:
		return
	try:
		speak(virtualBuffer.selection, textInfos.UNIT_LINE)
	except (AttributeError, RuntimeError):
		pass


def _notifyBrailleCaretMoved(virtualBuffer) -> None:
	"""Tell braille that the browse-mode caret moved.

	Browse mode's ``_set_selection`` does not notify braille (only review); NVDA's cursor
	manager calls ``braille.handler.handleCaretMove`` explicitly after moving. We do the same
	for our programmatic moves (routing, row navigation, leaving the table) so the pending
	update runs on the next core cycle.
	"""
	handler = braille.handler
	if handler is not None and handler.enabled:
		handler.handleCaretMove(virtualBuffer)


def _moveToAdjacentTableRow(virtualBuffer, *, forward: bool) -> bool:
	"""Move the caret to the first/last cell of the adjacent table row (single caret write).

	Forward navigation lands on the first cell (so reading flows into the new row from its
	start); backward navigation lands on the last cell (so scrolling back reads toward the
	start of the previous row). Browse-mode selection assignment is expensive, so the caret
	is written only once.
	"""
	cell = _currentTableCell(virtualBuffer)
	if cell is None:
		return False
	movement = "next" if forward else "previous"
	try:
		dest = virtualBuffer._getNearestTableCell(virtualBuffer.selection, cell, movement, "row")
	except LookupError:
		return False
	try:
		coords = virtualBuffer._getTableCellCoords(dest)
	except LookupError:
		coords = None
	if coords is not None:
		edge = _rowEdgeCellInfo(virtualBuffer, coords.tableID, coords.row, first=forward)
		if edge is not None:
			dest = edge
	target = dest.copy()
	target.collapse()
	virtualBuffer.selection = target
	_notifyBrailleCaretMoved(virtualBuffer)
	_speakOnNavigate(virtualBuffer)
	return True


def _leaveVirtualBufferTableForward(virtualBuffer, *, tableID: int, tableRow: int) -> bool:
	"""Move the browse-mode caret past the table; NVDA then restores normal document braille."""
	anchor = _lastCellInfoInTableRow(virtualBuffer, tableID, tableRow) or virtualBuffer.selection
	dest = _textInfoAfterTable(virtualBuffer, tableID, anchor)
	if dest is None:
		return False
	try:
		virtualBuffer.selection = dest
	except (AttributeError, NotImplementedError, RuntimeError):
		try:
			dest.updateCaret()
		except NotImplementedError:
			log.debugWarning("virtual buffer table forward exit failed", exc_info=True)
			return False
	_notifyBrailleCaretMoved(virtualBuffer)
	_speakOnNavigate(virtualBuffer)
	return True


def _documentLineNav(virtualBuffer, *, forward: bool, start: bool = False) -> None:
	"""Fall back to NVDA document line navigation (used when leaving the table upward).

	A ``CursorManagerRegion`` is used (not a plain ``TextInfoRegion``) so ``_setCursor`` moves
	the browse-mode selection rather than trying to move a physical caret.
	"""
	helper = braille.CursorManagerRegion(virtualBuffer)
	helper._readingInfo = virtualBuffer.selection.copy()
	if helper._readingInfo.isCollapsed:
		helper._readingInfo.expand(helper._getReadingUnit())
	if forward:
		braille.TextInfoRegion.nextLine(helper)
	else:
		braille.TextInfoRegion.previousLine(helper, start)
	_notifyBrailleCaretMoved(virtualBuffer)


# The single row region


class _CellSegment:
	"""Raw-text layout of one cell inside the row region, for routing dispatch."""

	__slots__ = (
		"cellInfo",
		"rawToContentPos",
		"column",
		"row",
		"rowSpan",
		"colSpan",
		"segStart",
		"contentStart",
		"contentEnd",
		"segEnd",
		"lineEndEnd",
		"hasTableEnd",
	)

	def __init__(self, **kwargs: Any) -> None:
		for key in self.__slots__:
			setattr(self, key, kwargs.get(key))


class TableRowBrailleRegion(braille.CursorManagerRegion):
	"""One braille region for the whole current table row (one cell per segment)."""

	allowPageTurns = True

	def __init__(self, virtualBuffer) -> None:
		super().__init__(virtualBuffer)
		self._virtualBuffer = virtualBuffer
		self.formatField = textInfos.FormatField()
		self._cellNvdaObject = None
		self._segments: list[_CellSegment] = []
		self._tableID: int | None = None
		self._row: int = 0
		self._dimsCache: dict[int, tuple[int, int]] = {}

	# building

	def _isMultiline(self) -> bool:
		return True

	def _tableDimensions(self, cellInfo, tableID) -> tuple[int, int] | None:
		"""Row/column counts for a table, cached per region (they don't change while navigating)."""
		cached = self._dimsCache.get(tableID)
		if cached is not None:
			return cached
		dims = _getVirtualBufferTableDimensions(self._virtualBuffer, cellInfo, tableID=tableID)
		if dims is not None:
			self._dimsCache[tableID] = dims
		return dims

	def _resetTranslationState(self) -> None:
		self.rawText = ""
		self.rawTextTypeforms = []
		self._rawToContentPos = []
		self.brlex_typeforms = {}
		self._len_brlex_typeforms = 0
		self.cursorPos = None
		self.selectionStart = self.selectionEnd = None
		self._segments = []

	def _buildFromRow(self, rowCells: list[_TableRowCellData], currentCell) -> None:
		self._resetTranslationState()
		cellSeparator, lineStart, lineEnd = _tableRowBrailleMarkers()
		self._tableID = currentCell.tableID
		self._row = currentCell.row
		dims = self._tableDimensions(rowCells[0].cellInfo, currentCell.tableID)
		tableRowCount = dims[0] if dims is not None else None
		isFirstRow = currentCell.row == 1
		isLastRow = tableRowCount is not None and currentCell.row == tableRowCount
		lastIndex = len(rowCells) - 1

		parts: list[str] = []
		typeforms: list[int] = []
		rawToContent: list[int] = []
		cursorPos: int | None = None

		def _emit(text: str, typeform: int, contentBase: int) -> None:
			if not text:
				return
			parts.append(text)
			typeforms.extend([typeform] * len(text))
			rawToContent.extend([contentBase] * len(text))

		for index, cell in enumerate(rowCells):
			if index == 0:
				if isFirstRow:
					label = _tableRoleBrailleLabel()
					prefix = f"{label}({dims[0]},{dims[1]})" if dims is not None else label
				else:
					prefix = ""
				prefix += lineStart or ""
			else:
				prefix = cellSeparator or ""
			suffix = ""
			lineEndPart = ""
			tableEndPart = ""
			if index == lastIndex:
				lineEndPart = lineEnd or ""
				tableEndPart = _tableBoundarySuffix() if isLastRow else ""
				suffix = lineEndPart + tableEndPart

			segStart = sum(len(p) for p in parts)
			_emit(prefix, louis.plain_text, self._nextContentBase(rawToContent))
			contentStart = sum(len(p) for p in parts)

			cellText = cell.text or ""
			cellTypeforms = list(cell.rawTextTypeforms)
			if len(cellTypeforms) < len(cellText):
				cellTypeforms += [louis.plain_text] * (len(cellText) - len(cellTypeforms))
			elif len(cellTypeforms) > len(cellText):
				cellTypeforms = cellTypeforms[: len(cellText)]
			if cellText:
				parts.append(cellText)
				typeforms.extend(cellTypeforms)
				# Map content raw positions to a per-cell content offset space.
				rawToContent.extend(range(len(cellText)))
			for rawPos, mask in cell.brlexTypeformItems:
				self.brlex_typeforms[contentStart + rawPos] = mask
			contentEnd = sum(len(p) for p in parts)

			lineEndEnd = contentEnd + len(lineEndPart)
			_emit(suffix, louis.plain_text, self._nextContentBase(rawToContent))
			segEnd = sum(len(p) for p in parts)

			if cell.isCurrent:
				inCell = cell.contentCursor if cell.contentCursor is not None else 0
				if cellText:
					cursorPos = contentStart + min(inCell, len(cellText) - 1)
				else:
					cursorPos = contentStart

			self._segments.append(
				_CellSegment(
					cellInfo=cell.cellInfo,
					rawToContentPos=cell.rawToContentPos,
					column=cell.column,
					row=cell.row,
					rowSpan=max(1, cell.rowSpan or 1),
					colSpan=max(1, cell.colSpan or 1),
					segStart=segStart,
					contentStart=contentStart,
					contentEnd=contentEnd,
					segEnd=segEnd,
					lineEndEnd=lineEndEnd,
					hasTableEnd=bool(tableEndPart),
				)
			)
			if cell.isCurrent:
				self._cellNvdaObject = cell.cellObj
				self.formatField = textInfos.FormatField()

		self.rawText = "".join(parts)
		self.rawTextTypeforms = typeforms
		self._rawToContentPos = rawToContent
		rawLen = len(self.rawText)
		if rawLen == 0:
			self.rawText = braille.TEXT_SEPARATOR
			self.rawTextTypeforms = [louis.plain_text]
			self._rawToContentPos = [0]
			rawLen = 1
		if cursorPos is not None:
			self.cursorPos = min(cursorPos, rawLen - 1)

	@staticmethod
	def _nextContentBase(rawToContent: list[int]) -> int:
		return rawToContent[-1] if rawToContent else 0

	def _applyTypeformMasks(self) -> None:
		if not self.brlex_typeforms:
			return
		active = 0
		for rawPos in range(len(self.rawText)):
			if rawPos in self.brlex_typeforms:
				active = self.brlex_typeforms[rawPos]
			if active:
				startBraille, endBraille = regionhelper.getBraillePosFromRawPos(self, rawPos)
				for braillePos in range(startBraille, endBraille + 1):
					if 0 <= braillePos < len(self.brailleCells):
						self.brailleCells[braillePos] |= active

	def _renderEmpty(self) -> None:
		"""Render a blank region with no cursor/selection.

		Used when the caret has left the table: NVDA still calls
		``scrollToCursorOrSelection`` on this region during the current pump cycle, so a stale
		cursor position would raise ``LookupError`` in ``regionPosToBufferPos``.
		"""
		self._resetTranslationState()
		self.rawText = braille.TEXT_SEPARATOR
		self.rawTextTypeforms = [louis.plain_text]
		self._rawToContentPos = [0]
		braille.Region.update(self)
		self.brailleCursorPos = None
		self.brailleSelectionStart = None
		self.brailleSelectionEnd = None

	def update(self) -> None:
		virtualBuffer = self._virtualBuffer
		handler = braille.handler
		if not _caretInTableRow(virtualBuffer):
			if handler is not None:
				core.callLater(0, _restoreNormalVirtualBufferBraille, handler, virtualBuffer)
			self._renderEmpty()
			return
		caret = virtualBuffer.selection
		try:
			currentCell = virtualBuffer._getTableCellCoords(caret)
		except LookupError:
			self._renderEmpty()
			return
		rowCells = _getTableRowCellData(
			virtualBuffer, caret, withText=True, formatConfig=_cellBrailleFormatConfig()
		)
		if not rowCells:
			self._renderEmpty()
			return
		self._buildFromRow(rowCells, currentCell)
		self.focusToHardLeft = True
		self.hidePreviousRegions = False
		braille.Region.update(self)
		self._applyTypeformMasks()

	# routing

	def _segmentForRawPos(self, rawPos: int) -> _CellSegment | None:
		for seg in self._segments:
			if seg.segStart <= rawPos < seg.segEnd:
				return seg
		return self._segments[-1] if self._segments else None

	def _routeWithinCell(self, seg: _CellSegment, rawPos: int) -> None:
		inCell = rawPos - seg.contentStart
		contentMap = seg.rawToContentPos
		if 0 <= inCell < len(contentMap):
			contentPos = contentMap[inCell]
		else:
			contentPos = 0
		readingInfo = _tableCellTextInfo(seg.cellInfo)
		dest: textInfos.TextInfo
		try:
			dest = readingInfo.moveToCodepointOffset(contentPos)
		except (RuntimeError, NotImplementedError, ValueError):
			dest = seg.cellInfo.copy()
		dest.collapse()
		self._setSelection(dest)
		speak = getattr(braille, "_speakOnRouting", None)
		if speak is not None:
			try:
				speak(dest.copy())
			except (AttributeError, RuntimeError):
				pass

	def _routeToCellStart(self, seg: _CellSegment) -> None:
		dest = seg.cellInfo.copy()
		dest.collapse()
		self._setSelection(dest)

	def _setSelection(self, info: textInfos.TextInfo) -> None:
		try:
			self._virtualBuffer.selection = info
		except (AttributeError, NotImplementedError, RuntimeError):
			try:
				info.updateCaret()
			except NotImplementedError:
				log.debugWarning("virtual buffer table row routing failed", exc_info=True)
				return
		_notifyBrailleCaretMoved(self._virtualBuffer)

	def routeTo(self, braillePos: int) -> None:
		try:
			rawPos = self.brailleToRawPos[braillePos]
		except IndexError:
			rawPos = max(0, len(self.rawText) - 1)
		seg = self._segmentForRawPos(rawPos)
		if seg is None:
			return
		if seg.contentStart <= rawPos < seg.contentEnd or seg.contentStart == seg.contentEnd == rawPos:
			self._routeWithinCell(seg, rawPos)
			return
		if rawPos < seg.contentStart:
			zone: TableRowRoutingZone = "column"
		elif seg.hasTableEnd and rawPos >= seg.lineEndEnd:
			zone = "tableEnd"
		else:
			zone = "row"
		message = _tableRowRoutingCoordFlash(
			zone,
			seg.cellInfo,
			seg.row,
			seg.column,
			rowSpan=seg.rowSpan,
			colSpan=seg.colSpan,
		)
		if zone == "tableEnd":
			if _leaveVirtualBufferTableForward(self._virtualBuffer, tableID=self._tableID, tableRow=seg.row):
				if message:
					core.callLater(0, ui.message, message)
				return
		self._routeToCellStart(seg)
		if message:
			core.callLater(0, ui.message, message)

	# row navigation (called by BrailleBuffer scroll at row edges)

	def _isLastRow(self) -> bool:
		if self._segments and self._segments[-1].hasTableEnd:
			return True
		anchor = self._segments[0].cellInfo if self._segments else self._virtualBuffer.selection
		dims = self._tableDimensions(anchor, self._tableID)
		return dims is not None and self._row == dims[0]

	def nextLine(self) -> None:
		if self._isLastRow():
			if _leaveVirtualBufferTableForward(
				self._virtualBuffer, tableID=self._tableID, tableRow=self._row
			):
				return
		if _moveToAdjacentTableRow(self._virtualBuffer, forward=True):
			return
		_documentLineNav(self._virtualBuffer, forward=True)

	def previousLine(self, start: bool = False) -> None:
		if _moveToAdjacentTableRow(self._virtualBuffer, forward=False):
			return
		# At the first row: leave the table upward using normal document navigation.
		_documentLineNav(self._virtualBuffer, forward=False, start=start)


# Region installation and NVDA integration


def _restoreNormalVirtualBufferBraille(handler: braille.BrailleHandler, virtualBuffer) -> None:
	if handler is None or not handler.enabled:
		return
	if handler.buffer is handler.messageBuffer:
		handler._dismissMessage(shouldUpdate=False)
	oldRegions = list(handler.mainBuffer.regions)
	handler._doNewObject(
		itertools.chain(
			braille.getFocusContextRegions(virtualBuffer, oldFocusRegions=oldRegions),
			braille.getFocusRegions(virtualBuffer),
		)
	)


def _buildTableRowRegion(virtualBuffer) -> TableRowBrailleRegion:
	return TableRowBrailleRegion(virtualBuffer)


def _shouldUseTableRowBrailleRegions(obj, review: bool = False) -> bool:
	if not is_table_row_braille_enabled():
		return False
	if review or obj.passThrough or not obj.isReady:
		return False
	return _caretInTableRow(obj)


def virtualBuffer_getBrailleRegions(obj, review: bool = False) -> Iterable[braille.Region]:
	"""Return the table-row region, or raise NotImplementedError for NVDA fallback.

	Must not be a generator: NVDA only catches NotImplementedError from the initial call.
	"""
	if not _shouldUseTableRowBrailleRegions(obj, review):
		raise NotImplementedError
	return [_buildTableRowRegion(obj)]


def _getFocusContextRegionsForVirtualBufferTable(obj, oldFocusRegions=None):
	"""Skip foreground ancestor regions in table-row mode so the row uses the full display."""
	if isinstance(obj, VirtualBuffer) and usesTableRowBrailleRegions(obj):
		return iter(())
	return _originalGetFocusContextRegions(obj, oldFocusRegions=oldFocusRegions)


def _lastRegionIsTableRow(handler: braille.BrailleHandler, virtualBuffer) -> bool:
	regions = handler.mainBuffer.regions
	if not regions:
		return False
	last = regions[-1]
	return isinstance(last, TableRowBrailleRegion) and last._virtualBuffer is virtualBuffer


def refresh_virtual_buffer_table_braille(virtualBuffer) -> None:
	"""Install (or reinstall) the table-row region for the focused virtual buffer."""
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	if not usesTableRowBrailleRegions(virtualBuffer) or not _isForegroundVirtualBuffer(virtualBuffer):
		return
	if handler.buffer is not handler.mainBuffer:
		handler.buffer = handler.mainBuffer
	region = _buildTableRowRegion(virtualBuffer)
	region.update()
	handler._doNewObject([region])


# Thin caret-move wrapper: swap into row mode when entering a table


def _virtualBufferTableBraille_handleCaretMove(self, obj, shouldAutoTether: bool = True) -> None:
	_originalHandleCaretMove(self, obj, shouldAutoTether=shouldAutoTether)
	if self is None or not self.enabled:
		return
	if not is_table_row_braille_enabled():
		return
	if not (isinstance(obj, VirtualBuffer) and _isForegroundVirtualBuffer(obj)):
		return
	if self._tether != TetherTo.FOCUS.value:
		return
	if _lastRegionIsTableRow(self, obj):
		# Already in row mode; NVDA's native pending-update refresh handles caret moves
		# (and leaving the table is handled by TableRowBrailleRegion.update).
		return
	if _caretInTableRow(obj):
		refresh_virtual_buffer_table_braille(obj)


# Settings / document-formatting refreshes


def _refreshTableRowBrailleContent(handler: braille.BrailleHandler, virtualBuffer) -> bool:
	if not _lastRegionIsTableRow(handler, virtualBuffer):
		return False
	refresh_virtual_buffer_table_braille(virtualBuffer)
	return True


def refresh_document_formatting_braille_display() -> None:
	"""Refresh braille after document formatting settings change."""
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	virtualBuffer = _virtualBufferFromFocusTree()
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
	core.callLater(0, refresh_document_formatting_braille_display)


def _apply_virtual_document_braille_settings() -> None:
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	virtualBuffer = _virtualBufferFromFocusTree()
	if virtualBuffer is None:
		return
	if is_table_row_braille_enabled() and usesTableRowBrailleRegions(virtualBuffer):
		refresh_virtual_buffer_table_braille(virtualBuffer)
	elif _lastRegionIsTableRow(handler, virtualBuffer):
		_restoreNormalVirtualBufferBraille(handler, virtualBuffer)


def schedule_virtual_document_braille_refresh() -> None:
	core.callLater(0, _apply_virtual_document_braille_settings)


# Virtual-buffer table navigation fallbacks (Gecko)


def _gecko_getTableCellAt_vbuf_fallback(self, tableID, startPos, destRow, destCol):
	try:
		return _originalGeckoGetTableCellAt(self, tableID, startPos, destRow, destCol)
	except LookupError:
		return VirtualBuffer._getTableCellAt(self, tableID, startPos, destRow, destCol)


def _gecko_getNearestTableCell_vbuf_when_row_braille(self, startPos, cell, movement, axis):
	if is_table_row_braille_enabled():
		return VirtualBuffer._getNearestTableCell(self, startPos, cell, movement, axis)
	return _originalGeckoGetNearestTableCell(self, startPos, cell, movement, axis)


def _tableFindNewCell_safe_recovery(self, movement=None, axis=None, selection=None, raiseOnEdge=False):
	try:
		return _originalTableFindNewCell(self, movement, axis, selection, raiseOnEdge)
	except RuntimeError as e:
		if e.args and e.args[0] == "Unable to find current cell.":
			raise LookupError from e
		raise


# install / uninstall

_installed = False
_originalGetBrailleRegions: Any = None
_originalGetFocusContextRegions: Any = None
_originalHandleCaretMove: Any = None
_originalGeckoGetTableCellAt: Any = None
_originalGeckoGetNearestTableCell: Any = None
_originalTableFindNewCell: Any = None


def _install_navigation_patches() -> None:
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


def _uninstall_navigation_patches() -> None:
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


def install_virtual_buffer_table_braille() -> None:
	global _installed, _originalGetBrailleRegions, _originalGetFocusContextRegions, _originalHandleCaretMove
	if _installed:
		return
	_originalGetBrailleRegions = getattr(VirtualBuffer, "getBrailleRegions", None)
	VirtualBuffer.getBrailleRegions = virtualBuffer_getBrailleRegions
	_originalGetFocusContextRegions = braille.getFocusContextRegions
	braille.getFocusContextRegions = _getFocusContextRegionsForVirtualBufferTable
	_originalHandleCaretMove = braille.BrailleHandler.handleCaretMove
	braille.BrailleHandler.handleCaretMove = _virtualBufferTableBraille_handleCaretMove
	_install_navigation_patches()
	_installed = True
	log.debug("Virtual buffer table row braille (single-region) installed")


def uninstall_virtual_buffer_table_braille() -> None:
	global _installed, _originalGetBrailleRegions, _originalGetFocusContextRegions, _originalHandleCaretMove
	if not _installed:
		return
	_uninstall_navigation_patches()
	if _originalGetBrailleRegions is not None:
		VirtualBuffer.getBrailleRegions = _originalGetBrailleRegions
	else:
		try:
			del VirtualBuffer.getBrailleRegions
		except AttributeError:
			pass
	if _originalGetFocusContextRegions is not None:
		braille.getFocusContextRegions = _originalGetFocusContextRegions
	if _originalHandleCaretMove is not None:
		braille.BrailleHandler.handleCaretMove = _originalHandleCaretMove
	_originalGetBrailleRegions = None
	_originalGetFocusContextRegions = None
	_originalHandleCaretMove = None
	_installed = False
