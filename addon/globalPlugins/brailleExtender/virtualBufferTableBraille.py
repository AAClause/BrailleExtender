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

Design rules (robustness and speed):

* The display is never blanked. When the buffer is momentarily unavailable (loading, pass-through,
  dying) or an update fails, the region keeps its last good content. A region commits its new
  state atomically, only once the whole row has been built.
* Switching between the normal document line and the row region happens synchronously in the
  ``handleCaretMove`` hook, before NVDA runs its pending update, so no stale or empty frame is
  ever rendered and the outdated region is never rebuilt for nothing.
* Reading the caret position costs one ``getTextWithFields`` call (cell coordinates and table
  size come from the same field list). Cell coordinates and per-cell braille text are cached per
  row and invalidated whenever the virtual buffer content changes, so moving the caret inside a
  row only re-renders the cell holding the caret.
* The region hides the focus-context regions with ``hidePreviousRegions`` rather than patching
  NVDA's focus-context generator.

Hooks: ``VirtualBuffer.getBrailleRegions``, a thin ``BrailleHandler.handleCaretMove`` wrapper,
content-change counters on ``VirtualBuffer`` and Gecko table-navigation fallbacks.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from typing import Any, Literal, NamedTuple

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

# Exceptions that mean "the virtual buffer cannot answer right now" (dying, reloading, COM hiccup).
_TRANSIENT_ERRORS = (RuntimeError, AttributeError, NotImplementedError, OSError)


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


def _formatSignature(formatConfig: dict[str, Any]) -> tuple:
	"""Hashable fingerprint of a format config, used to invalidate cached cell text."""
	return tuple(
		(key, value if isinstance(value, (bool, int, str, type(None))) else repr(value))
		for key, value in sorted(formatConfig.items(), key=lambda item: item[0])
	)


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


# Virtual buffer content generation (cache invalidation)


def _contentGeneration(virtualBuffer) -> int:
	return getattr(virtualBuffer, "_beContentGen", 0)


def _bumpContentGeneration(virtualBuffer) -> None:
	try:
		virtualBuffer._beContentGen = _contentGeneration(virtualBuffer) + 1
	except AttributeError:
		pass


# Table metadata, read from NVDA virtual-buffer control fields in a single pass


class _TableCell(NamedTuple):
	tableID: Any
	row: int
	col: int
	rowSpan: int
	colSpan: int


class _CaretTable(NamedTuple):
	cell: _TableCell
	dims: tuple[int, int] | None
	caret: textInfos.TextInfo


class _Unavailable(Exception):
	"""The virtual buffer cannot be queried right now; callers must keep what is displayed."""


def _layoutTableIDs(fields) -> set:
	if config.conf["documentFormatting"]["includeLayoutTables"]:
		return set()
	ids = set()
	for field in fields:
		if (
			isinstance(field, textInfos.FieldCommand)
			and field.command == "controlStart"
			and field.field.get("table-layout")
		):
			tableID = field.field.get("table-id")
			if tableID is not None:
				ids.add(tableID)
	return ids


def _toInt(value, default: int | None = None) -> int | None:
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def _tableDimsFromAttrs(attrs) -> tuple[int, int] | None:
	rowCount = attrs.get("table-rowcount-presentational")
	if rowCount is None:
		rowCount = attrs.get("table-rowcount")
	colCount = attrs.get("table-columncount-presentational")
	if colCount is None:
		colCount = attrs.get("table-columncount")
	rowCount, colCount = _toInt(rowCount), _toInt(colCount)
	if rowCount is None or colCount is None:
		return None
	return rowCount, colCount


