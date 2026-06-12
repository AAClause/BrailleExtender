# coding: utf-8
# brailleExtenderExcel.py
# Part of Braille Extender addon for NVDA
# Copyright 2026 André-Abush Clause, released under GPL.

from __future__ import annotations

import ctypes
import itertools
import re
from collections.abc import Generator, Iterable
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, NamedTuple

import addonHandler
import api
import braille
import config
import core
import eventHandler
import keyboardHandler
from comtypes import COMError
from comtypes.automation import BSTR
from logHandler import log
from scriptHandler import script
from speech import speakMessage
import NVDAHelper
from NVDAObjects.window.excel import convertAddressToLocal

from appModules.excel import AppModule as _NVDAExcelAppModule

from globalPlugins.brailleExtender.common import addonName

if TYPE_CHECKING:
	from NVDAObjects import NVDAObject
	from NVDAObjects.window.excel import ExcelCell

addonHandler.initTranslation()

try:
	from NVDAHelper.localLib import EXCEL_CELLINFO
except (ImportError, ModuleNotFoundError):
	from NVDAObjects.window.excel import ExcelCellInfo as EXCEL_CELLINFO

_nvdaHelperLocalLib = NVDAHelper.localLib

_CELL_INFO_FLAGS = 0x1 | 0x2 | 0x10 | 0x80
_XL_A1 = 1
_ADDRESS_SPLIT_RE = re.compile(r"^([A-Za-z]+)(\d+)")


class FormulaScope(StrEnum):
	CELL = auto()
	ROW = auto()
	COLUMN = auto()

	@property
	def label(self) -> str:
		return SCOPE_LABELS[self]

	@property
	def isRowOrColumn(self) -> bool:
		return self in (FormulaScope.ROW, FormulaScope.COLUMN)


SCOPE_LABELS: dict[FormulaScope, str] = {
	FormulaScope.CELL: _("Focused cell only"),
	FormulaScope.ROW: _("Row range on one line"),
	FormulaScope.COLUMN: _("Column range on one line"),
}

# Translators: Default short label at the start of an Excel row-range braille line, before the cell address.
# English example on the display: "row A2: sale |  | 99". Keep brief. Do not add spaces at the end.
_AXIS_PREFIX_ROW_DEFAULT = pgettext("excelBrailleAxis", "row")
# Translators: Default short label at the start of an Excel column-range braille line, before the cell address.
# English example on the display: "col A2: sale |  | 99". Keep brief. Do not add spaces at the end.
_AXIS_PREFIX_COLUMN_DEFAULT = pgettext("excelBrailleAxis", "col")


class ScopeFormulaDisplay(StrEnum):
	ACTIVE_CELL = auto()
	ALL = auto()
	NONE = auto()


class ExcelBrailleResult(NamedTuple):
	description: str | None
	suppress_name: bool
	suppress_coords: bool

	@staticmethod
	def empty() -> ExcelBrailleResult:
		return ExcelBrailleResult(None, False, False)


class ScopedBrailleSegment(NamedTuple):
	text: str
	row: int
	column: int
	isCurrent: bool


def _conf() -> Any:
	return config.conf["brailleExtender"]["excel"]


def _scope() -> FormulaScope:
	try:
		return FormulaScope(_conf()["cellFormulaScope"])
	except ValueError:
		return FormulaScope.CELL


def cycle_formula_scope() -> FormulaScope:
	scopes = list(FormulaScope)
	current = _scope()
	new_scope = scopes[(scopes.index(current) + 1) % len(scopes)]
	_conf()["cellFormulaScope"] = new_scope.value
	return new_scope


_scopedWindowCache: dict[
	tuple[int, tuple[int, int] | None],
	tuple[tuple[Any, ...], list[EXCEL_CELLINFO] | None],
] = {}


def _configuredAxisPrefix(configKey: str, default: str) -> str:
	custom = str(_conf()[configKey] or "").strip()
	return custom if custom else default


def _scopedLinePrefix(scope: FormulaScope | None = None) -> str:
	scope = scope or _scope()
	if scope == FormulaScope.ROW:
		text = _configuredAxisPrefix("rowAxisPrefix", _AXIS_PREFIX_ROW_DEFAULT)
	elif scope == FormulaScope.COLUMN:
		text = _configuredAxisPrefix("columnAxisPrefix", _AXIS_PREFIX_COLUMN_DEFAULT)
	else:
		return ""
	return f"{text} "


def _scopedSettingsKey() -> tuple[Any, ...]:
	return (
		_scope(),
		int(_conf()["cellFormulaNeighbors"]),
		_scopeFormulaDisplay(),
		str(_conf()["cellFormulaSeparator"] or " | "),
		_configuredAxisPrefix("rowAxisPrefix", _AXIS_PREFIX_ROW_DEFAULT),
		_configuredAxisPrefix("columnAxisPrefix", _AXIS_PREFIX_COLUMN_DEFAULT),
	)


def clear_scoped_braille_cache(obj: NVDAObject | None = None) -> None:
	global _scopedWindowCache
	if obj is None:
		_scopedWindowCache.clear()
		return
	obj_id = id(obj)
	for key in list(_scopedWindowCache):
		if isinstance(key, tuple) and key and key[0] == obj_id:
			del _scopedWindowCache[key]


