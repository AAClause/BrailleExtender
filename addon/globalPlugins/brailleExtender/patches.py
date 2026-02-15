# coding: utf-8
# patches.py - Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush CLAUSE, released under GPL.

import ctypes
import os
import re
import struct
import sys
import time

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
	baseDir, CHOICE_tags, IS_CURRENT_NO, RC_EMULATE_ARROWS_BEEP, RC_EMULATE_ARROWS_SILENT,
	NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING, NVDA_HAS_SPEAK_ON_ROUTING, NVDA_HAS_SPEAK_ON_NAVIGATING_BY_UNIT,
)
from .documentformatting import get_method, get_tags, N_, normalizeTextAlign, normalize_report_key
from .objectpresentation import getPropertiesBraille, selectedElementEnabled, update_NVDAObjectRegion
from .onehand import process as processOneHandMode
from .utils import getCurrentChar, getSpeechSymbols, getTether, getCharFromValue, getCurrentBrailleTables, get_output_reason, get_control_type

addonHandler.initTranslation()

instanceGP = None

roleLabels = braille.roleLabels
landmarkLabels = braille.landmarkLabels

def SELECTION_SHAPE(): return braille.SELECTION_SHAPE


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
	# Skip when NVDA core provides this (since 2025.1 via speakOnNavigatingByUnit)
	if NVDA_HAS_SPEAK_ON_NAVIGATING_BY_UNIT:
		return
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
	if braille.handler.buffer == braille.handler.mainBuffer and braille.handler.getTether() == "speech":
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


variationSelectorsPattern = lambda: r"([^\ufe00-\ufe0f])[\ufe00-\ufe0f]\u20E3?"