def _tableStateFromFields(fields, tableID=None) -> tuple[_TableCell, tuple[int, int] | None] | None:
	"""Deepest (or ``tableID``'s) table cell found in ``fields`` plus its table dimensions."""
	layoutIDs = _layoutTableIDs(fields)
	tableRole = get_control_type("ROLE_TABLE")
	cell: _TableCell | None = None
	for field in reversed(list(fields)):
		if not (isinstance(field, textInfos.FieldCommand) and field.command == "controlStart"):
			continue
		attrs = field.field
		fieldTableID = attrs.get("table-id")
		if fieldTableID is None or fieldTableID in layoutIDs:
			continue
		if cell is None:
			if tableID is not None and fieldTableID != tableID:
				continue
			if "table-columnnumber" not in attrs or attrs.get("table-layout"):
				continue
			row, col = _toInt(attrs.get("table-rownumber")), _toInt(attrs.get("table-columnnumber"))
			if row is None or col is None:
				continue
			cell = _TableCell(
				fieldTableID,
				row,
				col,
				_toInt(attrs.get("table-rowsspanned"), 1) or 1,
				_toInt(attrs.get("table-columnsspanned"), 1) or 1,
			)
			continue
		if fieldTableID == cell.tableID and attrs.get("role") == tableRole:
			return cell, _tableDimsFromAttrs(attrs)
	return (cell, None) if cell is not None else None


def _readCaretTable(virtualBuffer) -> _CaretTable | None:
	"""Table cell holding the browse-mode caret; ``None`` when the caret is outside any table.

	One ``getTextWithFields`` call. Raises ``_Unavailable`` when the buffer is not in a state
	where the answer can be trusted (loading, pass-through, dead, COM error).
	"""
	if virtualBuffer.passThrough or not virtualBuffer.isReady or not getattr(virtualBuffer, "isAlive", True):
		raise _Unavailable
	try:
		caret = virtualBuffer.selection
		info = caret.copy()
		if info.isCollapsed:
			info.expand(textInfos.UNIT_CHARACTER)
		fields = info.getTextWithFields()
	except LookupError:
		return None
	except _TRANSIENT_ERRORS as e:
		raise _Unavailable from e
	state = _tableStateFromFields(fields)
	if state is None:
		return None
	return _CaretTable(state[0], state[1], caret)


def _caretInTableRow(virtualBuffer) -> bool:
	try:
		return _readCaretTable(virtualBuffer) is not None
	except _Unavailable:
		return False


def usesTableRowBrailleRegions(virtualBuffer) -> bool:
	return is_table_row_braille_enabled() and _caretInTableRow(virtualBuffer)


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
	__slots__ = ("brlexTypeformItems", "endsWithField", "rawTextTypeforms", "rawToContentPos", "text")

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


class _RowCell:
	"""One cell of the cached current row; ``snapshot`` is the caret-less braille text."""

	__slots__ = ("col", "colSpan", "info", "row", "rowSpan", "snapshot")

	def __init__(self, info: textInfos.TextInfo, coords: _TableCell) -> None:
		self.info = info
		self.col = coords.col
		self.row = coords.row
		self.rowSpan = max(1, coords.rowSpan or 1)
		self.colSpan = max(1, coords.colSpan or 1)
		self.snapshot: _CellBrailleSnapshot | None = None


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


def _caretInsideCell(cellField: textInfos.TextInfo, caret: textInfos.TextInfo) -> bool:
	try:
		return (
			cellField.compareEndPoints(caret, "startToStart") <= 0
			and cellField.compareEndPoints(caret, "endToEnd") >= 0
		)
	except (RuntimeError, NotImplementedError, TypeError, ValueError):
		return True


def _populateCellBrailleBuilder(
	builder: _CellBrailleTextBuilder,
	cellInfo: textInfos.TextInfo,
	caret: textInfos.TextInfo | None,
	formatConfig: dict[str, Any],
) -> int | None:
	"""Fill builder with cell braille; return raw ``cursorPos`` (NVDA three-chunk algorithm)."""
	cellField = _tableCellTextInfo(cellInfo)
	if caret is None or not _caretInsideCell(cellField, caret):
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


