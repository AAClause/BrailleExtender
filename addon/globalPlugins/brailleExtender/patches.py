# coding: utf-8
# patches.py - Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush CLAUSE, released under GPL.

from __future__ import annotations

import ctypes
import os
import re
import struct
import sys
import time
from typing import Any, Optional, Sequence

import addonHandler
import api
import braille
import brailleInput
import colors
import config
import controlTypes
import core
import globalCommands
import inputCore
import keyboardHandler
import louis
import louisHelper
import nvwave
import queueHandler
try:
	import sayAllHandler
except ModuleNotFoundError:
	from speech.sayAll import SayAllHandler as sayAllHandler
import scriptHandler
import speech
import textInfos
import tones
import treeInterceptorHandler
import watchdog
import winUser
from logHandler import log

try:
	import winBindings
	_user32 = winBindings.user32
	_useWinBindings = True
except ImportError:
	_user32 = winUser
	_useWinBindings = False

from . import addoncfg
from . import advancedinput
from . import autoscroll
from . import huc
from . import regionhelper
from . import speechhistorymode
from . import undefinedchars
from .common import (
	baseDir,
	BRLEX_CELL_MASK_BY_METHOD,
	CHOICE_tags,
	IS_CURRENT_NO,
	RC_EMULATE_ARROWS_BEEP,
	RC_EMULATE_ARROWS_SILENT,
	NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING,
	NVDA_HAS_SPEAK_ON_ROUTING,
)
from .documentformatting import (
	format_config_font_attributes_report_braille,
	format_config_indicates_spelling_braille,
	get_method,
	get_report,
	get_tags,
	N_,
	normalizeTextAlign,
	normalize_report_key,
	report_row_follows_nvda,
	use_be_format_field_chrome,
	alignment_method_shows_format_tags,
)
from .objectpresentation import getPropertiesBraille, selectedElementEnabled, update_NVDAObjectRegion
from .onehand import process as processOneHandMode
from .utils import (
	getCharFromValue,
	getCurrentBrailleTables,
	getCurrentChar,
	getSpeechSymbols,
	getTether,
	get_control_type,
	get_output_reason,
	is_braille_unicode_normalization_enabled,
)

addonHandler.initTranslation()

instanceGP = None


def _selection_shape_bitmask() -> int:
	return int(braille.SELECTION_SHAPE)


_VARIATION_SELECTOR_SUFFIX_RE = re.compile(r"([^\ufe00-\ufe0f])[\ufe00-\ufe0f]\u20E3?")


def _stop_nvda_core_autoscroll() -> None:
	"""Disable NVDA's built-in braille auto-scroll (CallLater), if available."""
	auto_scroll = getattr(braille.handler, "autoScroll", None)
	if not callable(auto_scroll):
		return
	try:
		auto_scroll(enable=False)
	except Exception:
		log.debugWarning("BrailleExtender: could not disable NVDA core auto scroll", exc_info=True)


def _saveOriginals():
	o = {}
	o["getControlFieldBraille"] = braille.getControlFieldBraille
	o["getFormatFieldBraille"] = braille.getFormatFieldBraille
	o["Region.update"] = braille.Region.update
	o["TextInfoRegion._addTextWithFields"] = braille.TextInfoRegion._addTextWithFields
	o["TextInfoRegion.update"] = braille.TextInfoRegion.update
	o["TextInfoRegion.previousLine"] = braille.TextInfoRegion.previousLine
	o["TextInfoRegion.nextLine"] = braille.TextInfoRegion.nextLine
	o["TextInfoRegion._getTypeformFromFormatField"] = getattr(
		braille.TextInfoRegion, "_getTypeformFromFormatField", None
	)
	o["BrailleInputHandler._translate"] = brailleInput.BrailleInputHandler._translate
	o["BrailleInputHandler.emulateKey"] = brailleInput.BrailleInputHandler.emulateKey
	o["BrailleInputHandler.input"] = brailleInput.BrailleInputHandler.input
	o["BrailleInputHandler.sendChars"] = brailleInput.BrailleInputHandler.sendChars
	o["script_braille_routeTo"] = globalCommands.GlobalCommands.script_braille_routeTo
	o["NVDAObjectRegion.update"] = braille.NVDAObjectRegion.update
	o["getPropertiesBraille"] = braille.getPropertiesBraille
	o["BrailleHandler.getTether"] = braille.BrailleHandler.getTether
	o["BrailleHandler.handleGainFocus"] = braille.BrailleHandler.handleGainFocus
	if hasattr(braille.BrailleHandler, "handleCaretMove"):
		o["BrailleHandler.handleCaretMove"] = braille.BrailleHandler.handleCaretMove
	if hasattr(braille.BrailleHandler, "setTether"):
		o["BrailleHandler.setTether"] = braille.BrailleHandler.setTether
	o["BrailleHandler._displayWithCursor"] = getattr(
		braille.BrailleHandler, "_displayWithCursor", None
	)
	if hasattr(louis, "_createTablesString"):
		o["_createTablesString"] = louis._createTablesString
	return o

_originals = _saveOriginals()

origFunc = {
	"script_braille_routeTo": _originals["script_braille_routeTo"],
	"update": _originals["Region.update"],
	"update_TextInfoRegion": _originals["TextInfoRegion.update"],
}
if "_createTablesString" in _originals:
	origFunc["_createTablesString"] = _originals["_createTablesString"]


def sayCurrentLine():
	global instanceGP
	if not get_auto_scroll():
		if getTether() == braille.handler.TETHER_REVIEW:
			if config.conf["brailleExtender"]["speakScroll"] in [addoncfg.CHOICE_focusAndReview, addoncfg.CHOICE_review]:
				scriptHandler.executeScript(
					globalCommands.commands.script_review_currentLine, None)
			return
		if config.conf["brailleExtender"]["speakScroll"] in [addoncfg.CHOICE_focusAndReview, addoncfg.CHOICE_focus]:
			obj = api.getFocusObject()
			treeInterceptor = obj.treeInterceptor
			if isinstance(treeInterceptor, treeInterceptorHandler.DocumentTreeInterceptor) and not treeInterceptor.passThrough:
				obj = treeInterceptor
			try:
				info = obj.makeTextInfo(textInfos.POSITION_CARET)
			except (NotImplementedError, RuntimeError):
				info = obj.makeTextInfo(textInfos.POSITION_FIRST)
			info.expand(textInfos.UNIT_LINE)
			speech.speakTextInfo(info, unit=textInfos.UNIT_LINE, reason=REASON_CARET)


def _queue_braille_scroll_line_speech() -> None:
	"""Respect BrailleExtender speakScroll (none / focus / review / both) on all NVDA versions."""
	queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
	queueHandler.queueFunction(queueHandler.eventQueue, sayCurrentLine)


def say_character_under_braille_routing_cursor(gesture):
	# Skip when NVDA core provides this (since 2024.4)
	if NVDA_HAS_SPEAK_ON_ROUTING:
		return
	if not get_auto_scroll() and scriptHandler.getLastScriptRepeatCount() == 0 and config.conf["brailleExtender"]["speakRoutingTo"]:
		region = braille.handler.buffer
		if region.cursorPos is None:
			return
		try:
			start = region.brailleToRawPos[braille.handler.buffer.windowStartPos +
										   gesture.routingIndex]
			_, endBraillePos = regionhelper.getBraillePosFromRawPos(
				region, start)
			end = region.brailleToRawPos[endBraillePos+1]
			ch = region.rawText[start:end]
			if ch:
				speech.speakMessage(getSpeechSymbols(ch))
		except IndexError:
			pass