def update_region(self):
	"""Update this region.
	Subclasses should extend this to update L{rawText}, L{cursorPos}, L{selectionStart} and L{selectionEnd} if necessary.
	The base class method handles translation of L{rawText} into braille, placing the result in L{brailleCells}.
	Typeform information from L{rawTextTypeforms} is used, if any.
	L{rawToBraillePos} and L{brailleToRawPos} are updated according to the translation.
	L{brailleCursorPos}, L{brailleSelectionStart} and L{brailleSelectionEnd} are similarly updated based on L{cursorPos}, L{selectionStart} and L{selectionEnd}, respectively.
	@postcondition: L{brailleCells}, L{brailleCursorPos}, L{brailleSelectionStart} and L{brailleSelectionEnd} are updated and ready for rendering.
	"""
	if config.conf["brailleExtender"]["advanced"]["fixCursorPositions"]:
		pattern = variationSelectorsPattern()
		matches = re.finditer(pattern, self.rawText)
		posToRemove = []
		for match in matches:
			posToRemove += list(range(match.start() + 1, match.end()))
		self.rawText = re.sub(pattern, r"\1", self.rawText)
		if isinstance(self.cursorPos, int):
			adjustCursor = len(list(filter(lambda e: e<=self.cursorPos, posToRemove)))
			self.cursorPos -= adjustCursor
		if isinstance(self.selectionStart, int):
			adjustCursor = len(list(filter(lambda e: e<=self.selectionStart, posToRemove)))
			self.selectionStart -= adjustCursor
		if isinstance(self.selectionEnd, int):
			adjustCursor = len(list(filter(lambda e: e<=self.selectionEnd, posToRemove)))
			self.selectionEnd -= adjustCursor
	mode = louis.dotsIO
	if config.conf["braille"]["expandAtCursor"] and self.cursorPos is not None:
		mode |= louis.compbrlAtCursor
	self.brailleCells, self.brailleToRawPos, self.rawToBraillePos, self.brailleCursorPos = louisHelper.translate(
		getCurrentBrailleTables(brf=instanceGP.BRFMode),
		self.rawText,
		typeform=self.rawTextTypeforms,
		mode=mode,
		cursorPos=self.cursorPos
	)
	if (self.parseUndefinedChars
		and config.conf["brailleExtender"]["undefinedCharsRepr"]["method"] != undefinedchars.CHOICE_tableBehaviour
		and len(self.rawText) <= config.conf["brailleExtender"]["undefinedCharsRepr"]["characterLimit"]
	):
		undefinedchars.undefinedCharProcess(self)
	if selectedElementEnabled():
		d = {
			addoncfg.CHOICE_dot7: 64,
			addoncfg.CHOICE_dot8: 128,
			addoncfg.CHOICE_dots78: 192
		}
		if config.conf["brailleExtender"]["objectPresentation"]["selectedElement"] in d:
			addDots = d[config.conf["brailleExtender"]["objectPresentation"]["selectedElement"]]
			if hasattr(self, "obj") and self.obj and hasattr(self.obj, "states") and self.obj.states and self.obj.name and get_control_type("STATE_SELECTED") in self.obj.states:
				name = self.obj.name
				if config.conf["brailleExtender"]["advanced"]["fixCursorPositions"]:
					name = re.sub(variationSelectorsPattern(), r"\1", name)
				if name in self.rawText:
					start = self.rawText.index(name)
					end = start + len(name)-1
					startBraillePos, _ = regionhelper.getBraillePosFromRawPos(
						self, start)
					_, endBraillePos = regionhelper.getBraillePosFromRawPos(
						self, end)
					self.brailleCells = [cell | addDots if startBraillePos <= pos <=
										 endBraillePos else cell for pos, cell in enumerate(self.brailleCells)]
	if self.selectionStart is not None and self.selectionEnd is not None:
		try:
			self.brailleSelectionStart = self.rawToBraillePos[self.selectionStart]
			if self.selectionEnd >= len(self.rawText):
				self.brailleSelectionEnd = len(self.brailleCells)
			else:
				self.brailleSelectionEnd = self.rawToBraillePos[self.selectionEnd]
			for pos in range(self.brailleSelectionStart, self.brailleSelectionEnd):
				self.brailleCells[pos] |= SELECTION_SHAPE()
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
		self.rawText += ' '
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
	presCat = field.getPresentationCategory(ancestors, formatConfig)
	field._presCat = presCat
	role = field.get("role", get_control_type("ROLE_UNKNOWN"))
	if reportStart:
		if presCat == field.PRESCAT_CONTAINER and not field.get("_startOfNode"):
			return None
	else:
		if (
				not field.get("_endOfNode")
				or presCat != field.PRESCAT_CONTAINER
		):
			return None

	states = field.get("states", set())
	value = field.get('value', None)
	childControlCount = int(field.get('_childcontrolcount',"0"))
	current = field.get("current", IS_CURRENT_NO)
	placeholder = field.get('placeholder', None)
	roleText = field.get('roleTextBraille', field.get('roleText'))
	roleTextPost = None
	landmark = field.get("landmark")
	if not roleText and role == get_control_type("ROLE_LANDMARK") and landmark:
		roleText = f'{roleLabels[get_control_type("ROLE_LANDMARK")]} {landmarkLabels[landmark]}'
	content = field.get("content")

	if childControlCount and role == get_control_type("ROLE_LIST"):
		roleTextPost = "(%s)" % childControlCount
	if childControlCount and role == get_control_type("ROLE_TABLE"):
		row_count = field.get("table-rowcount", 0)
		column_count = field.get("table-columncount", 0)
		roleTextPost = f"({row_count},{column_count})"
	if presCat == field.PRESCAT_LAYOUT:
		text = []
		if current:
			text.append(getPropertiesBraille(current=current))
		if role == get_control_type("ROLE_GRAPHIC") and content:
			text.append(content)
		return braille.TEXT_SEPARATOR.join(text) if len(text) != 0 else None

	if role in (get_control_type("ROLE_TABLECELL"), get_control_type("ROLE_TABLECOLUMNHEADER"), get_control_type("ROLE_TABLEROWHEADER")) and field.get("table-id"):
		reportTableHeaders = formatConfig["reportTableHeaders"]
		reportTableCellCoords = formatConfig["reportTableCellCoords"]
		props = {
			"states": states,
			"rowNumber": (field.get("table-rownumber-presentational") or field.get("table-rownumber")),
			"columnNumber": (field.get("table-columnnumber-presentational") or field.get("table-columnnumber")),
			"rowSpan": field.get("table-rowsspanned"),
			"columnSpan": field.get("table-columnsspanned"),
			"includeTableCellCoords": reportTableCellCoords,
			"current": current,
		}
		if reportTableHeaders:
			props["columnHeaderText"] = field.get("table-columnheadertext")
		return getPropertiesBraille(**props)

	if reportStart:
		props = {
			"_role" if role == get_control_type("ROLE_MATH") else "role": role,
			"states": states,
			"value": value,
			"current": current,
			"placeholder": placeholder,
			"roleText": roleText,
			"roleTextPost": roleTextPost
		}
		if field.get("alwaysReportName", False):
			name = field.get("name")
			if name:
				props["name"] = name
		if config.conf["presentation"]["reportKeyboardShortcuts"]:
			kbShortcut = field.get("keyboardShortcut")
			if kbShortcut:
				props["keyboardShortcut"] = kbShortcut
		level = field.get("level")
		if level:
			props["positionInfo"] = {"level": level}
		text = getPropertiesBraille(**props)
		if content:
			if text:
				text += braille.TEXT_SEPARATOR
			text += content
		elif role == get_control_type("ROLE_MATH"):
			import mathPres
			if hasattr(mathPres, "ensureInit"):
				mathPres.ensureInit()
			if mathPres.brailleProvider:
				try:
					if text:
						text += braille.TEXT_SEPARATOR
					text += mathPres.brailleProvider.getBrailleForMathMl(
						info.getMathMl(field))
				except (NotImplementedError, LookupError):
					pass
		return text

	return N_("%s end") % getPropertiesBraille(
		role=role,
		roleText=roleText,
	)


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
		if formatConfig["reportParagraphIndentation"]:
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
				textList.append((N_("h%s") % headingLevel)+' ')

	if formatConfig["reportPage"]:
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

	if formatConfig["reportAlignment"]:
		textAlign = normalizeTextAlign(field.get("text-align"))
		old_textAlign = normalizeTextAlign(fieldCache.get("text-align"))
		if textAlign and textAlign != old_textAlign:
			tag = get_tags(f"text-align:{textAlign}")
			if tag:
				textList.append(tag.start)

	if formatConfig["reportLinks"]:
		link = field.get("link")
		oldLink = fieldCache.get("link") if fieldCache else None
		if link and link != oldLink:
			textList.append(braille.roleLabels[get_control_type("ROLE_LINK")] +' ')

	if formatConfig["reportStyle"]:
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
	if formatConfig["reportFontName"]:
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
	if formatConfig["reportFontSize"]:
		fontSize = field.get("font-size")
		oldFontSize = fieldCache.get(
			"font-size") if fieldCache is not None else None
		if fontSize and fontSize != oldFontSize:
			textList.append("⣏%s⣹" % fontSize)
	if formatConfig["reportColor"]:
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

	if formatConfig["reportRevisions"]:
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
		old_comment = fieldCache.get("comment")
		tag = get_tags("comments")
		if not old_comment and comment:
			textList.append(tag.start)
		elif old_comment and not comment:
			textList.append(tag.end)

	start_tag_list = []
	end_tag_list = []

	tags = []
	fontAttributeReporting = formatConfig.get("fontAttributeReporting")
	if fontAttributeReporting is None:
		fontAttributeReporting = formatConfig.get("reportFontAttributes")
	else:
		fontAttributeReporting = fontAttributeReporting == 1
	if fontAttributeReporting:
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
	if formatConfig.get("reportSpellingErrors", False):
		tags += [tag for tag in [
			"invalid-spelling",
			"invalid-grammar"] if get_method(tag) == CHOICE_tags
		]

		for name_tag in tags:
			name_field = name_tag.split(':')[0]
			value_field = name_tag.split(
				':', 1)[1] if ':' in name_tag else None
			field_value = field.get(name_field)
			old_field_value = fieldCache.get(
				name_field) if fieldCache else None
			tag = get_tags(f"{name_field}:{field_value}")
			old_tag = get_tags(f"{name_field}:{old_field_value}")
			if value_field != old_field_value and old_tag and old_field_value:
				if old_field_value != field_value:
					end_tag_list.append(old_tag.end)
			if field_value and tag and field_value != value_field and field_value != old_field_value:
				start_tag_list.append(tag.start)
	fieldCache.clear()
	fieldCache.update(field)
	textList.insert(0, ''.join(end_tag_list[::-1]))
	textList.append(''.join(start_tag_list))
	return braille.TEXT_SEPARATOR.join([x for x in textList if x])


