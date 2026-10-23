# coding: utf-8
# virtualBufferTableBraille.py - Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush CLAUSE, released under GPL.
"""Show the current virtual-buffer table row on one braille line.

Browse-mode documents get one :class:`VirtualBufferBrailleRegion` (returned by
``VirtualBuffer.getBrailleRegions``, after the usual root-object region, exactly as NVDA's
``getFocusRegions`` does for a cursor manager). When the caret is in a table cell the region shows
the whole row, one segment per cell; elsewhere it is a plain ``CursorManagerRegion`` line.

Design rules (robustness and speed):

* The add-on never replaces braille regions itself. The row/line switch happens inside
  ``update``, so NVDA's own pipeline (focus, caret moves, buffer updates, pending updates, window
  save/restore, messages) handles everything, the same way on NVDA 2024.1 through 2027.x.
* The display is never blanked by the add-on: when the buffer is momentarily unavailable or a row
  cannot be built, the last content stays; a row is committed atomically once fully built.
* Reading the caret position costs one ``getTextWithFields`` call (cell coordinates and table size
  come from the same field list). Cell coordinates and cell braille text are cached per row and
  invalidated whenever the buffer content changes, so moving inside a row only re-renders the cell
  holding the caret. Content-driven row refreshes are coalesced.
* NVDA 2026.3 moved most braille symbols out of the ``braille`` namespace (old accesses log a
  warning with a stack trace); they are resolved once at import from their current location.

Hooks: ``VirtualBuffer.getBrailleRegions``, content-change counters on ``VirtualBuffer`` and Gecko
table-navigation fallbacks. All are undone by :func:`uninstall_virtual_buffer_table_braille`.
"""

from __future__ import annotations

import importlib
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


def _braille_symbol(name: str, *newModules: str, required: bool = True):
	"""Fetch a braille symbol from where NVDA 2026.3+ defines it, else from ``braille``.

	NVDA 2026.3 moved these symbols out of the ``braille`` package namespace; accessing them
	through ``braille`` still works but logs a warning with a stack trace on every access, which
	is far too costly on the per-update code paths of this module. Resolve each once, here.
	"""
	for moduleName in newModules:
		try:
			module = importlib.import_module(moduleName)
		except ImportError:
			continue
		if name in vars(module):
			return vars(module)[name]
	if required:
		return getattr(braille, name)
	return getattr(braille, name, None)


_Region = _braille_symbol("Region", "braille.regions.base")
_TextInfoRegion = _braille_symbol("TextInfoRegion", "braille.regions.textInfo")
_CursorManagerRegion = _braille_symbol("CursorManagerRegion", "braille.regions.textInfo")
_NVDAObjectRegion = _braille_symbol("NVDAObjectRegion", "braille.regions.NVDAObject")
_roleLabels = _braille_symbol("roleLabels", "braille.labels")
TEXT_SEPARATOR = _braille_symbol("TEXT_SEPARATOR", "braille.constants")
# Private helpers, available from NVDA 2025.1 only.
_speakOnRouting = _braille_symbol("_speakOnRouting", "braille.regions.textInfo", required=False)
_speakOnNavigatingByUnit = _braille_symbol(
	"_speakOnNavigatingByUnit", "braille.regions.textInfo", required=False
)

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


# Focused document


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


def _tableRoleBrailleLabelCandidates() -> tuple[str, ...]:
	candidates: list[str] = []
	table_role = get_control_type("ROLE_TABLE")
	try:
		label = _roleLabels[table_role]
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


class _CellBrailleTextBuilder(_TextInfoRegion):
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


def _rawTableID(tableID):
	"""The ``table-id`` value stored in the virtual buffer, for attribute searches.

	Since NVDA 2026.3, ``Gecko_ia2_TextInfo._normalizeControlField`` reports ``table-id`` as
	``(docHandle, id)`` (#17750), while buffer searches (``VirtualBuffer._iterTableCells``,
	which matches ``str(tableID)``) still need the raw ``id``. Other buffers and older NVDA
	versions report the raw value, which is returned unchanged.
	"""
	if isinstance(tableID, tuple) and tableID:
		return tableID[-1]
	return tableID


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
	for info in virtualBuffer._iterTableCells(_rawTableID(tableID), row=row):
		record = _rowCellRecord(info, tableID, row)
		if record is not None:
			cells.append(record)
	cells.sort(key=lambda item: item.col)
	return cells