def _coordsToRowColumn(coords: str) -> tuple[int, int] | None:
	local = coords.split(" through ")[0].strip().replace("$", "")
	match = _ADDRESS_SPLIT_RE.match(local)
	if not match:
		return None
	row = int(match.group(2))
	column = _columnNumberFromLabel(match.group(1))
	if row < 1 or column < 1:
		return None
	return row, column


def _getScopedRangeWindow(
	obj: NVDAObject,
	cellInfo: EXCEL_CELLINFO | None = None,
	*,
	scope: FormulaScope | None = None,
) -> list[EXCEL_CELLINFO] | None:
	scope = scope or _scope()
	if not scope.isRowOrColumn:
		return None
	settings_key = _scopedSettingsKey()
	position = _focusRowColumn(obj, cellInfo)
	position_key = position[:2] if position else None
	cache_key = (id(obj), position_key)
	cached = _scopedWindowCache.get(cache_key)
	if cached is not None and cached[0] == settings_key:
		return cached[1]
	window = _fetchScopedRangeCellInfos(obj, cellInfo, scope)
	_scopedWindowCache[cache_key] = (settings_key, window)
	return window


def _scopeFormulaDisplay() -> ScopeFormulaDisplay:
	try:
		return ScopeFormulaDisplay(_conf()["scopeFormulaDisplay"])
	except ValueError:
		return ScopeFormulaDisplay.ACTIVE_CELL


def isExcelWorksheetCell(obj: NVDAObject | None) -> bool:
	if obj is None:
		return False
	if not hasattr(obj, "excelCellObject"):
		return False
	return bool(getattr(obj.appModule, "helperLocalBindingHandle", None))


def _includeFormulaForCell(isCurrent: bool) -> bool:
	display = _scopeFormulaDisplay()
	if display == ScopeFormulaDisplay.ALL:
		return True
	if display == ScopeFormulaDisplay.NONE:
		return False
	return isCurrent


def _isExcelFormula(formula: str | None) -> bool:
	return (formula or "").strip().startswith("=")


def _localAddress(cellInfo: EXCEL_CELLINFO) -> str | None:
	if not cellInfo.address:
		return None
	return cellInfo.address.split("!")[-1].split(":")[0]


def _columnLabel(columnNumber: int) -> str:
	label = ""
	column = columnNumber
	while column > 0:
		column, remainder = divmod(column - 1, 26)
		label = chr(65 + remainder) + label
	return label


def _columnNumberFromLabel(label: str) -> int:
	number = 0
	for character in label.upper():
		number = number * 26 + (ord(character) - 64)
	return number


def _mergeAnchor(address: str | None) -> tuple[int, int] | None:
	if not address:
		return None
	local = address.split("!")[-1]
	if ":" not in local:
		return None
	start = local.split(":", 1)[0].strip("$")
	match = _ADDRESS_SPLIT_RE.match(start)
	if not match:
		return None
	return int(match.group(2)), _columnNumberFromLabel(match.group(1))


def _isPrimaryMergeCell(cellInfo: EXCEL_CELLINFO) -> bool:
	anchor = _mergeAnchor(cellInfo.address)
	if anchor is None:
		return True
	return (cellInfo.rowNumber, cellInfo.columnNumber) == anchor


def _cellInfoRichness(cellInfo: EXCEL_CELLINFO) -> int:
	return int(_isExcelFormula(cellInfo.formula)) + int(bool((cellInfo.text or "").strip()))


def _indexCellInfosByPosition(cellInfos: Iterable[EXCEL_CELLINFO]) -> dict[tuple[int, int], EXCEL_CELLINFO]:
	byPosition: dict[tuple[int, int], EXCEL_CELLINFO] = {}
	for cellInfo in cellInfos:
		row, column = cellInfo.rowNumber, cellInfo.columnNumber
		if row < 1 or column < 1:
			continue
		key = (row, column)
		existing = byPosition.get(key)
		if existing is None or _cellInfoRichness(cellInfo) > _cellInfoRichness(existing):
			byPosition[key] = cellInfo
	return byPosition


def _fetchCellInfos(obj: NVDAObject, rangeAddress: str, cellCount: int) -> list[EXCEL_CELLINFO]:
	handle = getattr(obj.appModule, "helperLocalBindingHandle", None)
	if not handle or cellCount <= 0:
		return []
	cellInfos = (EXCEL_CELLINFO * cellCount)()
	numFetched = ctypes.c_long()
	try:
		localAddress = convertAddressToLocal(obj.excelCellObject.Application, rangeAddress)
	except (AttributeError, COMError):
		return []
	if (
		_nvdaHelperLocalLib.nvdaInProcUtils_excel_getCellInfos(
			handle,
			obj.windowHandle,
			BSTR(localAddress),
			_CELL_INFO_FLAGS,
			cellCount,
			cellInfos,
			ctypes.byref(numFetched),
		)
		!= 0
		or numFetched.value <= 0
	):
		return []
	return [
		cellInfos[i]
		for i in range(numFetched.value)
		if cellInfos[i].address or (cellInfos[i].rowNumber and cellInfos[i].columnNumber)
	]


def _emptyCellInfo(rowNumber: int, columnNumber: int) -> EXCEL_CELLINFO:
	cellInfo = EXCEL_CELLINFO()
	cellInfo.rowNumber = rowNumber
	cellInfo.columnNumber = columnNumber
	return cellInfo