def _addTextWithFields(self, info, formatConfig, isSelection=False):
	shouldMoveCursorToFirstContent = not isSelection and self.cursorPos is not None
	ctrlFields = []
	typeform = louis.plain_text
	formatFieldAttributesCache = getattr(
		info.obj, "_brailleFormatFieldAttributesCache", {})
	inClickable = False
	for command in info.getTextWithFields(formatConfig=formatConfig):
		if isinstance(command, str):
			inClickable = False
			self._isFormatFieldAtStart = False
			if not command:
				continue
			if self._endsWithField:
				self.rawText += braille.TEXT_SEPARATOR
				self.rawTextTypeforms.append(louis.plain_text)
				self._rawToContentPos.append(self._currentContentPos)
			if isSelection and self.selectionStart is None:
				self.selectionStart = len(self.rawText)
			elif shouldMoveCursorToFirstContent:
				self.cursorPos = len(self.rawText)
				shouldMoveCursorToFirstContent = False
			self.rawText += command
			commandLen = len(command)
			self.rawTextTypeforms.extend((typeform,) * commandLen)
			endPos = self._currentContentPos + commandLen
			self._rawToContentPos.extend(
				range(self._currentContentPos, endPos))
			self._currentContentPos = endPos
			if isSelection:
				self.selectionEnd = len(self.rawText)
			self._endsWithField = False
		elif isinstance(command, textInfos.FieldCommand):
			cmd = command.command
			field = command.field
			if cmd == "formatChange":
				typeform, brlex_typeform = self._getTypeformFromFormatField(
					field, formatConfig)
				text = getFormatFieldBraille(
					field, formatFieldAttributesCache, self._isFormatFieldAtStart, formatConfig)
				if text:
					self._addFieldText(text, self._currentContentPos, False)
				self._len_brlex_typeforms += self._rawToContentPos.count(
					self._currentContentPos)
				self.brlex_typeforms[self._len_brlex_typeforms +
					self._currentContentPos] = brlex_typeform
				if not text:
					continue
			elif cmd == "controlStart":
				if self._skipFieldsNotAtStartOfNode and not field.get("_startOfNode"):
					text = None
				else:
					textList = []
					if not inClickable and formatConfig['reportClickable']:
						states = field.get('states')
						if states and get_control_type("STATE_CLICKABLE") in states:
							field._presCat = presCat = field.getPresentationCategory(
								ctrlFields, formatConfig)
							if not presCat or presCat is field.PRESCAT_LAYOUT:
								textList.append(
									braille.positiveStateLabels[get_control_type("STATE_CLICKABLE")])
							inClickable = True
					text = info.getControlFieldBraille(
						field, ctrlFields, True, formatConfig)
					if text:
						textList.append(text)
					text = " ".join(textList)
				ctrlFields.append(field)
				if not text:
					continue
				if getattr(field, "_presCat") == field.PRESCAT_MARKER:
					fieldStart = len(self.rawText)
					if fieldStart > 0:
						fieldStart += 1
					if isSelection and self.selectionStart is None:
						self.selectionStart = fieldStart
					elif shouldMoveCursorToFirstContent:
						self.cursorPos = fieldStart
						shouldMoveCursorToFirstContent = False
				self._addFieldText(text, self._currentContentPos,)
			elif cmd == "controlEnd":
				inClickable = False
				field = ctrlFields.pop()
				text = info.getControlFieldBraille(
					field, ctrlFields, False, formatConfig)
				if not text:
					continue
				self._addFieldText(text, self._currentContentPos - 1)
			self._endsWithField = True
	if isSelection and self.selectionStart is None:
		self.cursorPos = len(self.rawText)
	if not self._skipFieldsNotAtStartOfNode:
		self._skipFieldsNotAtStartOfNode = True
	info.obj._brailleFormatFieldAttributesCache = formatFieldAttributesCache