def script_braille_routeTo(self, gesture):
	if braille.handler.buffer == braille.handler.mainBuffer and braille.handler.getTether() == speechhistorymode.TETHER_SPEECH:
		return speechhistorymode.showSpeechFromRoutingIndex(gesture.routingIndex)
	if get_auto_scroll() and braille.handler.buffer is braille.handler.mainBuffer:
		braille.handler.toggle_auto_scroll()
	obj = api.getNavigatorObject()
	if (config.conf["brailleExtender"]["routingCursorsEditFields"] in [RC_EMULATE_ARROWS_BEEP, RC_EMULATE_ARROWS_SILENT] and
		braille.handler.buffer is braille.handler.mainBuffer and
		braille.handler.mainBuffer.cursorPos is not None and
		obj.hasFocus and
		obj.role in [get_control_type("ROLE_TERMINAL"), get_control_type("ROLE_EDITABLETEXT")]
	):
		play_beeps = config.conf["brailleExtender"]["routingCursorsEditFields"] == RC_EMULATE_ARROWS_BEEP
		nb = 0
		key = "rightarrow"
		region = braille.handler.mainBuffer
		cur_pos = region.brailleToRawPos[region.cursorPos]
		size = region.brailleToRawPos[-1]
		try:
			new_pos = region.brailleToRawPos[braille.handler.buffer.windowStartPos + gesture.routingIndex]
		except IndexError:
			new_pos = size
		log.debug(f"Moving from position {cur_pos} to position {new_pos}")
		if play_beeps: tones.beep(100, 100)
		if new_pos == 0:
			keyboardHandler.KeyboardInputGesture.fromName("home").send()
		elif new_pos >= size:
			keyboardHandler.KeyboardInputGesture.fromName("end").send()
		else:
			if cur_pos > new_pos:
				key = "leftarrow"
				nb = cur_pos - new_pos
			else:
				nb = new_pos - cur_pos
			i = 0
			gestureKB = keyboardHandler.KeyboardInputGesture.fromName(key)
			while i < nb:
				gestureKB.send()
				i += 1
		if play_beeps: tones.beep(150, 100)
		say_character_under_braille_routing_cursor(gesture)
		return
	try: braille.handler.routeTo(gesture.routingIndex)
	except LookupError: pass
	say_character_under_braille_routing_cursor(gesture)


def update_region(self) -> None:
	"""Translate L{rawText} to braille cells (mirrors NVDA Region.update, plus add-on hooks).

	Includes Unicode normalization when enabled in NVDA braille settings, so liblouis and
	undefined-character replacement stay aligned with raw text indices.
	"""
	if config.conf["brailleExtender"]["advanced"]["fixCursorPositions"]:
		pattern = _VARIATION_SELECTOR_SUFFIX_RE
		matches = list(pattern.finditer(self.rawText))
		positions_to_remove: list[int] = []
		for match in matches:
			positions_to_remove.extend(range(match.start() + 1, match.end()))
		self.rawText = pattern.sub(r"\1", self.rawText)
		if isinstance(self.cursorPos, int):
			self.cursorPos -= sum(1 for p in positions_to_remove if p <= self.cursorPos)
		if isinstance(self.selectionStart, int):
			self.selectionStart -= sum(1 for p in positions_to_remove if p <= self.selectionStart)
		if isinstance(self.selectionEnd, int):
			self.selectionEnd -= sum(1 for p in positions_to_remove if p <= self.selectionEnd)
	mode = louis.dotsIO
	if config.conf["braille"]["expandAtCursor"] and self.cursorPos is not None:
		mode |= louis.compbrlAtCursor

	converter: Any = None
	text_to_translate = self.rawText
	text_typeforms = self.rawTextTypeforms
	translate_cursor: Optional[int] = self.cursorPos
	if is_braille_unicode_normalization_enabled():
		try:
			from textUtils import UnicodeNormalizationOffsetConverter, isUnicodeNormalized
		except ImportError:
			isUnicodeNormalized = None  # type: ignore[assignment]
		else:
			if isUnicodeNormalized is not None and not isUnicodeNormalized(text_to_translate):
				converter = UnicodeNormalizationOffsetConverter(text_to_translate)
				text_to_translate = converter.encoded
				if text_typeforms is not None:
					text_typeforms = [
						text_typeforms[str_offset]
						for str_offset in converter.computedEncodedToStrOffsets
					]
				if translate_cursor is not None:
					translate_cursor = converter.strToEncodedOffsets(translate_cursor)

	self.brailleCells, braille_to_raw_pos, raw_to_braille_pos, self.brailleCursorPos = louisHelper.translate(
		getCurrentBrailleTables(brf=bool(instanceGP and instanceGP.BRFMode)),
		text_to_translate,
		typeform=text_typeforms,
		mode=mode,
		cursorPos=translate_cursor,
	)
	if converter is not None:
		braille_to_raw_pos = [converter.encodedToStrOffsets(i) for i in braille_to_raw_pos]
		raw_to_braille_pos = [raw_to_braille_pos[i] for i in converter.computedStrToEncodedOffsets]
	self.brailleToRawPos = braille_to_raw_pos
	self.rawToBraillePos = raw_to_braille_pos

	if (
		undefinedchars.should_apply_undefined_char_processing(self)
	):
		undefinedchars.undefinedCharProcess(self)
	if selectedElementEnabled():
		selected_mode = config.conf["brailleExtender"]["objectPresentation"]["selectedElement"]
		add_dots = BRLEX_CELL_MASK_BY_METHOD.get(selected_mode, 0)
		if (
			add_dots
			and hasattr(self, "obj")
			and self.obj
			and getattr(self.obj, "states", None)
			and self.obj.name
			and get_control_type("STATE_SELECTED") in self.obj.states
		):
			name = self.obj.name
			if config.conf["brailleExtender"]["advanced"]["fixCursorPositions"]:
				name = _VARIATION_SELECTOR_SUFFIX_RE.sub(r"\1", name)
			if name in self.rawText:
				start = self.rawText.index(name)
				end = start + len(name) - 1
				start_braille_pos, _ = regionhelper.getBraillePosFromRawPos(self, start)
				_, end_braille_pos = regionhelper.getBraillePosFromRawPos(self, end)
				self.brailleCells = [
					cell | add_dots if start_braille_pos <= pos <= end_braille_pos else cell
					for pos, cell in enumerate(self.brailleCells)
				]
	if (
		self.selectionStart is not None
		and self.selectionEnd is not None
		and config.conf["braille"].get("showSelection", True)
	):
		selection_shape = _selection_shape_bitmask()
		try:
			self.brailleSelectionStart = self.rawToBraillePos[self.selectionStart]
			if self.selectionEnd >= len(self.rawText):
				self.brailleSelectionEnd = len(self.brailleCells)
			else:
				self.brailleSelectionEnd = self.rawToBraillePos[self.selectionEnd]
			for pos in range(self.brailleSelectionStart, self.brailleSelectionEnd):
				self.brailleCells[pos] |= selection_shape
		except IndexError:
			pass
	else:
		if instanceGP and instanceGP.hideDots78:
			self.brailleCells = [(cell & 63) for cell in self.brailleCells]