def _currentCoords(obj: NVDAObject, cellInfo: EXCEL_CELLINFO | None) -> str | None:
	try:
		if obj.cellCoordsText:
			return obj.cellCoordsText
	except (AttributeError, NotImplementedError):
		pass
	if cellInfo:
		local = _localAddress(cellInfo)
		if local:
			return local
		row = cellInfo.rowNumber
		column = cellInfo.columnNumber
		if row and column:
			return f"{_columnLabel(column)}{row}"
	try:
		row = obj.rowNumber
		column = obj.columnNumber
		if row and column:
			return f"{_columnLabel(column)}{row}"
	except (AttributeError, NotImplementedError, TypeError):
		pass
	context = _getExcelCellContext(obj)
	if context is not None:
		_, row, column, _, _ = context
		return f"{_columnLabel(column)}{row}"
	return None


def _focusRowColumn(
	obj: NVDAObject,
	cellInfo: EXCEL_CELLINFO | None,
) -> tuple[int, int, str] | None:
	"""Row, column, and A1-style label for the focused cell in scoped braille."""
	row: int | None = None
	column: int | None = None
	context = _getExcelCellContext(obj)
	if context is not None:
		row, column = int(context[1]), int(context[2])
	if (row is None or column is None or row < 1 or column < 1) and cellInfo:
		if cellInfo.rowNumber >= 1 and cellInfo.columnNumber >= 1:
			row, column = cellInfo.rowNumber, cellInfo.columnNumber
	if row is None or column is None or row < 1 or column < 1:
		try:
			obj_row = obj.rowNumber
			obj_column = obj.columnNumber
		except (AttributeError, NotImplementedError, TypeError):
			obj_row = obj_column = None
		if obj_row and obj_column:
			row, column = int(obj_row), int(obj_column)
	if row is None or column is None or row < 1 or column < 1:
		coords = _currentCoords(obj, cellInfo)
		if coords:
			parsed = _coordsToRowColumn(coords)
			if parsed:
				row, column = parsed
	if row is None or column is None or row < 1 or column < 1:
		return None
	coordsLabel = f"{_columnLabel(column)}{row}"
	labeled = _currentCoords(obj, cellInfo)
	if labeled:
		local = labeled.split(" through ")[0].strip().replace("$", "")
		parsed = _coordsToRowColumn(local)
		if parsed == (row, column):
			coordsLabel = local
	return row, column, coordsLabel


def _cellInfoIsCurrentFocus(
	cellInfo: EXCEL_CELLINFO,
	currentRow: int,
	currentColumn: int,
) -> bool:
	if cellInfo.rowNumber == currentRow and cellInfo.columnNumber == currentColumn:
		return True
	if cellInfo.rowNumber < 1 or cellInfo.columnNumber < 1:
		local = _localAddress(cellInfo)
		if local:
			parsed = _coordsToRowColumn(local)
			return parsed == (currentRow, currentColumn)
	return False


def _cellContent(cellInfo: EXCEL_CELLINFO, *, isCurrent: bool) -> str:
	if not isCurrent and not _isPrimaryMergeCell(cellInfo):
		return ""
	formula = (cellInfo.formula or "").strip()
	text = (cellInfo.text or "").strip()
	if _isExcelFormula(formula) and _conf()["cellFormula"] and _includeFormulaForCell(isCurrent):
		return f"{text} {formula}" if text else formula
	return text


def _hasDisplayContent(cellInfo: EXCEL_CELLINFO, *, isCurrent: bool) -> bool:
	if isCurrent:
		return True
	if not _isPrimaryMergeCell(cellInfo):
		return False
	if (cellInfo.text or "").strip():
		return True
	return _conf()["cellFormula"] and _isExcelFormula(cellInfo.formula) and _includeFormulaForCell(isCurrent)


def _buildScopedWindow(
	byPosition: dict[tuple[int, int], EXCEL_CELLINFO],
	scope: FormulaScope,
	currentRow: int,
	currentColumn: int,
	neighbors: int,
) -> list[EXCEL_CELLINFO]:
	if scope == FormulaScope.ROW:
		start = max(1, currentColumn - neighbors)
		end = currentColumn + neighbors
		window = [
			byPosition.get((currentRow, column)) or _emptyCellInfo(currentRow, column)
			for column in range(start, end + 1)
		]
	else:
		start = max(1, currentRow - neighbors)
		end = currentRow + neighbors
		window = [
			byPosition.get((row, currentColumn)) or _emptyCellInfo(row, currentColumn)
			for row in range(start, end + 1)
		]

	currentIndex = next(
		(
			i
			for i, cellInfo in enumerate(window)
			if _cellInfoIsCurrentFocus(cellInfo, currentRow, currentColumn)
		),
		None,
	)
	if currentIndex is None:
		return window

	contentIndices = [
		i for i, cellInfo in enumerate(window) if _hasDisplayContent(cellInfo, isCurrent=(i == currentIndex))
	]
	if currentIndex not in contentIndices:
		contentIndices.append(currentIndex)
	return window[min(contentIndices) : max(contentIndices) + 1]


def _getExcelCellContext(obj: NVDAObject) -> tuple[Any, int, int, Any, int] | None:
	if not isExcelWorksheetCell(obj):
		return None
	try:
		excelCell = obj.excelCellObject
		row = int(excelCell.row)
		column = int(excelCell.column)
		if row < 1 or column < 1:
			return None
		return (
			excelCell,
			row,
			column,
			excelCell.Worksheet,
			int(_conf()["cellFormulaNeighbors"]),
		)
	except (AttributeError, COMError, TypeError, ValueError):
		return None