def _buildCellBraille(
	cellInfo: textInfos.TextInfo,
	formatConfig: dict[str, Any],
	caret: textInfos.TextInfo | None = None,
) -> tuple[_CellBrailleSnapshot, int | None]:
	"""Build cell braille (and map ``caret`` into it) in one ``TextInfoRegion`` pass."""
	builder = _CellBrailleTextBuilder(cellInfo.obj)
	builderCursorPos = _populateCellBrailleBuilder(builder, cellInfo, caret, formatConfig)
	snapshot = _snapshotFromCellBuilder(builder)
	if builderCursorPos is None:
		return snapshot, None
	return snapshot, _builderCursorToContentDisplayIndex(
		builder,
		builderCursorPos,
		snapshot.text,
		snapshot.rawToContentPos,
	)


# Row collection and navigation


def _rowCellRecord(info: textInfos.TextInfo, tableID, row: int) -> _RowCell | None:
	"""Coordinates of ``info`` (a cell of ``tableID``/``row``), or ``None`` if it does not match."""
	probe = info.copy()
	if probe.isCollapsed:
		probe.expand(textInfos.UNIT_CHARACTER)
	try:
		state = _tableStateFromFields(probe.getTextWithFields(), tableID=tableID)
	except (LookupError, NotImplementedError):
		return None
	if state is None or state[0].row != row:
		return None
	return _RowCell(info, state[0])


def _collectRowCells(virtualBuffer, tableID, row: int) -> list[_RowCell]:
	cells: list[_RowCell] = []
	for info in virtualBuffer._iterTableCells(tableID, row=row):
		record = _rowCellRecord(info, tableID, row)
		if record is not None:
			cells.append(record)
	cells.sort(key=lambda item: item.col)
	return cells


def _rowEdgeCellInfo(virtualBuffer, tableID, row: int, *, first: bool) -> textInfos.TextInfo | None:
	"""First or last cell of a row in document order (cells of a row are laid out in column order)."""
	edge = None
	for info in virtualBuffer._iterTableCells(tableID, row=row):
		if first:
			return info
		edge = info
	return edge


def _textInfoAfterTable(
	virtualBuffer,
	tableID,
	anchorInfo: textInfos.TextInfo,
) -> textInfos.TextInfo | None:
	"""Collapsed TextInfo at the first position after the given table.

	``anchorInfo`` is a cell of the table's last row, so the search starts right after it and
	normally ends within a couple of steps.
	"""
	dest = anchorInfo.copy()
	dest.collapse(True)
	for _i in range(5000):
		try:
			state = _readTableStateAt(dest)
		except (RuntimeError, NotImplementedError):
			return None
		if state is None or state[0].tableID != tableID:
			dest.collapse()
			return dest
		if not dest.move(textInfos.UNIT_CHARACTER, 1):
			dest.collapse()
			return dest
	return None


def _readTableStateAt(info: textInfos.TextInfo):
	probe = info.copy()
	if probe.isCollapsed:
		probe.expand(textInfos.UNIT_CHARACTER)
	try:
		fields = probe.getTextWithFields()
	except LookupError:
		return None
	return _tableStateFromFields(fields)


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


def _setBrowseCaret(virtualBuffer, info: textInfos.TextInfo) -> bool:
	try:
		virtualBuffer.selection = info
	except (AttributeError, NotImplementedError, RuntimeError):
		try:
			info.updateCaret()
		except (NotImplementedError, RuntimeError):
			log.debugWarning("virtual buffer table braille: could not move the caret", exc_info=True)
			return False
	_notifyBrailleCaretMoved(virtualBuffer)
	return True


def _moveToAdjacentTableRow(virtualBuffer, *, forward: bool) -> bool:
	"""Move the caret to the first/last cell of the adjacent table row (single caret write).

	Forward navigation lands on the first cell (so reading flows into the new row from its
	start); backward navigation lands on the last cell (so scrolling back reads toward the
	start of the previous row). Browse-mode selection assignment is expensive, so the caret
	is written only once.
	"""
	try:
		state = _readCaretTable(virtualBuffer)
	except _Unavailable:
		return False
	if state is None:
		return False
	movement = "next" if forward else "previous"
	try:
		dest = virtualBuffer._getNearestTableCell(state.caret, state.cell, movement, "row")
		destState = _readTableStateAt(dest)
		if destState is not None:
			edge = _rowEdgeCellInfo(
				virtualBuffer,
				destState[0].tableID,
				destState[0].row,
				first=forward,
			)
			if edge is not None:
				dest = edge
	except (LookupError, *_TRANSIENT_ERRORS):
		return False
	target = dest.copy()
	target.collapse()
	if not _setBrowseCaret(virtualBuffer, target):
		return False
	_speakOnNavigate(virtualBuffer)
	return True