def update_TextInfoRegion(self):
	formatConfig = config.conf["documentFormatting"]
	unit = self._getReadingUnit()
	self.rawText = ""
	self.rawTextTypeforms = []
	self.brlex_typeforms = {}
	self._len_brlex_typeforms = 0
	self.cursorPos = None
	# The output includes text representing fields which isn't part of the real content in the control.
	# Therefore, maintain a map of positions in the output to positions in the content.
	self._rawToContentPos = []
	self._currentContentPos = 0
	self.selectionStart = self.selectionEnd = None
	self._isFormatFieldAtStart = True
	self._skipFieldsNotAtStartOfNode = False
	self._endsWithField = False

	# Selection has priority over cursor.
	# HACK: Some TextInfos only support UNIT_LINE properly if they are based on POSITION_CARET,
	# and copying the TextInfo breaks this ability.
	# So use the original TextInfo for line and a copy for cursor/selection.
	self._readingInfo = readingInfo = self._getSelection()
	sel = readingInfo.copy()
	if not sel.isCollapsed:
		# There is a selection.
		if self.obj.isTextSelectionAnchoredAtStart:
			# The end of the range is exclusive, so make it inclusive first.
			readingInfo.move(textInfos.UNIT_CHARACTER, -1, "end")
		# Collapse the selection to the unanchored end.
		readingInfo.collapse(end=self.obj.isTextSelectionAnchoredAtStart)
		# Get the reading unit at the selection.
		readingInfo.expand(unit)
		# Restrict the selection to the reading unit.
		if sel.compareEndPoints(readingInfo, "startToStart") < 0:
			sel.setEndPoint(readingInfo, "startToStart")
		if sel.compareEndPoints(readingInfo, "endToEnd") > 0:
			sel.setEndPoint(readingInfo, "endToEnd")
	else:
		# There is a cursor.
		# Get the reading unit at the cursor.
		readingInfo.expand(unit)

	# Not all text APIs support offsets, so we can't always get the offset of the selection relative to the start of the reading unit.
	# Therefore, grab the reading unit in three parts.
	# First, the chunk from the start of the reading unit to the start of the selection.
	chunk = readingInfo.copy()
	chunk.collapse()
	chunk.setEndPoint(sel, "endToStart")
	self._addTextWithFields(chunk, formatConfig)
	# If the user is entering braille, place any untranslated braille before the selection.
	# Import late to avoid circular import.
	import brailleInput
	text = brailleInput.handler.untranslatedBraille
	if text:
		rawInputIndStart = len(self.rawText)
		# _addFieldText adds text to self.rawText and updates other state accordingly.
		self._addFieldText(braille.INPUT_START_IND + text +
						   braille.INPUT_END_IND, None, separate=False)
		rawInputIndEnd = len(self.rawText)
	else:
		rawInputIndStart = None
	# Now, the selection itself.
	self._addTextWithFields(sel, formatConfig, isSelection=True)
	# Finally, get the chunk from the end of the selection to the end of the reading unit.
	chunk.setEndPoint(readingInfo, "endToEnd")
	chunk.setEndPoint(sel, "startToEnd")
	self._addTextWithFields(chunk, formatConfig)

	# Strip line ending characters.
	self.rawText = self.rawText.rstrip("\r\n\0\v\f")
	rawTextLen = len(self.rawText)
	if rawTextLen < len(self._rawToContentPos):
		self._currentContentPos = self._rawToContentPos[rawTextLen]
		del self.rawTextTypeforms[rawTextLen:]
	if rawTextLen == 0 or not self._endsWithField:
		self.rawText += braille.TEXT_SEPARATOR
		rawTextLen += 1
		self.rawTextTypeforms.append(louis.plain_text)
		self._rawToContentPos.append(self._currentContentPos)
	if self.cursorPos is not None and self.cursorPos >= rawTextLen:
		self.cursorPos = rawTextLen - 1
	# If this is not the start of the object, hide all previous regions.
	start = readingInfo.obj.makeTextInfo(textInfos.POSITION_FIRST)
	self.hidePreviousRegions = (
		start.compareEndPoints(readingInfo, "startToStart") < 0)
	if not self.focusToHardLeft:
		self.focusToHardLeft = self._isMultiline()
	super(braille.TextInfoRegion, self).update()

	if rawInputIndStart is not None:
		assert rawInputIndEnd is not None, "rawInputIndStart set but rawInputIndEnd isn't"
		self._brailleInputIndStart = self.rawToBraillePos[rawInputIndStart]
		self._brailleInputIndEnd = self.rawToBraillePos[rawInputIndEnd]
		self._brailleInputStart = self._brailleInputIndStart + \
			len(braille.INPUT_START_IND)
		self._brailleInputEnd = self._brailleInputIndEnd - \
			len(braille.INPUT_END_IND)
		self.brailleCursorPos = self._brailleInputStart + \
			brailleInput.handler.untranslatedCursorPos
	else:
		self._brailleInputIndStart = None

def getControlFieldBraille(info, field, ancestors, reportStart, formatConfig):
	"""Delegate to NVDA core; ``braille.getPropertiesBraille`` is still replaced by the add-on."""
	return _originals["getControlFieldBraille"](info, field, ancestors, reportStart, formatConfig)


def _spelling_errors_show_in_braille(format_config: dict[str, Any]) -> bool:
	return format_config_indicates_spelling_braille(format_config)


_IA2_NORMALIZE_HINT_KEYS: frozenset[str] = frozenset(
	{
		"font-weight",
		"font-style",
		"invalid",
		"text-underline-style",
		"text-underline-type",
		"text-line-through-style",
		"text-line-through-type",
		"text-indent",
		"mark",
	}
)


def _prepare_format_field_for_braille(field: dict[str, Any]) -> None:
	"""Map raw IA2-style keys to NVDA canonical format fields (bold, invalid-spelling, …).

	``normalizeIA2TextFormatField`` is only run when IA2-like keys are present so we do not inject
	default ``text-position`` on unrelated providers.
	"""
	if not isinstance(field, dict) or not field:
		return
	inv = field.get("invalid")
	if isinstance(inv, str):
		for token in re.split(r"[\s,]+", inv.strip().lower()):
			if token == "spelling":
				field["invalid-spelling"] = True
			elif token == "grammar":
				field["invalid-grammar"] = True
	if not any(k in field for k in _IA2_NORMALIZE_HINT_KEYS):
		return
	try:
		from NVDAObjects.IAccessible import normalizeIA2TextFormatField

		normalizeIA2TextFormatField(field)
	except Exception:
		log.debugWarning("BrailleExtender: normalizeIA2TextFormatField failed", exc_info=True)


def _text_position_matches_bucket(raw: Any, want: str) -> bool:
	"""True when ``raw`` represents subscript (want=sub) or superscript (want=super)."""
	if raw is None or raw is False:
		return False
	label = str(getattr(raw, "name", raw)).lower()
	if want == "sub":
		return "sub" in label
	if want == "super":
		return "super" in label
	return want in label


def _try_append_nvda_core_formatting_markers(
	field: dict[str, Any],
	fieldCache: dict[str, Any] | None,
	formatConfig: dict[str, Any],
	textList: list[str],
	*,
	font_attribute_reporting: bool,
) -> bool:
	"""Use NVDA's ``fontAttributeFormattingMarkers`` / ``_appendFormattingMarker`` when available.

	When this returns ``True``, NVDA appended non-empty marker text: BrailleExtender must not add its own
	tag/dots overlays for keys delegated to NVDA (classic font attrs, semantic emphasis/highlight when
	present in NVDA's marker table, and/or spelling).

	When this returns ``False``, NVDA did not emit markers for this chunk: either the API is missing
	(older NVDA), nothing is delegated to NVDA (add-on tags/dots for all attributes), or eligible markers
	produced no output. Callers may then fall back to add-on tags when the report row follows NVDA
	(``CHOICE_likeSpeech`` / "Follow NVDA document formatting" in settings).
	"""
	markers = getattr(braille, "fontAttributeFormattingMarkers", None)
	append_fn = getattr(braille, "_appendFormattingMarker", None)
	if not isinstance(markers, dict) or not callable(append_fn):
		return False
	font_attrs_follow_nvda = (
		report_row_follows_nvda("fontAttributes")
		and font_attribute_reporting
	)
	spelling_follows_nvda = (
		report_row_follows_nvda("spellingErrors")
		and format_config_indicates_spelling_braille(formatConfig)
	)
	emphasis_follows_nvda = (
		report_row_follows_nvda("emphasis")
		and bool(formatConfig.get("reportEmphasis", False))
	)
	highlight_follows_nvda = (
		report_row_follows_nvda("highlight")
		and bool(formatConfig.get("reportHighlight", False))
	)
	eligible: set[str] = set()
	if font_attrs_follow_nvda:
		eligible.update(("bold", "italic", "underline", "strikethrough"))
	if spelling_follows_nvda:
		eligible.update(("invalid-spelling", "invalid-grammar"))
	if emphasis_follows_nvda:
		eligible.update(k for k in ("strong", "emphasised") if k in markers)
	if highlight_follows_nvda and "marked" in markers:
		eligible.add("marked")
	if not eligible:
		return False
	parts: list[str] = []
	for key, marker in markers.items():
		if key not in eligible:
			continue
		try:
			if not marker.shouldBeUsed(key):
				continue
		except Exception:
			log.debugWarning(
				"BrailleExtender: NVDA marker shouldBeUsed failed for %s", key, exc_info=True
			)
			continue
		try:
			append_fn(key, marker, parts, field, fieldCache)
		except Exception:
			log.debugWarning(
				"BrailleExtender: NVDA _appendFormattingMarker failed for %s", key, exc_info=True
			)
	if not parts:
		# NVDA did not emit any markers; allow ``getFormatFieldBraille`` fallbacks (e.g. tags when
		# attributes are delegated to NVDA core but markers are empty).
		return False
	chunk = "".join(parts)
	try:
		ffd = config.conf["braille"]["fontFormattingDisplay"].calculated()
		from config.configFlags import FontFormattingBrailleModeFlag

		if ffd == FontFormattingBrailleModeFlag.TAGS:
			delim = getattr(braille, "FormatTagDelimiter", None)
			if delim is not None:
				chunk = f"{delim.START}{chunk}{delim.END}"
	except Exception:
		pass
	textList.append(chunk)
	return True


def _nvda_paragraph_start_preamble_allowed(formatConfig: dict[str, Any]) -> bool:
	"""True when every enabled is-at-start report row follows NVDA (then prepend NVDA paragraph marker)."""
	pairs = (
		("reportLineNumber", "lineNumber"),
		("reportHeadings", "headings"),
		("reportLinks", "links"),
		("reportComments", "comments"),
	)
	any_enabled = False
	for fc_key, report_id in pairs:
		if not formatConfig.get(fc_key):
			continue
		any_enabled = True
		if not report_row_follows_nvda(report_id):
			return False
	return any_enabled