def _fetchScopedRangeCellInfos(
	obj: NVDAObject,
	cellInfo: EXCEL_CELLINFO | None,
	scope: FormulaScope,
) -> list[EXCEL_CELLINFO] | None:
	context = _getExcelCellContext(obj)
	if context is None:
		return None
	excelCell, row, column, worksheet, neighbors = context
	try:
		if scope == FormulaScope.ROW:
			cellRange = worksheet.Range(
				worksheet.Cells(row, max(1, column - neighbors)),
				worksheet.Cells(row, column + neighbors),
			)
		else:
			cellRange = worksheet.Range(
				worksheet.Cells(max(1, row - neighbors), column),
				worksheet.Cells(row + neighbors, column),
			)
		rangeAddress = cellRange.address(True, True, _XL_A1, True)
		cellCount = cellRange.Count
	except (AttributeError, COMError):
		return None

	fetched = _fetchCellInfos(obj, rangeAddress, cellCount)
	if (
		cellInfo
		and cellInfo.rowNumber == row
		and cellInfo.columnNumber == column
		and not any(ci.rowNumber == row and ci.columnNumber == column for ci in fetched)
	):
		fetched.append(cellInfo)
	byPosition = _indexCellInfosByPosition(fetched)
	window = _buildScopedWindow(byPosition, scope, row, column, neighbors)
	return window if window else None


def _currentCellScopeDisplay(cellInfo: EXCEL_CELLINFO, obj: NVDAObject | None) -> str:
	display = _cellContent(cellInfo, isCurrent=True)
	if display:
		return display
	try:
		if obj is not None and obj.name:
			return obj.name.strip()
	except AttributeError:
		pass
	return (cellInfo.text or "").strip()


def _segmentEntry(
	cellInfo: EXCEL_CELLINFO,
	*,
	isCurrent: bool,
	currentCoords: str,
	obj: NVDAObject,
) -> str:
	if isCurrent:
		display = _currentCellScopeDisplay(cellInfo, obj)
		return f"{currentCoords}: {display}" if display else f"{currentCoords}:"
	content = _cellContent(cellInfo, isCurrent=False)
	return content if content else ""


def _minimalScopedSegment(
	obj: NVDAObject,
	window: list[EXCEL_CELLINFO],
	currentRow: int,
	currentColumn: int,
	currentCoords: str,
) -> ScopedBrailleSegment:
	linePrefix = _scopedLinePrefix()
	cellInfo = next(
		(info for info in window if _cellInfoIsCurrentFocus(info, currentRow, currentColumn)),
		None,
	)
	if cellInfo is None:
		cellInfo = _emptyCellInfo(currentRow, currentColumn)
	entry = _segmentEntry(
		cellInfo,
		isCurrent=True,
		currentCoords=currentCoords,
		obj=obj,
	)
	return ScopedBrailleSegment(linePrefix + entry, currentRow, currentColumn, True)


def _ensureCurrentSegmentInList(
	obj: NVDAObject,
	segments: list[ScopedBrailleSegment],
	window: list[EXCEL_CELLINFO],
) -> list[ScopedBrailleSegment]:
	if any(segment.isCurrent for segment in segments):
		return segments
	position = _focusRowColumn(obj, getattr(obj, "excelCellInfo", None))
	if position is None:
		return segments
	currentRow, currentColumn, currentCoords = position
	for index, segment in enumerate(segments):
		if segment.row == currentRow and segment.column == currentColumn:
			fixed = _minimalScopedSegment(obj, window, currentRow, currentColumn, currentCoords)
			updated = list(segments)
			if index == 0:
				updated[0] = fixed
			else:
				separator = str(_conf()["cellFormulaSeparator"] or " | ")
				entry = _segmentEntry(
					next(
						(info for info in window if _cellInfoIsCurrentFocus(info, currentRow, currentColumn)),
						_emptyCellInfo(currentRow, currentColumn),
					),
					isCurrent=True,
					currentCoords=currentCoords,
					obj=obj,
				)
				updated[index] = ScopedBrailleSegment(
					separator + entry,
					currentRow,
					currentColumn,
					True,
				)
			return updated
	return [_minimalScopedSegment(obj, window, currentRow, currentColumn, currentCoords), *segments]


def iterScopedBrailleSegments(
	obj: NVDAObject,
	window: list[EXCEL_CELLINFO] | None = None,
) -> Generator[ScopedBrailleSegment, None, None]:
	if not _scope().isRowOrColumn:
		return
	cellInfo: EXCEL_CELLINFO | None = getattr(obj, "excelCellInfo", None)
	if window is None:
		window = _getScopedRangeWindow(obj, cellInfo)
	if not window:
		return
	position = _focusRowColumn(obj, cellInfo)
	if position is None:
		return
	currentRow, currentColumn, currentCoords = position

	separator = str(_conf()["cellFormulaSeparator"] or " | ")
	linePrefix = _scopedLinePrefix()

	for index, info in enumerate(window):
		isCurrent = _cellInfoIsCurrentFocus(info, currentRow, currentColumn)
		entry = _segmentEntry(
			info,
			isCurrent=isCurrent,
			currentCoords=currentCoords,
			obj=obj,
		)
		text = linePrefix + entry if index == 0 else separator + entry
		yield ScopedBrailleSegment(text, info.rowNumber, info.columnNumber, isCurrent)