def _leaveVirtualBufferTableForward(virtualBuffer, *, tableID, tableRow: int) -> bool:
	"""Move the browse-mode caret past the table; NVDA then restores normal document braille."""
	try:
		anchor = _rowEdgeCellInfo(virtualBuffer, tableID, tableRow, first=False) or virtualBuffer.selection
		dest = _textInfoAfterTable(virtualBuffer, tableID, anchor)
	except (LookupError, *_TRANSIENT_ERRORS):
		return False
	if dest is None or not _setBrowseCaret(virtualBuffer, dest):
		return False
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
		"colSpan",
		"column",
		"contentEnd",
		"contentStart",
		"hasTableEnd",
		"lineEndEnd",
		"rawToContentPos",
		"row",
		"rowSpan",
		"segEnd",
		"segStart",
	)

	def __init__(self, **kwargs: Any) -> None:
		for key in self.__slots__:
			setattr(self, key, kwargs.get(key))


class _RowLayout:
	"""Immutable result of laying out a row; committed to the region only when complete."""

	__slots__ = (
		"brlexTypeforms",
		"cursorPos",
		"dims",
		"rawText",
		"rawToContent",
		"row",
		"segments",
		"tableID",
		"typeforms",
	)


class TableRowBrailleRegion(braille.CursorManagerRegion):
	"""One braille region for the whole current table row (one cell per segment)."""

	allowPageTurns = True

	def __init__(self, virtualBuffer) -> None:
		super().__init__(virtualBuffer)
		self._virtualBuffer = virtualBuffer
		self.formatField = textInfos.FormatField()
		self._cellNvdaObject = None
		self._segments: list[_CellSegment] = []
		self._tableID = None
		self._row: int = 0
		self._dims: tuple[int, int] | None = None
		self._rowKey: tuple | None = None
		self._rowCells: list[_RowCell] = []
		self.isBuilt = False
		self.focusToHardLeft = True
		# The row uses the whole display: no ancestor/context regions next to it.
		self.hidePreviousRegions = True
		# Valid (empty) translation state, so the region is safe to render before its first update.
		self.rawText = braille.TEXT_SEPARATOR
		self.rawTextTypeforms = [louis.plain_text]
		self._rawToContentPos = [0]
		self.brlex_typeforms = {}
		self._len_brlex_typeforms = 0
		braille.Region.update(self)

	def _isMultiline(self) -> bool:
		return True

	# building

	def _currentRowCells(self, state: _CaretTable, formatConfig: dict[str, Any]) -> list[_RowCell]:
		"""Cells of the caret's row, cached until the row, the buffer content or the format changes."""
		cell = state.cell
		key = (
			_contentGeneration(self._virtualBuffer),
			cell.tableID,
			cell.row,
			_formatSignature(formatConfig),
		)
		if key != self._rowKey:
			cells = _collectRowCells(self._virtualBuffer, cell.tableID, cell.row)
			self._rowCells = cells
			self._rowKey = key
		return self._rowCells

	def _layoutRow(self, state: _CaretTable, formatConfig: dict[str, Any]) -> _RowLayout | None:
		rowCells = self._currentRowCells(state, formatConfig)
		if not rowCells:
			return None
		current = state.cell
		cellSeparator, lineStart, lineEnd = _tableRowBrailleMarkers()
		dims = (
			state.dims
			if state.dims is not None
			else (self._dims if self._tableID == current.tableID else None)
		)
		isFirstRow = current.row == 1
		isLastRow = dims is not None and current.row == dims[0]
		lastIndex = len(rowCells) - 1

		parts: list[str] = []
		typeforms: list[int] = []
		rawToContent: list[int] = []
		brlex: dict[int, int] = {}
		segments: list[_CellSegment] = []
		cursorPos: int | None = None
		pos = 0

		def _emit(text: str) -> None:
			nonlocal pos
			if not text:
				return
			base = rawToContent[-1] if rawToContent else 0
			parts.append(text)
			typeforms.extend([louis.plain_text] * len(text))
			rawToContent.extend([base] * len(text))
			pos += len(text)

		for index, rowCell in enumerate(rowCells):
			isCurrent = rowCell.col == current.col
			if isCurrent:
				snapshot, contentCursor = _buildCellBraille(rowCell.info, formatConfig, state.caret)
			else:
				snapshot = rowCell.snapshot
				if snapshot is None:
					snapshot, _ = _buildCellBraille(rowCell.info, formatConfig)
					rowCell.snapshot = snapshot
				contentCursor = None

			if index == 0:
				prefix = ""
				if isFirstRow:
					label = _tableRoleBrailleLabel()
					prefix = f"{label}({dims[0]},{dims[1]})" if dims is not None else label
				prefix += lineStart or ""
			else:
				prefix = cellSeparator or ""
			lineEndPart = tableEndPart = ""
			if index == lastIndex:
				lineEndPart = lineEnd or ""
				tableEndPart = _tableBoundarySuffix() if isLastRow else ""

			segStart = pos
			_emit(prefix)
			contentStart = pos

			cellText = snapshot.text
			cellTypeforms = list(snapshot.rawTextTypeforms)
			if len(cellTypeforms) < len(cellText):
				cellTypeforms += [louis.plain_text] * (len(cellText) - len(cellTypeforms))
			elif len(cellTypeforms) > len(cellText):
				cellTypeforms = cellTypeforms[: len(cellText)]
			if cellText:
				parts.append(cellText)
				typeforms.extend(cellTypeforms)
				# Map content raw positions to a per-cell content offset space.
				rawToContent.extend(range(len(cellText)))
				pos += len(cellText)
			for rawPos, mask in snapshot.brlexTypeformItems:
				brlex[contentStart + rawPos] = mask
			contentEnd = pos

			_emit(lineEndPart + tableEndPart)
			if isCurrent:
				inCell = contentCursor if contentCursor is not None else 0
				cursorPos = contentStart + (min(inCell, len(cellText) - 1) if cellText else 0)

			segments.append(
				_CellSegment(
					cellInfo=rowCell.info,
					rawToContentPos=snapshot.rawToContentPos,
					column=rowCell.col,
					row=rowCell.row,
					rowSpan=rowCell.rowSpan,
					colSpan=rowCell.colSpan,
					segStart=segStart,
					contentStart=contentStart,
					contentEnd=contentEnd,
					segEnd=pos,
					lineEndEnd=contentEnd + len(lineEndPart),
					hasTableEnd=bool(tableEndPart),
				)
			)

		rawText = "".join(parts)
		if not rawText:
			rawText = braille.TEXT_SEPARATOR
			typeforms = [louis.plain_text]
			rawToContent = [0]
		layout = _RowLayout()
		layout.rawText = rawText
		layout.typeforms = typeforms
		layout.rawToContent = rawToContent
		layout.brlexTypeforms = brlex
		layout.cursorPos = min(cursorPos, len(rawText) - 1) if cursorPos is not None else None
		layout.segments = segments
		layout.tableID = current.tableID
		layout.row = current.row
		layout.dims = dims
		return layout

	def _commit(self, layout: _RowLayout) -> None:
		self.rawText = layout.rawText
		self.rawTextTypeforms = layout.typeforms
		self._rawToContentPos = layout.rawToContent
		self.brlex_typeforms = layout.brlexTypeforms
		self._len_brlex_typeforms = len(layout.brlexTypeforms)
		self.cursorPos = layout.cursorPos
		self.selectionStart = self.selectionEnd = None
		self._segments = layout.segments
		self._tableID = layout.tableID
		self._row = layout.row
		self._dims = layout.dims
		self.formatField = textInfos.FormatField()
		oldLength = len(self.brailleCells)
		braille.Region.update(self)
		self._applyTypeformMasks()
		if self.isBuilt and len(self.brailleCells) != oldLength:
			# NVDA restores the previous display window after a content-driven update and only
			# re-scrolls to the cursor on caret moves. If the row got shorter the restored window
			# can lie past its end and the display looks empty, so ask for a scroll to the cursor.
			self.pendingCaretUpdate = True
		self.isBuilt = True

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

	def update(self) -> None:
		"""Rebuild from the current caret row.

		Never blanks the display: if the buffer is unavailable, the caret is outside a table
		(the caret-move hook swaps the region out) or building fails, the previous content stays.
		"""
		virtualBuffer = self._virtualBuffer
		try:
			state = _readCaretTable(virtualBuffer)
		except _Unavailable:
			log.debug("virtual buffer table braille: update skipped, buffer unavailable")
			return
		if state is None:
			log.debug("virtual buffer table braille: update found the caret outside a table")
			if self.isBuilt:
				_scheduleLeaveRowMode(virtualBuffer, self)
			return
		try:
			layout = self._layoutRow(state, _cellBrailleFormatConfig())
		except Exception:  # noqa: BLE001
			# Drop the cache: it may hold cells of a buffer that changed under us.
			self._rowKey = None
			log.debugWarning("virtual buffer table braille: row update failed", exc_info=True)
			return
		if layout is None:
			log.debug("virtual buffer table braille: update found no cell in the row")
			self._rowKey = None
			return
		self._commit(layout)

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
		if not self._setSelection(dest):
			return
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

	def _setSelection(self, info: textInfos.TextInfo) -> bool:
		return _setBrowseCaret(self._virtualBuffer, info)

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
		try:
			message = _tableRowRoutingCoordFlash(
				zone,
				seg.cellInfo,
				seg.row,
				seg.column,
				rowSpan=seg.rowSpan,
				colSpan=seg.colSpan,
			)
		except _TRANSIENT_ERRORS:
			log.debugWarning("virtual buffer table braille: coordinate flash failed", exc_info=True)
			message = None
		if zone == "tableEnd" and _leaveVirtualBufferTableForward(
			self._virtualBuffer,
			tableID=self._tableID,
			tableRow=seg.row,
		):
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
		return self._dims is not None and self._row == self._dims[0]

	def nextLine(self) -> None:
		if self._isLastRow() and _leaveVirtualBufferTableForward(
			self._virtualBuffer,
			tableID=self._tableID,
			tableRow=self._row,
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


def _shouldUseTableRowBrailleRegions(obj, review: bool = False) -> bool:
	return not review and is_table_row_braille_enabled() and _caretInTableRow(obj)


def virtualBuffer_getBrailleRegions(obj, review: bool = False) -> Iterable[braille.Region]:
	"""Return the table-row region, or raise NotImplementedError for NVDA fallback.

	Must not be a generator: NVDA only catches NotImplementedError from the initial call.
	"""
	if not _shouldUseTableRowBrailleRegions(obj, review):
		raise NotImplementedError
	return [TableRowBrailleRegion(obj)]


def _tableRowRegion(handler: braille.BrailleHandler, virtualBuffer) -> TableRowBrailleRegion | None:
	"""The row region currently shown for ``virtualBuffer`` (always the last main-buffer region)."""
	regions = handler.mainBuffer.regions
	if not regions:
		return None
	last = regions[-1]
	if isinstance(last, TableRowBrailleRegion) and last._virtualBuffer is virtualBuffer:
		return last
	return None


def _discardPendingUpdate(handler: braille.BrailleHandler, region) -> None:
	pending = getattr(handler, "_regionsPendingUpdate", None)
	if pending is not None and region is not None:
		pending.discard(region)


def _enterRowMode(handler: braille.BrailleHandler, virtualBuffer) -> bool:
	"""Show a freshly built row region for ``virtualBuffer`` (synchronously, single build)."""
	region = TableRowBrailleRegion(virtualBuffer)
	region.update()
	if not region.isBuilt:
		log.debug("virtual buffer table braille: row region could not be built")
		return False
	log.debug("virtual buffer table braille: entering row mode")
	regions = handler.mainBuffer.regions
	if regions:
		# The region being replaced would otherwise be rebuilt by the pending update for nothing.
		_discardPendingUpdate(handler, regions[-1])
	handler._doNewObject([region])
	return True


def _leaveRowMode(handler: braille.BrailleHandler, virtualBuffer, region=None) -> None:
	"""Replace the row region with the regular document braille, synchronously."""
	log.debug("virtual buffer table braille: leaving row mode")
	_discardPendingUpdate(handler, region)
	oldRegions = list(handler.mainBuffer.regions)
	handler._doNewObject(
		itertools.chain(
			braille.getFocusContextRegions(virtualBuffer, oldFocusRegions=oldRegions),
			braille.getFocusRegions(virtualBuffer),
		)
	)


_leaveScheduled = False


def _scheduleLeaveRowMode(virtualBuffer, region) -> None:
	"""Fallback used when a region notices, mid-update, that the caret left the table.

	Normally ``_syncRowMode`` has already swapped regions in the caret-move hook; this covers
	other update triggers. Runs once, after re-validating that the swap is still needed.
	"""
	global _leaveScheduled
	if _leaveScheduled:
		return
	_leaveScheduled = True

	def _run() -> None:
		global _leaveScheduled
		_leaveScheduled = False
		try:
			handler = braille.handler
			if handler is None or not handler.enabled:
				return
			if _tableRowRegion(handler, virtualBuffer) is not region:
				return
			if not _isForegroundVirtualBuffer(virtualBuffer):
				return
			try:
				state = _readCaretTable(virtualBuffer)
			except _Unavailable:
				return
			if state is None:
				_leaveRowMode(handler, virtualBuffer, region)
		except Exception:  # noqa: BLE001
			log.debugWarning("virtual buffer table braille: leaving row mode failed", exc_info=True)

	core.callLater(0, _run)


def _syncRowMode(handler: braille.BrailleHandler, virtualBuffer) -> None:
	"""Make the main buffer match the caret: row region inside a table, regular braille outside."""
	if not (isinstance(virtualBuffer, VirtualBuffer) and handler.enabled):
		return
	if handler._tether != TetherTo.FOCUS.value or not _isForegroundVirtualBuffer(virtualBuffer):
		return
	region = _tableRowRegion(handler, virtualBuffer)
	if not is_table_row_braille_enabled():
		if region is not None:
			_leaveRowMode(handler, virtualBuffer, region)
		return
	try:
		state = _readCaretTable(virtualBuffer)
	except _Unavailable:
		return
	if state is None:
		if region is not None:
			_leaveRowMode(handler, virtualBuffer, region)
	elif region is None:
		_enterRowMode(handler, virtualBuffer)
	# else: already in row mode; NVDA's pending update (queued by the original handleCaretMove)
	# rebuilds the region.


def _virtualBufferTableBraille_handleCaretMove(self, obj, shouldAutoTether: bool = True) -> None:
	_originalHandleCaretMove(self, obj, shouldAutoTether=shouldAutoTether)
	try:
		_syncRowMode(self, obj)
	except Exception:  # noqa: BLE001
		log.debugWarning("virtual buffer table braille: caret-move sync failed", exc_info=True)


# Settings / document-formatting refreshes


def _rebuildForSettings() -> None:
	"""Re-render the focused document after a setting changed (new region = fresh caches)."""
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	virtualBuffer = _virtualBufferFromFocusTree()
	if virtualBuffer is None:
		return
	region = _tableRowRegion(handler, virtualBuffer)
	try:
		wantRow = is_table_row_braille_enabled() and _caretInTableRow(virtualBuffer)
	except _Unavailable:
		return
	if wantRow:
		if _enterRowMode(handler, virtualBuffer):
			return
	elif region is not None:
		_leaveRowMode(handler, virtualBuffer, region)
		return
	handler.handleUpdate(virtualBuffer)
	handler._handlePendingUpdate()


def _runSafely(fn) -> None:
	try:
		fn()
	except Exception:  # noqa: BLE001
		log.debugWarning("virtual buffer table braille: refresh failed", exc_info=True)


def refresh_document_formatting_braille_display() -> None:
	"""Refresh braille after document formatting settings change."""
	_runSafely(_rebuildForSettings)


def schedule_document_formatting_braille_refresh() -> None:
	core.callLater(0, refresh_document_formatting_braille_display)


def schedule_virtual_document_braille_refresh() -> None:
	core.callLater(0, refresh_document_formatting_braille_display)


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


# Content-change counters: any buffer update or (re)load invalidates cached row cells


# Content-driven refreshes of the row are coalesced: a table whose cells change many times per
# second must not rebuild the row and redraw the display on every notification.
CONTENT_REFRESH_DELAY_MS = 150


def _deliverContentUpdate(virtualBuffer) -> None:
	virtualBuffer._beUpdatePending = False
	if _originalHandleUpdate is None or not getattr(virtualBuffer, "isAlive", True):
		return
	try:
		_originalHandleUpdate(virtualBuffer)
	except Exception:  # noqa: BLE001
		log.debugWarning("virtual buffer table braille: deferred update failed", exc_info=True)


def _virtualBuffer_handleUpdate_counted(self):
	# The generation is bumped at once so that any update running before the deferred one
	# (e.g. caused by a caret move) already sees fresh content.
	_bumpContentGeneration(self)
	handler = braille.handler
	rowModeActive = handler is not None and handler.enabled and _tableRowRegion(handler, self) is not None
	if not rowModeActive:
		return _originalHandleUpdate(self)
	if getattr(self, "_beUpdatePending", False):
		return None
	self._beUpdatePending = True
	core.callLater(CONTENT_REFRESH_DELAY_MS, _deliverContentUpdate, self)
	return None


def _virtualBuffer_loadBufferDone_counted(self, *args, **kwargs):
	_bumpContentGeneration(self)
	return _originalLoadBufferDone(self, *args, **kwargs)


# install / uninstall

_installed = False
_originalGetBrailleRegions: Any = None
_originalHandleCaretMove: Any = None
_originalHandleUpdate: Any = None
_originalLoadBufferDone: Any = None
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
	global _installed, _originalGetBrailleRegions, _originalHandleCaretMove
	global _originalHandleUpdate, _originalLoadBufferDone
	if _installed:
		return
	_originalGetBrailleRegions = getattr(VirtualBuffer, "getBrailleRegions", None)
	VirtualBuffer.getBrailleRegions = virtualBuffer_getBrailleRegions
	_originalHandleCaretMove = braille.BrailleHandler.handleCaretMove
	braille.BrailleHandler.handleCaretMove = _virtualBufferTableBraille_handleCaretMove
	_originalHandleUpdate = getattr(VirtualBuffer, "_handleUpdate", None)
	if _originalHandleUpdate is not None:
		VirtualBuffer._handleUpdate = _virtualBuffer_handleUpdate_counted
	_originalLoadBufferDone = getattr(VirtualBuffer, "_loadBufferDone", None)
	if _originalLoadBufferDone is not None:
		VirtualBuffer._loadBufferDone = _virtualBuffer_loadBufferDone_counted
	_install_navigation_patches()
	_installed = True
	log.debug("Virtual buffer table row braille (single-region) installed")


def uninstall_virtual_buffer_table_braille() -> None:
	global _installed, _originalGetBrailleRegions, _originalHandleCaretMove
	global _originalHandleUpdate, _originalLoadBufferDone
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
	if _originalHandleCaretMove is not None:
		braille.BrailleHandler.handleCaretMove = _originalHandleCaretMove
	if _originalHandleUpdate is not None:
		VirtualBuffer._handleUpdate = _originalHandleUpdate
	if _originalLoadBufferDone is not None:
		VirtualBuffer._loadBufferDone = _originalLoadBufferDone
	_originalGetBrailleRegions = None
	_originalHandleCaretMove = None
	_originalHandleUpdate = None
	_originalLoadBufferDone = None
	_installed = False