def getFormatFieldBraille(field, fieldCache, isAtStart, formatConfig):
	"""Generates the braille text for the given format field.
	@param field: The format field to examine.
	@type field: {str : str, ...}
	@param fieldCache: The format field of the previous run; i.e. the cached format field.
	@type fieldCache: {str : str, ...}
	@param isAtStart: True if this format field precedes any text in the line/paragraph.
	This is useful to restrict display of information which should only appear at the start of the line/paragraph;
	e.g. the line number or line prefix (list bullet/number).
	@type isAtStart: bool
	@param formatConfig: The formatting config.
	@type formatConfig: {str : bool, ...}
	"""
	textList = []

	if isAtStart:
		if config.conf["brailleExtender"]["documentFormatting"]["processLinePerLine"]:
			fieldCache.clear()
		if _nvda_paragraph_start_preamble_allowed(formatConfig):
			get_psm = getattr(braille, "getParagraphStartMarker", None)
			if callable(get_psm):
				try:
					marker = get_psm()
					if marker:
						textList.append(marker)
				except Exception:
					log.debugWarning("BrailleExtender: getParagraphStartMarker failed", exc_info=True)
		if formatConfig["reportParagraphIndentation"] and use_be_format_field_chrome("paragraphIndentation"):
			indentLabels = {
				"left-indent": (N_("left indent"), N_("no left indent")),
				"right-indent": (N_("right indent"), N_("no right indent")),
				"hanging-indent": (N_("hanging indent"), N_("no hanging indent")),
				"first-line-indent": (N_("first line indent"), N_("no first line indent")),
			}
			text = []
			for attr,(label, noVal) in indentLabels.items():
				newVal = field.get(attr)
				oldVal = fieldCache.get(attr) if fieldCache else None
				if (newVal or oldVal is not None) and newVal != oldVal:
					if newVal:
						text.append("%s %s" % (label, newVal))
					else:
						text.append(noVal)
			if text:
				textList.append("⣏%s⣹" % ", ".join(text))
		if formatConfig["reportLineNumber"]:
			lineNumber = field.get("line-number")
			if lineNumber:
				textList.append("%s" % lineNumber)
		linePrefix = field.get("line-prefix")
		if linePrefix:
			textList.append(linePrefix)
		if formatConfig["reportHeadings"]:
			headingLevel = field.get('heading-level')
			if headingLevel:
				# Translators: Displayed in braille for a heading with a level.
				# %s is replaced with the level.
				hlabel = N_("h%s") % headingLevel
				if use_be_format_field_chrome("headings"):
					textList.append(hlabel + ' ')
				else:
					textList.append(hlabel)
		collapsed = field.get("collapsed")
		if collapsed:
			try:
				textList.append(braille.positiveStateLabels[controlTypes.State.COLLAPSED])
			except Exception:
				log.debugWarning("BrailleExtender: collapsed state label failed", exc_info=True)

	if formatConfig["reportPage"] and use_be_format_field_chrome("page"):
		pageNumber = field.get("page-number")
		oldPageNumber = fieldCache.get(
			"page-number") if fieldCache is not None else None
		if pageNumber and pageNumber != oldPageNumber:
			# Translators: Indicates the page number in a document.
			# %s will be replaced with the page number.
			text = N_("page %s") % pageNumber
			textList.append("⣏%s⣹" % text)
		sectionNumber = field.get("section-number")
		oldSectionNumber = fieldCache.get(
			"section-number") if fieldCache is not None else None
		if sectionNumber and sectionNumber != oldSectionNumber:
			# Translators: Indicates the section number in a document.
			# %s will be replaced with the section number.
			text = N_("section %s") % sectionNumber
			textList.append("⣏%s⣹" % text)

		textColumnCount = field.get("text-column-count")
		oldTextColumnCount = fieldCache.get(
			"text-column-count") if fieldCache is not None else None
		textColumnNumber = field.get("text-column-number")
		oldTextColumnNumber = fieldCache.get(
			"text-column-number") if fieldCache is not None else None
		if (((textColumnNumber and textColumnNumber != oldTextColumnNumber) or
			 (textColumnCount and textColumnCount != oldTextColumnCount)) and not
				(textColumnCount and int(textColumnCount) <= 1 and oldTextColumnCount is None)):
			if textColumnNumber and textColumnCount:
				# Translators: Indicates the text column number in a document.
				# {0} will be replaced with the text column number.
				# {1} will be replaced with the number of text columns.
				text = N_("column {0} of {1}").format(
					textColumnNumber, textColumnCount)
				textList.append("⣏%s⣹" % text)
			elif textColumnCount:
				# Translators: Indicates the text column number in a document.
				# %s will be replaced with the number of text columns.
				text = N_("%s columns") % (textColumnCount)
				textList.append("⣏%s⣹" % text)

	if formatConfig["reportAlignment"] and use_be_format_field_chrome("alignment"):
		textAlign = normalizeTextAlign(field.get("text-align"))
		old_textAlign = normalizeTextAlign(fieldCache.get("text-align"))
		if (
			textAlign
			and textAlign != old_textAlign
			and alignment_method_shows_format_tags(field.get("text-align"))
		):
			tag = get_tags(f"text-align:{textAlign}")
			if tag:
				textList.append(tag.start)

	if formatConfig["reportLinks"]:
		link = field.get("link")
		oldLink = fieldCache.get("link") if fieldCache else None
		if link and link != oldLink:
			linkCell = braille.roleLabels[get_control_type("ROLE_LINK")]
			if use_be_format_field_chrome("links"):
				textList.append(linkCell + ' ')
			else:
				textList.append(linkCell)

	if formatConfig["reportStyle"] and use_be_format_field_chrome("style"):
		style = field.get("style")
		oldStyle = fieldCache.get("style") if fieldCache is not None else None
		if style != oldStyle:
			if style:
				# Translators: Indicates the style of text.
				# A style is a collection of formatting settings and depends on the application.
				# %s will be replaced with the name of the style.
				text = N_("style %s") % style
			else:
				# Translators: Indicates that text has reverted to the default style.
				# A style is a collection of formatting settings and depends on the application.
				text = N_("default style")
			textList.append("⣏%s⣹" % text)
	if formatConfig["reportFontName"] and use_be_format_field_chrome("fontName"):
		fontFamily = field.get("font-family")
		oldFontFamily = fieldCache.get(
			"font-family") if fieldCache is not None else None
		if fontFamily and fontFamily != oldFontFamily:
			textList.append("⣏%s⣹" % fontFamily)
		fontName = field.get("font-name")
		oldFontName = fieldCache.get(
			"font-name") if fieldCache is not None else None
		if fontName and fontName != oldFontName:
			textList.append("⣏%s⣹" % fontName)
	if formatConfig["reportFontSize"] and use_be_format_field_chrome("fontSize"):
		fontSize = field.get("font-size")
		oldFontSize = fieldCache.get(
			"font-size") if fieldCache is not None else None
		if fontSize and fontSize != oldFontSize:
			textList.append("⣏%s⣹" % fontSize)
	if formatConfig["reportColor"] and use_be_format_field_chrome("color"):
		color = field.get("color")
		oldColor = fieldCache.get("color") if fieldCache is not None else None
		backgroundColor = field.get("background-color")
		oldBackgroundColor = fieldCache.get(
			"background-color") if fieldCache is not None else None
		backgroundColor2 = field.get("background-color2")
		oldBackgroundColor2 = fieldCache.get(
			"background-color2") if fieldCache is not None else None
		bgColorChanged = backgroundColor != oldBackgroundColor or backgroundColor2 != oldBackgroundColor2
		bgColorText = backgroundColor.name if isinstance(
			backgroundColor, colors.RGB) else backgroundColor
		if backgroundColor2:
			bg2Name = backgroundColor2.name if isinstance(
				backgroundColor2, colors.RGB) else backgroundColor2
			# Translators: Reported when there are two background colors.
			# This occurs when, for example, a gradient pattern is applied to a spreadsheet cell.
			# {color1} will be replaced with the first background color.
			# {color2} will be replaced with the second background color.
			bgColorText = N_("{color1} to {color2}").format(
				color1=bgColorText, color2=bg2Name)
		if color and backgroundColor and color != oldColor and bgColorChanged:
			# Translators: Reported when both the text and background colors change.
			# {color} will be replaced with the text color.
			# {backgroundColor} will be replaced with the background color.
			textList.append("⣏%s⣹" % N_("{color} on {backgroundColor}").format(
				color=color.name if isinstance(color, colors.RGB) else color,
				backgroundColor=bgColorText))
		elif color and color != oldColor:
			# Translators: Reported when the text color changes (but not the background color).
			# {color} will be replaced with the text color.
			textList.append("⣏%s⣹" % N_("{color}").format(
				color=color.name if isinstance(color, colors.RGB) else color))
		elif backgroundColor and bgColorChanged:
			# Translators: Reported when the background color changes (but not the text color).
			# {backgroundColor} will be replaced with the background color.
			textList.append("⣏%s⣹" % N_("{backgroundColor} background").format(
				backgroundColor=bgColorText))
		backgroundPattern = field.get("background-pattern")
		oldBackgroundPattern = fieldCache.get(
			"background-pattern") if fieldCache is not None else None
		if backgroundPattern and backgroundPattern != oldBackgroundPattern:
			textList.append("⣏%s⣹" % N_("background pattern {pattern}").format(
				pattern=backgroundPattern))

	if formatConfig["reportRevisions"] and use_be_format_field_chrome("revisions"):
		revision_insertion = field.get("revision-insertion")
		old_revision_insertion = fieldCache.get("revision-insertion")
		tag_revision_deletion = get_tags(f"revision-deletion")
		tag_revision_insertion = get_tags(f"revision-insertion")
		if not old_revision_insertion and revision_insertion:
			textList.append(tag_revision_insertion.start)
		elif old_revision_insertion and not revision_insertion:
			textList.append(tag_revision_insertion.end)

		revision_deletion = field.get("revision-deletion")
		old_revision_deletion = fieldCache.get("revision-deletion")
		if not old_revision_deletion and revision_deletion:
			textList.append(tag_revision_deletion.start)
		elif old_revision_deletion and not revision_deletion:
			textList.append(tag_revision_deletion.end)

	if formatConfig["reportComments"]:
		comment = field.get("comment")
		old_comment = fieldCache.get("comment") if fieldCache is not None else None
		if not use_be_format_field_chrome("comments"):
			if (comment or old_comment is not None) and comment != old_comment:
				if comment:
					if comment is textInfos.CommentType.DRAFT:
						# Translators: Brailled when text contains a draft comment.
						textList.append(_("drft cmnt"))
					elif comment is textInfos.CommentType.RESOLVED:
						# Translators: Brailled when text contains a resolved comment.
						textList.append(_("rslvd cmnt"))
					else:
						# Translators: Brailled when text contains a generic comment.
						textList.append(_("cmnt"))
		else:
			tag = get_tags("comments")
			if tag:
				if not old_comment and comment:
					textList.append(tag.start)
				elif old_comment and not comment:
					textList.append(tag.end)

	start_tag_list = []
	end_tag_list = []

	tags: list[str] = []

	font_attribute_reporting = format_config_font_attributes_report_braille(formatConfig)
	font_attrs_follow_nvda = report_row_follows_nvda("fontAttributes")
	emphasis_follows_nvda = report_row_follows_nvda("emphasis")
	highlight_follows_nvda = report_row_follows_nvda("highlight")
	if font_attribute_reporting and not font_attrs_follow_nvda:
		tags += [tag for tag in [
			"bold",
			"italic",
			"underline",
			"strikethrough"] if get_method(tag) == CHOICE_tags
		]
	if normalize_report_key("superscriptsAndSubscripts") and formatConfig["reportSuperscriptsAndSubscripts"]:
		tags += [tag for tag in [
			"text-position:sub",
			"text-position:super"] if get_method(tag) == CHOICE_tags
		]
	if formatConfig.get("reportEmphasis", False) and not emphasis_follows_nvda:
		tags += [k for k in ("strong", "emphasised") if get_method(k) == CHOICE_tags]
	if formatConfig.get("reportHighlight", False) and not highlight_follows_nvda:
		tags += [k for k in ("marked",) if get_method(k) == CHOICE_tags]
	spell_follows_nvda = report_row_follows_nvda("spellingErrors")
	if _spelling_errors_show_in_braille(formatConfig):
		if not spell_follows_nvda:
			tags += [tag for tag in [
				"invalid-spelling",
				"invalid-grammar"] if get_method(tag) == CHOICE_tags
			]

	def _apply_format_tag_names(name_tags: list[str]) -> None:
		"""Emit start/end tag cells like NVDA ``_appendFormattingMarker`` (truthy on / falsy off)."""
		for name_tag in name_tags:
			if name_tag.startswith("text-position:"):
				want = name_tag.split(":", 1)[1]
				new_val = field.get("text-position")
				old_val = fieldCache.get("text-position") if fieldCache is not None else None
				tag = get_tags(name_tag) or get_tags("text-position")
				if not tag:
					continue
				if _text_position_matches_bucket(new_val, want) and not _text_position_matches_bucket(
					old_val, want
				):
					start_tag_list.append(tag.start)
				elif _text_position_matches_bucket(old_val, want) and not _text_position_matches_bucket(
					new_val, want
				):
					end_tag_list.append(tag.end)
				continue
			name_field = name_tag.split(":", 1)[0]
			new_val = field.get(name_field, False)
			old_val = fieldCache.get(name_field, False) if fieldCache is not None else False
			tag = get_tags(name_field)
			if not tag:
				continue
			if new_val and not old_val:
				start_tag_list.append(tag.start)
			elif old_val and not new_val:
				end_tag_list.append(tag.end)

	_apply_format_tag_names(tags)
	nvda_marker_api_ok = _try_append_nvda_core_formatting_markers(
		field, fieldCache, formatConfig, textList, font_attribute_reporting=font_attribute_reporting
	)
	if not nvda_marker_api_ok:
		if (
			report_row_follows_nvda("spellingErrors")
			and _spelling_errors_show_in_braille(formatConfig)
		):
			_apply_format_tag_names(
				[t for t in ("invalid-spelling", "invalid-grammar") if get_method(t) == CHOICE_tags]
			)
		if font_attrs_follow_nvda and font_attribute_reporting:
			_apply_format_tag_names(
				[
					t
					for t in ("bold", "italic", "underline", "strikethrough")
					if get_method(t) == CHOICE_tags
				]
			)
		if emphasis_follows_nvda and formatConfig.get("reportEmphasis", False):
			_apply_format_tag_names(
				[k for k in ("strong", "emphasised") if get_method(k) == CHOICE_tags]
			)
		if highlight_follows_nvda and formatConfig.get("reportHighlight", False):
			_apply_format_tag_names([k for k in ("marked",) if get_method(k) == CHOICE_tags])
	else:
		markers_dict = getattr(braille, "fontAttributeFormattingMarkers", None) or {}
		if emphasis_follows_nvda and formatConfig.get("reportEmphasis", False):
			missing_emphasis = [
				k
				for k in ("strong", "emphasised")
				if k not in markers_dict and get_method(k) == CHOICE_tags
			]
			if missing_emphasis:
				_apply_format_tag_names(missing_emphasis)
		if (
			highlight_follows_nvda
			and formatConfig.get("reportHighlight", False)
			and "marked" not in markers_dict
			and get_method("marked") == CHOICE_tags
		):
			_apply_format_tag_names(["marked"])
	fieldCache.clear()
	fieldCache.update(field)
	textList.insert(0, ''.join(end_tag_list[::-1]))
	textList.append(''.join(start_tag_list))
	return braille.TEXT_SEPARATOR.join([x for x in textList if x])