def usesScopedBrailleRegions(
	obj: NVDAObject | None,
	window: list[EXCEL_CELLINFO] | None = None,
) -> bool:
	if obj is None or not _scope().isRowOrColumn:
		return False
	if window is not None:
		return bool(window)
	return _getScopedRangeWindow(obj, getattr(obj, "excelCellInfo", None)) is not None


def _excelHeaderSuffix(obj: NVDAObject) -> str:
	suffix = ""
	try:
		columnHeader = getattr(obj, "columnHeaderText", None)
		if columnHeader:
			suffix += "⣀" + columnHeader
	except (NotImplementedError, TypeError):
		pass
	try:
		rowHeader = getattr(obj, "rowHeaderText", None)
		if rowHeader:
			suffix += "⡀" + rowHeader
	except (NotImplementedError, TypeError):
		pass
	return suffix


def excelCellAt(focusCell: ExcelCell, row: int, column: int) -> ExcelCell | None:
	from NVDAObjects.window.excel import ExcelCell, ExcelMergedCell

	context = _getExcelCellContext(focusCell)
	if context is None:
		return None
	_, _, _, worksheet, _ = context
	try:
		cellPosition = worksheet.Cells(row, column)
		try:
			isMerged = cellPosition.mergeCells
		except (COMError, AttributeError):
			isMerged = False
		if isMerged:
			cellPosition = cellPosition.MergeArea(1)
			cellClass = ExcelMergedCell
		else:
			cellClass = ExcelCell
		cellObj = cellClass(
			windowHandle=focusCell.windowHandle,
			excelWindowObject=focusCell.excelWindowObject,
			excelCellObject=cellPosition,
		)
		cellObj.excelCellInfo
		return cellObj
	except (AttributeError, COMError):
		return None


def navigateToExcelCell(focusCell: ExcelCell, row: int, column: int) -> ExcelCell | None:
	cellObj = excelCellAt(focusCell, row, column)
	if cellObj is None:
		return None
	try:
		cellObj.excelCellObject.Select()
		cellObj.excelCellObject.Activate()
		eventHandler.executeEvent("gainFocus", cellObj)
		return cellObj
	except (AttributeError, COMError):
		return None


def _cellScopeFormulaText(cellInfo: EXCEL_CELLINFO) -> str | None:
	if (
		not _conf()["cellFormula"]
		or not _isExcelFormula(cellInfo.formula)
		or not _includeFormulaForCell(isCurrent=True)
	):
		return None
	formula = (cellInfo.formula or "").strip()
	return formula or None


def getExcelFormulaDescription(
	obj: NVDAObject | None,
	cellInfo: EXCEL_CELLINFO | None,
	states: set[int] | None,
	hasFormulaState: int,
) -> ExcelBrailleResult:
	if not _conf()["cellFormula"] or obj is None:
		return ExcelBrailleResult.empty()
	scope = _scope()
	if scope.isRowOrColumn:
		return ExcelBrailleResult.empty()
	if not cellInfo:
		return ExcelBrailleResult.empty()
	if not (states and hasFormulaState in states):
		return ExcelBrailleResult.empty()
	formulaText = _cellScopeFormulaText(cellInfo)
	if not formulaText:
		return ExcelBrailleResult.empty()
	return ExcelBrailleResult(formulaText, False, False)


_excelCellGetBrailleRegionsInstalled = False
_originalExcelCellGetBrailleRegions: Any = None


class ExcelCellBrailleRegion(braille.NVDAObjectRegion):
	def __init__(
		self,
		obj: NVDAObject,
		segmentText: str,
		appendText: str = "",
		*,
		isCurrentSegment: bool = False,
		focusCell: ExcelCell | None = None,
		row: int = 0,
		column: int = 0,
		currentCoords: str | None = None,
	) -> None:
		super().__init__(obj, appendText=appendText)
		self.segmentText = segmentText
		self.isCurrentSegment = isCurrentSegment
		self._focusCell = focusCell
		self._row = row
		self._column = column
		if isCurrentSegment and currentCoords:
			self._contentStart = len(f"{currentCoords}: ")
		else:
			self._contentStart = 0

	def update(self) -> None:
		text = self.segmentText + self.appendText
		if self.isCurrentSegment:
			text += _excelHeaderSuffix(self.obj)
		self.rawText = text
		self.focusToHardLeft = self.isCurrentSegment
		braille.Region.update(self)

	def routeTo(self, braillePos: int) -> None:
		if self.isCurrentSegment:
			self._routeToCurrentCell(braillePos)
			return
		self._routeToNeighborCell()

	def _routeToCurrentCell(self, braillePos: int) -> None:
		if braille.NVDAObjectHasUsefulText(self.obj):
			try:
				textRegion = braille.TextInfoRegion(self.obj)
				textRegion.update()
				rawPos = self.brailleToRawPos[braillePos]
				textOffset = self._rawPosToCellTextOffset(rawPos)
				if textRegion.rawText:
					textOffset = min(textOffset, len(textRegion.rawText) - 1)
				textRegion.routeTo(textRegion.rawToBraillePos[textOffset])
			except (AttributeError, IndexError, NotImplementedError):
				log.debugWarning(
					"Excel TextInfoRegion routing failed",
					exc_info=True,
				)
				self._startInCellEdit()
			return
		try:
			super().routeTo(braillePos)
		except NotImplementedError:
			pass
		self._startInCellEdit()

	def _rawPosToCellTextOffset(self, rawPos: int) -> int:
		if not self._contentStart:
			return rawPos
		return 0 if rawPos < self._contentStart else rawPos - self._contentStart

	@staticmethod
	def _startInCellEdit() -> None:
		keyboardHandler.KeyboardInputGesture.fromName("f2").send()

	def _routeToNeighborCell(self) -> None:
		if self._focusCell is None:
			return
		if navigateToExcelCell(self._focusCell, self._row, self._column) is None:
			log.debugWarning("Excel neighbor routing failed", exc_info=True)