def nextLine(self):
	dest = self._readingInfo.copy()
	continue_ = True
	while continue_:
		moved = dest.move(self._getReadingUnit(), 1)
		if not moved:
			if self.allowPageTurns and isinstance(dest.obj, textInfos.DocumentWithPageTurns):
				try: dest.obj.turnPage()
				except RuntimeError as err:
					log.error(err)
					continue_ = False
				else: dest = dest.obj.makeTextInfo(textInfos.POSITION_FIRST)
			else:
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
	if NVDA_HAS_SPEAK_ON_NAVIGATING_BY_UNIT:
		from braille import _speakOnNavigatingByUnit
		def _speakLine():
			_speakOnNavigatingByUnit(dest.copy(), self._getReadingUnit())
		queueHandler.queueFunction(queueHandler.eventQueue, _speakLine)
	else:
		queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
		queueHandler.queueFunction(queueHandler.eventQueue, sayCurrentLine)


def previousLine(self, start=False):
	dest = self._readingInfo.copy()
	dest.collapse()
	if start: unit = self._getReadingUnit()
	else: unit = textInfos.UNIT_CHARACTER
	continue_ = True
	while continue_:
		moved = dest.move(unit, -1)
		if not moved:
			if self.allowPageTurns and isinstance(dest.obj, textInfos.DocumentWithPageTurns):
				try: dest.obj.turnPage(previous=True)
				except RuntimeError as err:
					log.error(err)
					continue_ = False
				else:
					dest = dest.obj.makeTextInfo(textInfos.POSITION_LAST)
					dest.expand(unit)
			else: return
		if continue_ and config.conf["brailleExtender"]["skipBlankLinesScroll"] or (get_auto_scroll() and config.conf["brailleExtender"]["autoScroll"]["ignoreBlankLine"]):
			dest_ = dest.copy()
			dest_.expand(textInfos.UNIT_LINE)
			continue_ = not dest_.text.strip()
		else:
			continue_ = False
	dest.collapse()
	self._setCursor(dest)
	if NVDA_HAS_SPEAK_ON_NAVIGATING_BY_UNIT:
		from braille import _speakOnNavigatingByUnit
		def _speakLine():
			_speakOnNavigatingByUnit(dest.copy(), self._getReadingUnit())
		queueHandler.queueFunction(queueHandler.eventQueue, _speakLine)
	else:
		queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
		queueHandler.queueFunction(queueHandler.eventQueue, sayCurrentLine)


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
	except BaseException:
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
					except BaseException as err:
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
	role = None
	try:
		obj = api.getNavigatorObject()
	except OSError:
		obj = None
	if obj:
		role = api.getNavigatorObject().role
	if (
		config.conf["brailleExtender"]["reviewModeTerminal"]
		and role == controlTypes.ROLE_TERMINAL
	):
		return braille.handler.TETHER_REVIEW
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
	_try_apply("braille_handler", _apply_braille_handler)

	def _apply_execute_gesture():
		inputCore.decide_executeGesture.register(executeGesture)
	_try_apply("executeGesture", _apply_execute_gesture)

	_patchesApplied = len(_appliedPatches) > 0
	if not _patchesApplied:
		log.error("BrailleExtender: No patches could be applied; add-on may not function correctly")
	else:
		log.debug("BrailleExtender: Applied %d patch groups: %s", len(_appliedPatches), _appliedPatches)


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