def _addTextWithFields(self, info: textInfos.TextInfo, formatConfig: dict[str, Any], isSelection: bool = False) -> None:
	should_move_cursor_to_first_content = (not isSelection) and self.cursorPos is not None
	ctrl_fields: list[Any] = []
	typeform = louis.plain_text
	format_field_attributes_cache = getattr(
		info.obj, "_brailleFormatFieldAttributesCache", {})
	in_clickable = False
	if not info.isCollapsed:
		commands = info.getTextWithFields(formatConfig=formatConfig)
	else:
		commands = []
	for command in commands:
		if isinstance(command, str):
			in_clickable = False
			self._isFormatFieldAtStart = False
			if not command:
				continue
			if self._endsWithField:
				self.rawText += braille.TEXT_SEPARATOR
				self.rawTextTypeforms.append(louis.plain_text)
				self._rawToContentPos.append(self._currentContentPos)
			if isSelection and self.selectionStart is None:
				self.selectionStart = len(self.rawText)
			elif should_move_cursor_to_first_content:
				self.cursorPos = len(self.rawText)
				should_move_cursor_to_first_content = False
			self.rawText += command
			command_len = len(command)
			self.rawTextTypeforms.extend((typeform,) * command_len)
			end_pos = self._currentContentPos + command_len
			self._rawToContentPos.extend(range(self._currentContentPos, end_pos))
			self._currentContentPos = end_pos
			if isSelection:
				self.selectionEnd = len(self.rawText)
			self._endsWithField = False
		elif isinstance(command, textInfos.FieldCommand):
			cmd = command.command
			field = command.field
			if cmd == "formatChange":
				if isinstance(field, dict):
					_prepare_format_field_for_braille(field)
				typeform, brlex_typeform = self._getTypeformFromFormatField(
					field, formatConfig)
				text = getFormatFieldBraille(
					field, format_field_attributes_cache, self._isFormatFieldAtStart, formatConfig)
				if text:
					self._addFieldText(text, self._currentContentPos, False)
				self._len_brlex_typeforms += self._rawToContentPos.count(
					self._currentContentPos)
				self.brlex_typeforms[self._len_brlex_typeforms +
					self._currentContentPos] = brlex_typeform
				if not text:
					continue
				# Avoid TEXT_SEPARATOR before the next text run (no braille space after opening tags).
				self._endsWithField = False
				continue
			elif cmd == "controlStart":
				if self._skipFieldsNotAtStartOfNode and not field.get("_startOfNode"):
					text = None
				else:
					text_list: list[str] = []
					if not in_clickable and formatConfig["reportClickable"]:
						states = field.get("states")
						clickable = get_control_type("STATE_CLICKABLE")
						if states and clickable in states:
							field._presCat = pres_cat = field.getPresentationCategory(
								ctrl_fields, formatConfig)
							if not pres_cat or pres_cat is field.PRESCAT_LAYOUT:
								text_list.append(
									braille.positiveStateLabels[clickable])
							in_clickable = True
					text = info.getControlFieldBraille(
						field, ctrl_fields, True, formatConfig)
					if text:
						text_list.append(text)
					text = " ".join(text_list)
				ctrl_fields.append(field)
				if not text:
					continue
				if getattr(field, "_presCat") == field.PRESCAT_MARKER:
					field_start = len(self.rawText)
					if field_start > 0:
						field_start += 1
					if isSelection and self.selectionStart is None:
						self.selectionStart = field_start
					elif should_move_cursor_to_first_content:
						self.cursorPos = field_start
						should_move_cursor_to_first_content = False
				self._addFieldText(text, self._currentContentPos)
			elif cmd == "controlEnd":
				in_clickable = False
				field = ctrl_fields.pop()
				text = info.getControlFieldBraille(
					field, ctrl_fields, False, formatConfig)
				if not text:
					continue
				self._addFieldText(text, self._currentContentPos - 1)
			self._endsWithField = True
	if isSelection and self.selectionStart is None:
		self.cursorPos = len(self.rawText)
	if not self._skipFieldsNotAtStartOfNode:
		self._skipFieldsNotAtStartOfNode = True
	info.obj._brailleFormatFieldAttributesCache = format_field_attributes_cache