def _excelCellBrailleRegionsFromWindow(
	focusCell: ExcelCell,
	window: list[EXCEL_CELLINFO],
) -> list[ExcelCellBrailleRegion]:
	cellInfo: EXCEL_CELLINFO | None = getattr(focusCell, "excelCellInfo", None)
	currentCoords = _currentCoords(focusCell, cellInfo)
	segments = list(iterScopedBrailleSegments(focusCell, window))
	if not segments:
		position = _focusRowColumn(focusCell, cellInfo)
		if position is not None:
			currentRow, currentColumn, coords = position
			if not currentCoords:
				currentCoords = coords
			segments = [_minimalScopedSegment(focusCell, window, currentRow, currentColumn, coords)]
	else:
		segments = _ensureCurrentSegmentInList(focusCell, segments, window)
	regions: list[ExcelCellBrailleRegion] = []
	for segment in segments:
		regions.append(
			ExcelCellBrailleRegion(
				focusCell,
				segment.text,
				isCurrentSegment=segment.isCurrent,
				focusCell=focusCell,
				row=segment.row,
				column=segment.column,
				currentCoords=currentCoords if segment.isCurrent else None,
			)
		)
	return regions


def excelCell_getBrailleRegions(
	obj: ExcelCell,
	review: bool = False,
) -> Generator[ExcelCellBrailleRegion, None, None]:
	window = _getScopedRangeWindow(obj, getattr(obj, "excelCellInfo", None))
	if review or not isExcelWorksheetCell(obj) or not window:
		if _originalExcelCellGetBrailleRegions is not None:
			return _originalExcelCellGetBrailleRegions(obj, review=review)
		raise NotImplementedError
	regions = _excelCellBrailleRegionsFromWindow(obj, window)
	if not regions:
		# NVDA treats an empty custom generator as success; fall back to default regions.
		if _originalExcelCellGetBrailleRegions is not None:
			return _originalExcelCellGetBrailleRegions(obj, review=review)
		raise NotImplementedError
	for region in regions:
		yield region


def install_excel_braille_regions() -> None:
	global _excelCellGetBrailleRegionsInstalled, _originalExcelCellGetBrailleRegions
	if _excelCellGetBrailleRegionsInstalled:
		return
	from NVDAObjects.window.excel import ExcelCell, ExcelMergedCell

	_originalExcelCellGetBrailleRegions = getattr(ExcelCell, "getBrailleRegions", None)
	ExcelCell.getBrailleRegions = excelCell_getBrailleRegions
	ExcelMergedCell.getBrailleRegions = excelCell_getBrailleRegions
	_excelCellGetBrailleRegionsInstalled = True
	log.debug("Excel row/column braille regions installed")


def uninstall_excel_braille_regions() -> None:
	global _excelCellGetBrailleRegionsInstalled, _originalExcelCellGetBrailleRegions
	if not _excelCellGetBrailleRegionsInstalled:
		return
	from NVDAObjects.window.excel import ExcelCell, ExcelMergedCell

	for cls in (ExcelCell, ExcelMergedCell):
		if _originalExcelCellGetBrailleRegions is not None:
			cls.getBrailleRegions = _originalExcelCellGetBrailleRegions
		else:
			try:
				del cls.getBrailleRegions
			except AttributeError:
				pass
	_originalExcelCellGetBrailleRegions = None
	_excelCellGetBrailleRegionsInstalled = False


def sync_excel_braille_regions_patch() -> None:
	if _scope().isRowOrColumn:
		install_excel_braille_regions()
	else:
		uninstall_excel_braille_regions()


def _excel_focus_object_for_braille() -> NVDAObject | None:
	obj = api.getFocusObject()
	if hasattr(obj, "excelCellInfo") or hasattr(obj, "excelCellObject"):
		return obj
	for ancestor in api.getFocusAncestors():
		if hasattr(ancestor, "excelCellInfo") or hasattr(ancestor, "excelCellObject"):
			return ancestor
	return None


def _excel_cell_from_braille_buffer(handler: braille.BrailleHandler) -> NVDAObject | None:
	for region in reversed(handler.mainBuffer.regions):
		if isinstance(region, ExcelCellBrailleRegion):
			cell = region._focusCell or region.obj
			if cell is not None:
				return cell
		regionObj = getattr(region, "obj", None)
		if regionObj is not None and (
			hasattr(regionObj, "excelCellInfo") or hasattr(regionObj, "excelCellObject")
		):
			return regionObj
	return None