def _rowEdgeCellInfo(virtualBuffer, tableID, row: int, *, first: bool) -> textInfos.TextInfo | None:
	"""First or last cell of a row in document order (cells of a row are laid out in column order)."""
	edge = None
	for info in virtualBuffer._iterTableCells(_rawTableID(tableID), row=row):
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
	speak = _speakOnNavigatingByUnit
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
	helper = _CursorManagerRegion(virtualBuffer)
	helper._readingInfo = virtualBuffer.selection.copy()
	if helper._readingInfo.isCollapsed:
		helper._readingInfo.expand(helper._getReadingUnit())
	if forward:
		_TextInfoRegion.nextLine(helper)
	else:
		_TextInfoRegion.previousLine(helper, start)
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


class VirtualBufferBrailleRegion(_CursorManagerRegion):
	"""Braille region of a browse-mode document: the whole table row in a table, NVDA's line elsewhere.

	A single region instance serves the document whatever the caret position. Switching between
	row and line presentation happens inside :meth:`update`, so NVDA's own pipeline
	(``handleGainFocus``, ``handleCaretMove``, ``handleUpdate``, pending updates, window save and
	restore) drives everything and the add-on never replaces regions behind NVDA's back. That is
	what keeps the display from going blank: there is no region swap that can race with focus
	events, buffer reloads or messages.

	Outside tables the region behaves exactly like NVDA's ``CursorManagerRegion`` (including
	Braille Extender's patches of ``TextInfoRegion``).
	"""

	def __init__(self, virtualBuffer) -> None:
		super().__init__(virtualBuffer)
		self._virtualBuffer = virtualBuffer
		self.formatField = textInfos.FormatField()
		self._cellNvdaObject = None
		self._brailleInputIndStart = None
		self._segments: list[_CellSegment] = []
		self._tableID = None
		self._row: int = 0
		self._dims: tuple[int, int] | None = None
		self._rowKey: tuple | None = None
		self._rowCells: list[_RowCell] = []
		#: True while the region shows a table row rather than a document line.
		self.rowMode = False

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
			rawText = TEXT_SEPARATOR
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

	def _commitRow(self, layout: _RowLayout) -> None:
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
		self._cellNvdaObject = None
		self._brailleInputIndStart = None
		getDefaultLanguage = getattr(self, "_getDefaultRegionLanguage", None)
		if getDefaultLanguage is not None:
			# NVDA 2026.3+: the per-position languages of the previous line no longer apply.
			self._languageIndexes = {0: getDefaultLanguage()}
		# The row uses the whole display: the document/ancestor regions before it are hidden.
		self.hidePreviousRegions = True
		self.focusToHardLeft = True
		_Region.update(self)
		self._applyTypeformMasks()
		self.rowMode = True

	def _updateLine(self) -> None:
		"""Regular NVDA document line (``TextInfoRegion.update``, with Braille Extender's patches)."""
		self.rowMode = False
		self._segments = []
		self._cellNvdaObject = None
		_CursorManagerRegion.update(self)

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

	def _readRowState(self) -> _CaretTable | None:
		"""Caret table state if the row should be shown; raises ``_Unavailable`` to keep the display."""
		if not is_table_row_braille_enabled():
			return None
		try:
			return _readCaretTable(self._virtualBuffer)
		except _Unavailable:
			if self.brailleCells:
				raise
			# Nothing displayed yet: let the regular line update decide (as NVDA would).
			return None

	def update(self) -> None:
		wasRowMode = self.rowMode
		oldLength = len(self.brailleCells)
		try:
			state = self._readRowState()
		except _Unavailable:
			log.debug("virtual buffer table braille: buffer unavailable, keeping the display")
			return
		layout = None
		if state is not None:
			try:
				layout = self._layoutRow(state, _cellBrailleFormatConfig())
			except Exception:  # noqa: BLE001
				# Drop the cache: it may hold cells of a buffer that changed under us.
				self._rowKey = None
				log.debugWarning("virtual buffer table braille: row update failed", exc_info=True)
				if wasRowMode:
					# Keep the last row rather than flashing the document line.
					return
		if layout is not None:
			self._commitRow(layout)
		else:
			self._updateLine()
		if self.rowMode != wasRowMode or (self.rowMode and len(self.brailleCells) != oldLength):
			# NVDA restores the previous display window after a content-driven update and only
			# scrolls to the cursor after caret moves. When the presentation or the row length
			# changes, the restored window may be meaningless (or past the end: an empty
			# display), so ask NVDA to scroll to the cursor.
			self.pendingCaretUpdate = True

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
		speak = _speakOnRouting
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

	def _routeToRowPos(self, braillePos: int) -> None:
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

	def routeTo(self, braillePos: int) -> None:
		if self.rowMode:
			self._routeToRowPos(braillePos)
		else:
			super().routeTo(braillePos)

	def _rowTextInfoForBraillePos(self, braillePos: int) -> textInfos.TextInfo:
		try:
			rawPos = self.brailleToRawPos[braillePos]
		except IndexError:
			rawPos = max(0, len(self.rawText) - 1)
		seg = self._segmentForRawPos(rawPos)
		if seg is None:
			info = self._virtualBuffer.selection.copy()
			info.collapse()
			return info
		inCell = rawPos - seg.contentStart
		if 0 <= inCell < len(seg.rawToContentPos) and rawPos < seg.contentEnd:
			try:
				dest = _tableCellTextInfo(seg.cellInfo).moveToCodepointOffset(seg.rawToContentPos[inCell])
			except (RuntimeError, NotImplementedError, ValueError):
				dest = seg.cellInfo.copy()
		else:
			dest = seg.cellInfo.copy()
		dest.collapse()
		return dest

	def getTextInfoForBraillePos(self, braillePos: int) -> textInfos.TextInfo:
		if self.rowMode:
			return self._rowTextInfoForBraillePos(braillePos)
		return super().getTextInfoForBraillePos(braillePos)

	# row navigation (called by BrailleBuffer scroll at row edges)

	def _isLastRow(self) -> bool:
		if self._segments and self._segments[-1].hasTableEnd:
			return True
		return self._dims is not None and self._row == self._dims[0]

	def nextLine(self) -> None:
		if not self.rowMode:
			super().nextLine()
			return
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
		if not self.rowMode:
			super().previousLine(start)
			return
		if _moveToAdjacentTableRow(self._virtualBuffer, forward=False):
			return
		# At the first row: leave the table upward using normal document navigation.
		_documentLineNav(self._virtualBuffer, forward=False, start=start)