def nextLine(self) -> None:
	dest = self._readingInfo.copy()
	continue_ = True
	while continue_:
		moved = dest.move(self._getReadingUnit(), 1)
		if not moved:
			if self.allowPageTurns and isinstance(dest.obj, textInfos.DocumentWithPageTurns):
				try:
					dest.obj.turnPage()
				except RuntimeError as err:
					log.error(err)
					_stop_nvda_core_autoscroll()
					continue_ = False
				else:
					dest = dest.obj.makeTextInfo(textInfos.POSITION_FIRST)
			else:
				_stop_nvda_core_autoscroll()
				if get_auto_scroll():
					braille.handler.toggle_auto_scroll()
				return
		if continue_ and config.conf["brailleExtender"]["skipBlankLinesScroll"] or (
			get_auto_scroll() and (
				config.conf["brailleExtender"]["autoScroll"]["ignoreBlankLine"]
				or config.conf["brailleExtender"]["autoScroll"]["adjustToContent"])
		):
			dest_ = dest.copy()
			dest_.expand(textInfos.UNIT_LINE)
			continue_ = not dest_.text.strip()
		else:
			continue_ = False
	dest.collapse()
	self._setCursor(dest)
	_queue_braille_scroll_line_speech()


def previousLine(self, start: bool = False) -> None:
	dest = self._readingInfo.copy()
	dest.collapse()
	unit = self._getReadingUnit() if start else textInfos.UNIT_CHARACTER
	continue_ = True
	while continue_:
		moved = dest.move(unit, -1)
		if not moved:
			if self.allowPageTurns and isinstance(dest.obj, textInfos.DocumentWithPageTurns):
				try:
					dest.obj.turnPage(previous=True)
				except RuntimeError as err:
					log.error(err)
					_stop_nvda_core_autoscroll()
					continue_ = False
				else:
					dest = dest.obj.makeTextInfo(textInfos.POSITION_LAST)
					dest.expand(unit)
			else:
				_stop_nvda_core_autoscroll()
				return
		if continue_ and config.conf["brailleExtender"]["skipBlankLinesScroll"] or (
			get_auto_scroll() and config.conf["brailleExtender"]["autoScroll"]["ignoreBlankLine"]
		):
			dest_ = dest.copy()
			dest_.expand(textInfos.UNIT_LINE)
			continue_ = not dest_.text.strip()
		else:
			continue_ = False
	dest.collapse()
	self._setCursor(dest)
	_queue_braille_scroll_line_speech()


def executeGesture(gesture):
	script = gesture.script
	if "brailleDisplayDrivers" in str(type(gesture)):
		if (
			instanceGP.brailleKeyboardLocked
			and (
				(
					hasattr(script, "__func__")
					and script.__func__.__name__ != "script_toggleLockBrailleKeyboard"
				)
				or not hasattr(script, "__func__")
			)
		):
			return
		if (
			hasattr(script, "__func__")
			and (
				script.__func__.__name__ in [
					"script_braille_dots", "script_braille_enter",
					"script_volumePlus", "script_volumeMinus", "script_toggleVolume",
					"script_hourDate",
					"script_ctrl", "script_alt", "script_nvda", "script_win",
					"script_ctrlAlt", "script_ctrlAltWin", "script_ctrlAltWinShift", "script_ctrlAltShift","script_ctrlWin","script_ctrlWinShift","script_ctrlShift","script_altWin","script_altWinShift","script_altShift","script_winShift"
				] or (
					not NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING
					and not config.conf["brailleExtender"]['stopSpeechScroll']
					and script.__func__.__name__ in ["script_braille_scrollBack", "script_braille_scrollForward"]
				)
			)
		):
			gesture.speechEffectWhenExecuted = None
	return True


def sendChars(self, chars):
	"""Sends the provided unicode characters to the system.
	@param chars: The characters to send to the system.
	"""
	inputs = []
	chars = ''.join(c if ord(c) <= 0xffff else ''.join(
			chr(x) for x in struct.unpack('>2H', c.encode("utf-16be"))) for c in chars)
	if _useWinBindings:
		INPUT_TYPE = _user32.INPUT_TYPE
		KEYEVENTF = _user32.KEYEVENTF
		INPUT = _user32.INPUT
		for ch in chars:
			for direction in (0, KEYEVENTF.KEYUP):
				input_ = INPUT()
				input_.type = INPUT_TYPE.KEYBOARD
				input_.ii.ki = _user32.KEYBDINPUT()
				input_.ii.ki.wScan = ord(ch)
				input_.ii.ki.dwFlags = KEYEVENTF.UNICODE | direction
				inputs.append(input_)
		n = len(inputs)
		arr = (INPUT * n)(*inputs)
		_user32.SendInput(n, arr, ctypes.sizeof(INPUT))
	else:
		for ch in chars:
			for direction in (0, winUser.KEYEVENTF_KEYUP):
				input_ = winUser.Input()
				input_.type = winUser.INPUT_KEYBOARD
				input_.ii.ki = winUser.KeyBdInput()
				input_.ii.ki.wScan = ord(ch)
				input_.ii.ki.dwFlags = winUser.KEYEVENTF_UNICODE | direction
				inputs.append(input_)
		winUser.SendInput(inputs)
	focusObj = api.getFocusObject()
	if keyboardHandler.shouldUseToUnicodeEx(focusObj):
		for ch in chars:
			focusObj.event_typedCharacter(ch=ch)