def _resolve_excel_cell_for_braille_refresh() -> NVDAObject | None:
	cell = _excel_focus_object_for_braille()
	if cell is not None:
		return cell
	handler = braille.handler
	if handler is None or not handler.enabled:
		return None
	return _excel_cell_from_braille_buffer(handler)


def schedule_excel_braille_refresh() -> None:
	# Defer until the settings dialog closes; focus is not on a cell during onSave.
	core.callLater(0, refresh_excel_braille_display)


def _partition_braille_buffer_regions(regions: list) -> tuple[list, list]:
	contextRegions: list = []
	focusRegions: list = []
	for region in regions:
		if getattr(region, "_focusAncestorIndex", None) is not None:
			contextRegions.append(region)
		else:
			focusRegions.append(region)
	return contextRegions, focusRegions


def _excel_primary_focus_region(focusRegions: list) -> Any | None:
	for region in focusRegions:
		if getattr(region, "isCurrentSegment", False):
			return region
	return focusRegions[0] if focusRegions else None


def _focus_excel_current_at_display_left(
	handler: braille.BrailleHandler, mainBuffer: braille.BrailleBuffer
) -> bool:
	focusRegion = None
	for region in mainBuffer.regions:
		if getattr(region, "_focusAncestorIndex", None) is not None:
			continue
		if getattr(region, "isCurrentSegment", False):
			focusRegion = region
			break
	if focusRegion is None:
		for region in reversed(mainBuffer.regions):
			if getattr(region, "_focusAncestorIndex", None) is None:
				focusRegion = region
				break
	if focusRegion is None:
		return False
	for region in mainBuffer.regions:
		if getattr(region, "_focusAncestorIndex", None) is not None:
			region.focusToHardLeft = False
	focusRegion.focusToHardLeft = True
	try:
		mainBuffer.focus(focusRegion)
	except LookupError:
		log.debugWarning("Excel braille focus placement failed", exc_info=True)
		return False
	if handler.buffer is mainBuffer:
		handler.update()
	return True


def _apply_braille_buffer_focus_regions(
	handler: braille.BrailleHandler,
	mainBuffer: braille.BrailleBuffer,
	contextRegions: list,
	focusRegions: list,
) -> bool:
	for region in contextRegions:
		region.focusToHardLeft = False
		region.update()
	for region in focusRegions:
		region.update()
	mainBuffer.regions = contextRegions + focusRegions
	mainBuffer.update()
	if not focusRegions:
		if handler.buffer is mainBuffer:
			handler.update()
		return True
	primaryFocus = _excel_primary_focus_region(focusRegions)
	if primaryFocus is None:
		return False
	for region in focusRegions:
		region.focusToHardLeft = region is primaryFocus
	try:
		mainBuffer.focus(primaryFocus)
	except LookupError:
		log.debugWarning("Excel braille focus placement failed", exc_info=True)
		return False
	if handler.buffer is mainBuffer:
		handler.update()
	return True


def _build_excel_focus_regions(focus: NVDAObject) -> list:
	window = _getScopedRangeWindow(focus, getattr(focus, "excelCellInfo", None))
	if _scope().isRowOrColumn and window:
		regions = _excelCellBrailleRegionsFromWindow(focus, window)
		if regions:
			for region in regions:
				region.update()
			return regions
	region = braille.NVDAObjectRegion(focus)
	region.focusToHardLeft = True
	region.update()
	return [region]


def refresh_excel_braille_display() -> None:
	handler = braille.handler
	if handler is None or not handler.enabled:
		return
	sync_excel_braille_regions_patch()
	clear_scoped_braille_cache()
	focus = _resolve_excel_cell_for_braille_refresh()
	if focus is None:
		return
	focus.invalidateCache()
	if handler.buffer is not handler.mainBuffer:
		handler.buffer = handler.mainBuffer
	mainBuffer = handler.mainBuffer
	oldRegions = list(mainBuffer.regions)
	contextRegions, focusRegions = _partition_braille_buffer_regions(oldRegions)
	scopedWindow = (
		_getScopedRangeWindow(focus, getattr(focus, "excelCellInfo", None))
		if _scope().isRowOrColumn
		else None
	)
	wasScopedLine = bool(focusRegions) and isinstance(focusRegions[0], ExcelCellBrailleRegion)
	wantsScopedLine = scopedWindow is not None

	if wantsScopedLine == wasScopedLine:
		if wantsScopedLine:
			newFocusRegions = _build_excel_focus_regions(focus)
			if newFocusRegions and _apply_braille_buffer_focus_regions(
				handler, mainBuffer, contextRegions, newFocusRegions
			):
				return
		elif len(focusRegions) == 1:
			focusRegions[0].focusToHardLeft = True
			focusRegions[0].update()
			if _apply_braille_buffer_focus_regions(handler, mainBuffer, contextRegions, focusRegions):
				return

	if contextRegions:
		newFocusRegions = _build_excel_focus_regions(focus)
		if newFocusRegions and _apply_braille_buffer_focus_regions(
			handler, mainBuffer, contextRegions, newFocusRegions
		):
			return

	regionObj = focus
	treeInterceptor = getattr(focus, "treeInterceptor", None)
	if treeInterceptor is not None and not treeInterceptor.passThrough and treeInterceptor.isReady:
		regionObj = treeInterceptor
	handler._doNewObject(
		itertools.chain(
			braille.getFocusContextRegions(regionObj, oldFocusRegions=oldRegions),
			braille.getFocusRegions(regionObj),
		)
	)
	if wantsScopedLine and not _focus_excel_current_at_display_left(handler, mainBuffer):
		if mainBuffer.regions:
			try:
				mainBuffer.focus(mainBuffer.regions[-1])
				if handler.buffer is mainBuffer:
					handler.update()
			except LookupError:
				log.debugWarning("Excel braille fallback focus failed", exc_info=True)