# Kept for code referring to the previous class name.
TableRowBrailleRegion = VirtualBufferBrailleRegion


# Region installation and NVDA integration


def virtualBuffer_getBrailleRegions(obj, review: bool = False) -> Iterable[_Region]:
	"""Regions of a browse-mode document: the root object region, then the document region.

	Mirrors NVDA's ``getFocusRegions`` for a cursor manager, with the document region replaced by
	:class:`VirtualBufferBrailleRegion`. Must not be a generator: NVDA only catches
	``NotImplementedError`` from the initial call.
	"""
	if review or not is_table_row_braille_enabled():
		raise NotImplementedError
	return [
		_NVDAObjectRegion(obj.rootNVDAObject, appendText=TEXT_SEPARATOR),
		VirtualBufferBrailleRegion(obj),
	]


def _documentRegion(handler, virtualBuffer) -> VirtualBufferBrailleRegion | None:
	"""Our region currently shown for ``virtualBuffer`` (always the last main-buffer region)."""
	if handler is None:
		return None
	regions = handler.mainBuffer.regions
	if not regions:
		return None
	last = regions[-1]
	if isinstance(last, VirtualBufferBrailleRegion) and last._virtualBuffer is virtualBuffer:
		return last
	return None


# Settings / document-formatting refreshes


def _rebuildForSettings() -> None:
	"""Re-render the focused document after a setting changed."""
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	virtualBuffer = _virtualBufferFromFocusTree()
	if virtualBuffer is None:
		return
	region = _documentRegion(handler, virtualBuffer)
	if region is None:
		if is_table_row_braille_enabled() and handler._tether == TetherTo.FOCUS.value:
			# The document is shown with NVDA's own regions: rebuild them so ours are used.
			handler.handleGainFocus(virtualBuffer, shouldAutoTether=False)
			return
	else:
		# Cached cell text depends on the settings; the region falls back to the regular line
		# by itself when row braille has been disabled.
		region._rowKey = None
	handler.handleUpdate(virtualBuffer)
	handler._handlePendingUpdate()


def refresh_document_formatting_braille_display() -> None:
	"""Refresh braille after document formatting settings change."""
	try:
		_rebuildForSettings()
	except Exception:  # noqa: BLE001
		log.debugWarning("virtual buffer table braille: refresh failed", exc_info=True)


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


def _gecko_iterTableCells_rawID(self, tableID, *args, **kwargs):
	"""Search the buffer with the raw ``table-id`` (NVDA 2026.3+ reports ``(docHandle, id)``)."""
	return _originalGeckoIterTableCells(self, _rawTableID(tableID), *args, **kwargs)


def _tableFindNewCell_safe_recovery(self, movement=None, axis=None, selection=None, raiseOnEdge=False):
	try:
		return _originalTableFindNewCell(self, movement, axis, selection, raiseOnEdge)
	except RuntimeError as e:
		if e.args and e.args[0] == "Unable to find current cell.":
			raise LookupError from e
		raise