def emulateKey(self, key, withModifiers=True):
	"""Emulates a key using the keyboard emulation system.
	If emulation fails (e.g. because of an unknown key), a debug warning is logged
	and the system falls back to sending unicode characters.
	@param withModifiers: Whether this key emulation should include the modifiers that are held virtually.
					Note that this method does not take care of clearing L{self.currentModifiers}.
	@type withModifiers: bool
	"""
	if withModifiers:
		keys = list(self.currentModifiers)
		keys.append(key)
		gesture = "+".join(keys)
	else:
		gesture = key
	try:
		inputCore.manager.emulateGesture(
			keyboardHandler.KeyboardInputGesture.fromName(gesture))
		instanceGP.lastShortcutPerformed = gesture
	except Exception:
		log.debugWarning(
			"Unable to emulate %r, falling back to sending unicode characters" % gesture, exc_info=True)
		self.sendChars(key)


def input_(self, dots):
	"""Handle one cell of braille input."""
	pos = self.untranslatedStart + self.untranslatedCursorPos
	endWord = dots == 0
	continue_ = True
	if config.conf["brailleExtender"]["oneHandedMode"]["enabled"]:
		continue_, endWord = processOneHandMode(self, dots)
		if not continue_:
			return
	else:
		self.bufferBraille.insert(pos, dots)
		self.untranslatedCursorPos += 1
	ok = False
	if instanceGP:
		focusObj = api.getFocusObject()
		ok = not self.currentModifiers and (
			not focusObj.treeInterceptor or focusObj.treeInterceptor.passThrough)
	if instanceGP and instanceGP.advancedInput and ok:
		pos = self.untranslatedStart + self.untranslatedCursorPos
		advancedInputStr = ''.join([chr(cell | 0x2800)
									for cell in self.bufferBraille[:pos]])
		if advancedInputStr:
			res = ''
			abreviations = advancedinput.getReplacements(
				[advancedInputStr])
			startUnicodeValue = "⠃⠙⠓⠕⠭⡃⡙⡓⡕⡭"
			if not abreviations and advancedInputStr[0] in startUnicodeValue:
				advancedInputStr = config.conf["brailleExtender"][
					"advancedInputMode"]["escapeSignUnicodeValue"] + advancedInputStr
			lenEscapeSign = len(
				config.conf["brailleExtender"]["advancedInputMode"]["escapeSignUnicodeValue"])
			if advancedInputStr == config.conf["brailleExtender"]["advancedInputMode"]["escapeSignUnicodeValue"] or (advancedInputStr.startswith(config.conf["brailleExtender"]["advancedInputMode"]["escapeSignUnicodeValue"]) and len(advancedInputStr) > lenEscapeSign and advancedInputStr[lenEscapeSign] in startUnicodeValue):
				equiv = {'⠃': 'b', '⠙': 'd', '⠓': 'h', '⠕': 'o', '⠭': 'x',
						 '⡃': 'B', '⡙': 'D', '⡓': 'H', '⡕': 'O', '⡭': 'X'}
				if advancedInputStr[-1] == '⠀':
					text = equiv[advancedInputStr[1]] + louis.backTranslate(
						getCurrentBrailleTables(True, brf=instanceGP.BRFMode), advancedInputStr[2:-1])[0]
					try:
						res = getCharFromValue(text)
						sendChar(res)
					except Exception as err:
						speech.speakMessage(repr(err))
						return badInput(self)
				else:
					self._reportUntranslated(pos)
			elif abreviations:
				if len(abreviations) == 1:
					res = abreviations[0].replacement
					sendChar(res)
				else:
					return self._reportUntranslated(pos)
			else:
				res = huc.isValidHUCInput(advancedInputStr)
				if res == huc.HUC_INPUT_INCOMPLETE: return self._reportUntranslated(pos)
				if res == huc.HUC_INPUT_INVALID: return badInput(self)
				res = huc.backTranslate(advancedInputStr)
				sendChar(res)
			if res and config.conf["brailleExtender"]["advancedInputMode"]["stopAfterOneChar"]:
				instanceGP.advancedInput = False
		return
	if not self.useContractedForCurrentFocus or endWord:
		if self._translate(endWord):
			if not endWord:
				self.cellsWithText.add(pos)
		elif self.bufferText and not self.useContractedForCurrentFocus and self._table.contracted:
			# Translators: Reported when translation didn't succeed due to unsupported input.
			speech.speakMessage(_("Unsupported input"))
			self.flushBuffer()
		else:
			self._reportUntranslated(pos)
	else:
		self._reportUntranslated(pos)

def sendChar(char):
	nvwave.playWaveFile(os.path.join(baseDir, "res/sounds/keyPress.wav"))
	core.callLater(0, brailleInput.handler.sendChars, char)
	if len(char) == 1:
		core.callLater(100, speech.speakSpelling, char)
	else:
		core.callLater(100, speech.speakMessage, char)


def badInput(self):
	nvwave.playWaveFile("waves/textError.wav")
	self.flushBuffer()
	pos = self.untranslatedStart + self.untranslatedCursorPos
	self._reportUntranslated(pos)


def _translate(self, endWord):
	"""Translate buffered braille up to the cursor.
	Any text produced is sent to the system.
	@param endWord: C{True} if this is the end of a word, C{False} otherwise.
	@type endWord: bool
	@return: C{True} if translation produced text, C{False} if not.
	@rtype: bool
	"""
	assert not self.useContractedForCurrentFocus or endWord, "Must only translate contracted at end of word"
	if self.useContractedForCurrentFocus:
		self.bufferText = ""
	oldTextLen = len(self.bufferText)
	pos = self.untranslatedStart + self.untranslatedCursorPos
	data = "".join([chr(cell | brailleInput.LOUIS_DOTS_IO_START)
					 for cell in self.bufferBraille[:pos]])
	mode = louis.dotsIO | louis.noUndefinedDots
	if (not self.currentFocusIsTextObj or self.currentModifiers) and self._table.contracted:
		mode |= louis.partialTrans
	self.bufferText = louis.backTranslate(getCurrentBrailleTables(True, brf=instanceGP.BRFMode),
										  data, mode=mode)[0]
	newText = self.bufferText[oldTextLen:]
	if newText:
		if self.useContractedForCurrentFocus or self.currentModifiers:
			speech._suppressSpeakTypedCharacters(len(newText))
		else:
			self._uncontSentTime = time.time()
		self.untranslatedStart = pos
		self.untranslatedCursorPos = 0
		if self.currentModifiers or not self.currentFocusIsTextObj:
			if len(newText) > 1:
				newText = ""
			else:
				self.emulateKey(newText)
		else:
			if config.conf["brailleExtender"]["smartCapsLock"] and winUser.getKeyState(winUser.VK_CAPITAL)&1:
				tmp = []
				for ch in newText:
					if ch.islower():
						tmp.append(ch.upper())
					else:
						tmp.append(ch.lower())
				newText = ''.join(tmp)
			self.sendChars(newText)

	if endWord or (newText and (not self.currentFocusIsTextObj or self.currentModifiers)):
		del self.bufferBraille[:pos]
		self.bufferText = ""
		self.cellsWithText.clear()
		if not instanceGP.modifiersLocked:
			self.currentModifiers.clear()
			instanceGP.clearMessageFlash()
		self.untranslatedStart = 0
		self.untranslatedCursorPos = 0

	if newText or endWord:
		self._updateUntranslated()
		return True

	return False


def _createTablesString(tablesList):
	"""Creates a tables string for liblouis calls"""
	return b",".join([x.encode(sys.getfilesystemencoding()) if isinstance(x, str) else bytes(x) for x in tablesList])


def _displayWithCursor(self):
	if not self._cells:
		return
	cells = list(self._cells)
	if self._cursorPos is not None and self._cursorBlinkUp and not self._auto_scroll:
		if self.getTether() == self.TETHER_FOCUS:
			cells[self._cursorPos] |= config.conf["braille"]["cursorShapeFocus"]
		else:
			cells[self._cursorPos] |= config.conf["braille"]["cursorShapeReview"]
	self._writeCells(cells)


origGetTether = _originals["BrailleHandler.getTether"]


def getTetherWithRoleTerminal(self):
	if config.conf["brailleExtender"]["speechHistoryMode"]["enabled"]:
		return speechhistorymode.TETHER_SPEECH
	return origGetTether(self)


_patchesApplied = False
_appliedPatches: set = set()


def _try_apply(name: str, apply_fn) -> bool:
	"""Try to apply a patch. Log on failure. Return True if applied."""
	try:
		apply_fn()
		_appliedPatches.add(name)
		return True
	except Exception as e:
		log.warning("BrailleExtender: Could not apply patch %s: %s", name, e, exc_info=True)
		return False