_headerTextGuardsInstalled = False
_originalGetRowHeaderText: Any = None
_originalGetColumnHeaderText: Any = None
_originalFetchAssociatedHeaderCellText: Any = None


def _excelCellCoordinatesReady(cell: NVDAObject) -> bool:
	try:
		rowNumber = cell.rowNumber
		columnNumber = cell.columnNumber
	except (AttributeError, NotImplementedError, TypeError):
		return False
	return (
		isinstance(rowNumber, int) and isinstance(columnNumber, int) and rowNumber >= 1 and columnNumber >= 1
	)


def _safeFetchAssociatedHeaderCellText(self, cell, columnHeader: bool = False) -> str | None:
	if not _excelCellCoordinatesReady(cell):
		return None
	try:
		return _originalFetchAssociatedHeaderCellText(self, cell, columnHeader=columnHeader)
	except (TypeError, ValueError, COMError, AttributeError, NotImplementedError):
		log.debugWarning("Excel header text lookup failed", exc_info=True)
		return None


def _safeGetRowHeaderText(self: ExcelCell) -> str | None:
	if not _excelCellCoordinatesReady(self):
		return None
	try:
		return _originalGetRowHeaderText(self)
	except (TypeError, ValueError, COMError, AttributeError, NotImplementedError):
		log.debugWarning("Excel row header text lookup failed", exc_info=True)
		return None


def _safeGetColumnHeaderText(self: ExcelCell) -> str | None:
	if not _excelCellCoordinatesReady(self):
		return None
	try:
		return _originalGetColumnHeaderText(self)
	except (TypeError, ValueError, COMError, AttributeError, NotImplementedError):
		log.debugWarning("Excel column header text lookup failed", exc_info=True)
		return None


def install_excel_header_text_guards() -> None:
	global _headerTextGuardsInstalled, _originalGetRowHeaderText, _originalGetColumnHeaderText
	global _originalFetchAssociatedHeaderCellText
	if _headerTextGuardsInstalled:
		return
	from NVDAObjects.window.excel import ExcelCell, ExcelMergedCell, ExcelWorksheet

	_originalFetchAssociatedHeaderCellText = ExcelWorksheet.fetchAssociatedHeaderCellText
	ExcelWorksheet.fetchAssociatedHeaderCellText = _safeFetchAssociatedHeaderCellText
	_originalGetRowHeaderText = ExcelCell._get_rowHeaderText
	_originalGetColumnHeaderText = ExcelCell._get_columnHeaderText
	for cls in (ExcelCell, ExcelMergedCell):
		cls._get_rowHeaderText = _safeGetRowHeaderText
		cls._get_columnHeaderText = _safeGetColumnHeaderText
	_headerTextGuardsInstalled = True


def uninstall_excel_header_text_guards() -> None:
	global _headerTextGuardsInstalled, _originalGetRowHeaderText, _originalGetColumnHeaderText
	global _originalFetchAssociatedHeaderCellText
	if not _headerTextGuardsInstalled:
		return
	from NVDAObjects.window.excel import ExcelCell, ExcelMergedCell, ExcelWorksheet

	if _originalFetchAssociatedHeaderCellText is not None:
		ExcelWorksheet.fetchAssociatedHeaderCellText = _originalFetchAssociatedHeaderCellText
	for cls in (ExcelCell, ExcelMergedCell):
		if _originalGetRowHeaderText is not None:
			cls._get_rowHeaderText = _originalGetRowHeaderText
		if _originalGetColumnHeaderText is not None:
			cls._get_columnHeaderText = _originalGetColumnHeaderText
	_originalFetchAssociatedHeaderCellText = None
	_originalGetRowHeaderText = None
	_originalGetColumnHeaderText = None
	_headerTextGuardsInstalled = False


class AppModule(_NVDAExcelAppModule):
	scriptCategory = addonName

	def event_gainFocus(self, obj, nextHandler):
		nextHandler()
		if isExcelWorksheetCell(obj):
			clear_scoped_braille_cache(obj)
		if not _scope().isRowOrColumn:
			return
		focus = _excel_focus_object_for_braille()
		if focus is None:
			return
		if not usesScopedBrailleRegions(focus):
			return
		handler = braille.handler
		if handler is None or not handler.enabled or handler.buffer is not handler.mainBuffer:
			return
		_focus_excel_current_at_display_left(handler, handler.mainBuffer)

	@script(
		description=_("Cycle Excel braille view (focused cell, row range, or column range on one line)"),
	)
	def script_cycleExcelFormulaScope(self, gesture):
		if not _conf()["cellFormula"]:
			speakMessage(
				_(
					"Report cell formulas in braille is disabled. "
					"Enable it in Braille Extender settings, Excel."
				)
			)
			return
		new_scope = cycle_formula_scope()
		refresh_excel_braille_display()
		speakMessage(new_scope.label)