# Content-change counters: any buffer update or (re)load invalidates cached row cells

# Content-driven refreshes of a displayed row are coalesced: a table whose cells change many
# times per second must not rebuild the row and redraw the display on every notification.
CONTENT_REFRESH_DELAY_MS = 150


def _deliverContentUpdate(virtualBuffer) -> None:
	virtualBuffer._beUpdatePending = False
	if _originalHandleUpdate is None or not getattr(virtualBuffer, "VBufHandle", None):
		return
	try:
		_originalHandleUpdate(virtualBuffer)
	except Exception:  # noqa: BLE001
		log.debugWarning("virtual buffer table braille: deferred update failed", exc_info=True)


def _virtualBuffer_handleUpdate_counted(self):
	# The generation is bumped at once so that any update running before the deferred one
	# (e.g. caused by a caret move) already sees fresh content.
	_bumpContentGeneration(self)
	region = _documentRegion(braille.handler, self)
	if region is None or not region.rowMode:
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

#: (owner, attribute, own value before patching, whether owner defined it itself), in patch order.
_appliedPatches: list[tuple[Any, str, Any, bool]] = []


def _patch(owner, name: str, replacement, *, required: bool = True) -> Any:
	"""Replace ``owner.name`` and record how to undo it; return the previous (inherited) value."""
	ownValues = vars(owner)
	had = name in ownValues
	previous = getattr(owner, name, None)
	if previous is None and required:
		log.debug("virtual buffer table braille: %s.%s missing, not patched", owner.__name__, name)
		return None
	_appliedPatches.append((owner, name, ownValues.get(name), had))
	setattr(owner, name, replacement)
	return previous


_originalHandleUpdate: Any = None
_originalLoadBufferDone: Any = None
_originalGeckoGetTableCellAt: Any = None
_originalGeckoGetNearestTableCell: Any = None
_originalGeckoIterTableCells: Any = None
_originalTableFindNewCell: Any = None


def install_virtual_buffer_table_braille() -> None:
	global _originalHandleUpdate, _originalLoadBufferDone
	global _originalGeckoGetTableCellAt, _originalGeckoGetNearestTableCell, _originalTableFindNewCell
	global _originalGeckoIterTableCells
	if _appliedPatches:
		return
	try:
		_patch(VirtualBuffer, "getBrailleRegions", virtualBuffer_getBrailleRegions, required=False)
		_originalHandleUpdate = _patch(VirtualBuffer, "_handleUpdate", _virtualBuffer_handleUpdate_counted)
		_originalLoadBufferDone = _patch(
			VirtualBuffer,
			"_loadBufferDone",
			_virtualBuffer_loadBufferDone_counted,
		)
		if Gecko_ia2 is not None:
			_originalGeckoGetTableCellAt = _patch(
				Gecko_ia2,
				"_getTableCellAt",
				_gecko_getTableCellAt_vbuf_fallback,
			)
			_originalGeckoGetNearestTableCell = _patch(
				Gecko_ia2,
				"_getNearestTableCell",
				_gecko_getNearestTableCell_vbuf_when_row_braille,
			)
			# Also repairs NVDA's own vbuf table search (used by the fallbacks above) on 2026.3+.
			_originalGeckoIterTableCells = _patch(Gecko_ia2, "_iterTableCells", _gecko_iterTableCells_rawID)
		if DocumentWithTableNavigation is not None:
			_originalTableFindNewCell = _patch(
				DocumentWithTableNavigation,
				"_tableFindNewCell",
				_tableFindNewCell_safe_recovery,
			)
	except Exception:
		uninstall_virtual_buffer_table_braille()
		raise
	log.debug("Virtual buffer table row braille installed")


def uninstall_virtual_buffer_table_braille() -> None:
	global _originalHandleUpdate, _originalLoadBufferDone
	global _originalGeckoGetTableCellAt, _originalGeckoGetNearestTableCell, _originalTableFindNewCell
	global _originalGeckoIterTableCells
	while _appliedPatches:
		owner, name, ownValue, had = _appliedPatches.pop()
		try:
			if had:
				setattr(owner, name, ownValue)
			else:
				delattr(owner, name)
		except AttributeError:
			log.debugWarning("virtual buffer table braille: could not restore %s", name, exc_info=True)
	_originalHandleUpdate = None
	_originalLoadBufferDone = None
	_originalGeckoGetTableCellAt = None
	_originalGeckoGetNearestTableCell = None
	_originalGeckoIterTableCells = None
	_originalTableFindNewCell = None