def apply_patches() -> None:
	"""Apply all BrailleExtender patches to NVDA core. Called at add-on load.
	Each patch is tried individually; failures are logged but do not prevent other patches.
	"""
	global _patchesApplied

	def _apply_braille_region():
		braille.getControlFieldBraille = getControlFieldBraille
		braille.getFormatFieldBraille = getFormatFieldBraille
		braille.Region.update = update_region
		braille.TextInfoRegion._addTextWithFields = _addTextWithFields
		braille.TextInfoRegion.update = update_TextInfoRegion
		braille.TextInfoRegion.previousLine = previousLine
		braille.TextInfoRegion.nextLine = nextLine
		braille.NVDAObjectRegion.update = update_NVDAObjectRegion
		braille.getPropertiesBraille = getPropertiesBraille
		braille.Region.parseUndefinedChars = True
		braille.Region.brlex_typeforms = {}
		braille.Region._len_brlex_typeforms = 0
		if _originals.get("TextInfoRegion._getTypeformFromFormatField"):
			pass  # Restored in unload
	_try_apply("braille_region", _apply_braille_region)

	def _apply_braille_input():
		brailleInput.BrailleInputHandler._translate = _translate
		brailleInput.BrailleInputHandler.emulateKey = emulateKey
		brailleInput.BrailleInputHandler.input = input_
		brailleInput.BrailleInputHandler.sendChars = sendChars
	_try_apply("braille_input", _apply_braille_input)

	def _apply_route_to():
		globalCommands.GlobalCommands.script_braille_routeTo = script_braille_routeTo
		if origFunc.get("script_braille_routeTo") and getattr(origFunc["script_braille_routeTo"], "__doc__", None):
			script_braille_routeTo.__doc__ = origFunc["script_braille_routeTo"].__doc__
	_try_apply("script_braille_routeTo", _apply_route_to)

	if hasattr(louis, "_createTablesString"):
		def _apply_louis():
			louis._createTablesString = _createTablesString
		_try_apply("louis_createTablesString", _apply_louis)

	def _apply_braille_handler():
		from .braille_terminal import (
			make_patched_handle_caret_move,
			make_patched_handle_gain_focus,
			make_patched_set_tether,
		)

		braille.BrailleHandler.AutoScroll = autoscroll.AutoScroll
		braille.BrailleHandler._auto_scroll = None
		braille.BrailleHandler.get_auto_scroll_delay = autoscroll.get_auto_scroll_delay
		braille.BrailleHandler.get_dynamic_auto_scroll_delay = autoscroll.get_dynamic_auto_scroll_delay
		braille.BrailleHandler.decrease_auto_scroll_delay = autoscroll.decrease_auto_scroll_delay
		braille.BrailleHandler.increase_auto_scroll_delay = autoscroll.increase_auto_scroll_delay
		braille.BrailleHandler.report_auto_scroll_delay = autoscroll.report_auto_scroll_delay
		braille.BrailleHandler.toggle_auto_scroll = autoscroll.toggle_auto_scroll
		braille.BrailleHandler._displayWithCursor = _displayWithCursor
		braille.BrailleHandler.getTether = getTetherWithRoleTerminal
		braille.BrailleHandler.handleGainFocus = make_patched_handle_gain_focus(_originals)
		if _originals.get("BrailleHandler.setTether"):
			braille.BrailleHandler.setTether = make_patched_set_tether(_originals)
		if _originals.get("BrailleHandler.handleCaretMove"):
			braille.BrailleHandler.handleCaretMove = make_patched_handle_caret_move(_originals)
	_try_apply("braille_handler", _apply_braille_handler)

	def _apply_execute_gesture():
		inputCore.decide_executeGesture.register(executeGesture)
	_try_apply("executeGesture", _apply_execute_gesture)

	_patchesApplied = len(_appliedPatches) > 0
	if not _patchesApplied:
		log.error("BrailleExtender: No patches could be applied; add-on may not function correctly")
	else:
		log.debug("BrailleExtender: Applied %d patch groups: %s", len(_appliedPatches), _appliedPatches)
		try:
			speechhistorymode.install()
		except Exception:
			log.warning("BrailleExtender: could not install speech history hooks", exc_info=True)


def is_patch_applied(name: str) -> bool:
	"""Return True if the given patch group was successfully applied."""
	return name in _appliedPatches


def get_auto_scroll():
	"""Return braille.handler._auto_scroll if autoscroll patch is applied, else None."""
	if "braille_handler" not in _appliedPatches:
		return None
	return getattr(braille.handler, "_auto_scroll", None)

_executeGestureHandler = executeGesture
REASON_CARET = get_output_reason("CARET")


def unload_patches() -> None:
	"""Restore only the patches that were successfully applied."""
	global _patchesApplied
	if not _patchesApplied:
		return
	_patchesApplied = False
	applied = _appliedPatches.copy()
	_appliedPatches.clear()

	speechhistorymode.uninstall()

	if "executeGesture" in applied:
		try:
			inputCore.decide_executeGesture.unregister(_executeGestureHandler)
		except Exception:
			pass

	if "braille_region" in applied:
		try:
			braille.getControlFieldBraille = _originals["getControlFieldBraille"]
			braille.getFormatFieldBraille = _originals["getFormatFieldBraille"]
			braille.Region.update = _originals["Region.update"]
			braille.TextInfoRegion._addTextWithFields = _originals["TextInfoRegion._addTextWithFields"]
			braille.TextInfoRegion.update = _originals["TextInfoRegion.update"]
			braille.TextInfoRegion.previousLine = _originals["TextInfoRegion.previousLine"]
			braille.TextInfoRegion.nextLine = _originals["TextInfoRegion.nextLine"]
			if _originals.get("TextInfoRegion._getTypeformFromFormatField"):
				braille.TextInfoRegion._getTypeformFromFormatField = _originals["TextInfoRegion._getTypeformFromFormatField"]
			braille.NVDAObjectRegion.update = _originals["NVDAObjectRegion.update"]
			braille.getPropertiesBraille = _originals["getPropertiesBraille"]
			for attr in ("parseUndefinedChars", "brlex_typeforms", "_len_brlex_typeforms"):
				try:
					delattr(braille.Region, attr)
				except AttributeError:
					pass
		except Exception as e:
			log.warning("BrailleExtender: Error restoring braille_region patches: %s", e)

	if "braille_input" in applied:
		try:
			brailleInput.BrailleInputHandler._translate = _originals["BrailleInputHandler._translate"]
			brailleInput.BrailleInputHandler.emulateKey = _originals["BrailleInputHandler.emulateKey"]
			brailleInput.BrailleInputHandler.input = _originals["BrailleInputHandler.input"]
			brailleInput.BrailleInputHandler.sendChars = _originals["BrailleInputHandler.sendChars"]
		except Exception as e:
			log.warning("BrailleExtender: Error restoring braille_input patches: %s", e)

	if "script_braille_routeTo" in applied:
		try:
			globalCommands.GlobalCommands.script_braille_routeTo = _originals["script_braille_routeTo"]
		except Exception as e:
			log.warning("BrailleExtender: Error restoring script_braille_routeTo: %s", e)

	if "braille_handler" in applied:
		try:
			braille.BrailleHandler.getTether = _originals["BrailleHandler.getTether"]
			if _originals.get("BrailleHandler.handleGainFocus"):
				braille.BrailleHandler.handleGainFocus = _originals["BrailleHandler.handleGainFocus"]
			if _originals.get("BrailleHandler.setTether"):
				braille.BrailleHandler.setTether = _originals["BrailleHandler.setTether"]
			if _originals.get("BrailleHandler.handleCaretMove"):
				braille.BrailleHandler.handleCaretMove = _originals["BrailleHandler.handleCaretMove"]
			if _originals.get("BrailleHandler._displayWithCursor"):
				braille.BrailleHandler._displayWithCursor = _originals["BrailleHandler._displayWithCursor"]
			for attr in ("AutoScroll", "_auto_scroll", "get_auto_scroll_delay", "get_dynamic_auto_scroll_delay",
					"decrease_auto_scroll_delay", "increase_auto_scroll_delay", "report_auto_scroll_delay",
					"toggle_auto_scroll"):
				try:
					delattr(braille.BrailleHandler, attr)
				except AttributeError:
					pass
		except Exception as e:
			log.warning("BrailleExtender: Error restoring braille_handler patches: %s", e)

	if "louis_createTablesString" in applied and "_createTablesString" in _originals:
		try:
			louis._createTablesString = _originals["_createTablesString"]
		except Exception as e:
			log.warning("BrailleExtender: Error restoring louis patch: %s", e)

	log.info("BrailleExtender patches unloaded")
