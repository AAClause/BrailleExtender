# coding: utf-8
# patches.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush CLAUSE, released under GPL.
# This file modify some functions from core.
# coding: utf-8

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

from . import addoncfg
from . import advancedinput
from . import autoscroll
from . import huc
from . import regionhelper
from . import speechhistorymode
from . import undefinedchars
from .common import baseDir, CHOICE_tags, IS_CURRENT_NO, RC_EMULATE_ARROWS_BEEP, RC_EMULATE_ARROWS_SILENT
from .documentformatting import get_method, get_tags, N_, normalizeTextAlign, normalize_report_key
from .objectpresentation import getPropertiesBraille, selectedElementEnabled, update_NVDAObjectRegion
from .onehand import process as processOneHandMode
from .utils import getCurrentChar, getSpeechSymbols, getTether, getCharFromValue, getCurrentBrailleTables, get_output_reason, get_control_type

addonHandler.initTranslation()

instanceGP = None

roleLabels = braille.roleLabels
landmarkLabels = braille.landmarkLabels

def SELECTION_SHAPE(): return braille.SELECTION_SHAPE


origFunc = {
	"script_braille_routeTo": globalCommands.GlobalCommands.script_braille_routeTo,
	"update": braille.Region.update,
	"_createTablesString": louis._createTablesString,
	"update_TextInfoRegion": braille.TextInfoRegion.update,
}


def sayCurrentLine():
	global instanceGP
	if not braille.handler._auto_scroll:
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

# globalCommands.GlobalCommands.script_braille_routeTo()
def say_character_under_braille_routing_cursor(gesture):
	if not braille.handler._auto_scroll and scriptHandler.getLastScriptRepeatCount() == 0 and config.conf["brailleExtender"]["speakRoutingTo"]:
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
	if braille.handler._auto_scroll and braille.handler.buffer is braille.handler.mainBuffer:
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


# braille.Region.update()
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
			# Mark the selection.
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
		# The stripped text is shorter than the original.
		self._currentContentPos = self._rawToContentPos[rawTextLen]
		del self.rawTextTypeforms[rawTextLen:]
		# Trimming _rawToContentPos doesn't matter,
		# because we'll only ever ask for indexes valid in rawText.
		#del self._rawToContentPos[rawTextLen:]
	if rawTextLen == 0 or not self._endsWithField:
		# There is no text left after stripping line ending characters,
		# or the last item added can be navigated with a cursor.
		# Add a space in case the cursor is at the end of the reading unit.
		self.rawText += ' '
		rawTextLen += 1
		self.rawTextTypeforms.append(louis.plain_text)
		self._rawToContentPos.append(self._currentContentPos)
	if self.cursorPos is not None and self.cursorPos >= rawTextLen:
		self.cursorPos = rawTextLen - 1
	# The selection end doesn't have to be checked, Region.update() makes sure brailleSelectionEnd is valid.

	# If this is not the start of the object, hide all previous regions.
	start = readingInfo.obj.makeTextInfo(textInfos.POSITION_FIRST)
	self.hidePreviousRegions = (
		start.compareEndPoints(readingInfo, "startToStart") < 0)
	# Don't touch focusToHardLeft if it is already true
	# For example, it can be set to True in getFocusContextRegions when this region represents the first new focus ancestor
	# Alternatively, BrailleHandler._doNewObject can set this to True when this region represents the focus object and the focus ancestry didn't change
	if not self.focusToHardLeft:
		# If this is a multiline control, position it at the absolute left of the display when focused.
		self.focusToHardLeft = self._isMultiline()
	super(braille.TextInfoRegion, self).update()

	if rawInputIndStart is not None:
		assert rawInputIndEnd is not None, "rawInputIndStart set but rawInputIndEnd isn't"
		# These are the start and end of the untranslated input area,
		# including the start and end indicators.
		self._brailleInputIndStart = self.rawToBraillePos[rawInputIndStart]
		self._brailleInputIndEnd = self.rawToBraillePos[rawInputIndEnd]
		# These are the start and end of the actual untranslated input, excluding indicators.
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
	# Cache this for later use.
	field._presCat = presCat
	role = field.get("role", get_control_type("ROLE_UNKNOWN"))
	if reportStart:
		# If this is a container, only report it if this is the start of the node.
		if presCat == field.PRESCAT_CONTAINER and not field.get("_startOfNode"):
			return None
	else:
		# We only report ends for containers that are not landmarks/regions
		# and only if this is the end of the node.
		if (
				not field.get("_endOfNode")
				or presCat != field.PRESCAT_CONTAINER
				#or role == get_control_type("ROLE_LANDMARK")
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
		# Table cell.
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
			# Don't report the role for math here.
			# However, we still need to pass it (hence "_role").
			"_role" if role == get_control_type("ROLE_MATH") else "role": role,
			"states": states,
			"value": value,
			"current": current,
			"placeholder": placeholder,
			"roleText": roleText,
			"roleTextPost": roleTextPost
		}
		if field.get("alwaysReportName", False):
			# Ensure that the name of the field gets presented even if normally it wouldn't.
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

		# Because we do not want to report the number of columns when a document is just opened and there is only
		# one column. This would be verbose, in the standard case.
		# column number has changed, or the columnCount has changed
		# but not if the columnCount is 1 or less and there is no old columnCount.
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
	if formatConfig["reportFontAttributes"]:
		tags += [tag for tag in [
			"bold",
			"italic",
			"underline",
			"strikethrough"] if get_method(tag) == CHOICE_tags
		]
	if (normalize_report_key("superscriptsAndSubscripts") and formatConfig["reportSuperscriptsAndSubscripts"]) or formatConfig["reportFontAttributes"]:
		tags += [tag for tag in [
			"text-position:sub",
			"text-position:super"] if get_method(tag) == CHOICE_tags
		]
	if formatConfig["reportSpellingErrors"]:
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


# braille.TextInfoRegion._addTextWithFields
def _addTextWithFields(self, info, formatConfig, isSelection=False):
	shouldMoveCursorToFirstContent = not isSelection and self.cursorPos is not None
	ctrlFields = []
	typeform = louis.plain_text
	formatFieldAttributesCache = getattr(
		info.obj, "_brailleFormatFieldAttributesCache", {})
	# When true, we are inside a clickable field, and should therefore not report any more new clickable fields
	inClickable = False
	for command in info.getTextWithFields(formatConfig=formatConfig):
		if isinstance(command, str):
			# Text should break a run of clickables
			inClickable = False
			self._isFormatFieldAtStart = False
			if not command:
				continue
			if self._endsWithField:
				# The last item added was a field,
				#? so add a space before the content.
				self.rawText += braille.TEXT_SEPARATOR
				self.rawTextTypeforms.append(louis.plain_text)
				self._rawToContentPos.append(self._currentContentPos)
			if isSelection and self.selectionStart is None:
				# This is where the content begins.
				self.selectionStart = len(self.rawText)
			elif shouldMoveCursorToFirstContent:
				# This is the first piece of content after the cursor.
				# Position the cursor here, as it may currently be positioned on control field text.
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
				# The last time this is set will be the end of the content.
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
							# We have entered an outer most clickable or entered a new clickable after exiting a previous one
							# Report it if there is nothing else interesting about the field
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
				# Place this field on a stack so we can access it for controlEnd.
				ctrlFields.append(field)
				if not text:
					continue
				if getattr(field, "_presCat") == field.PRESCAT_MARKER:
					# In this case, the field text is what the user cares about,
					# not the actual content.
					fieldStart = len(self.rawText)
					if fieldStart > 0:
						# There'll be a space before the field text.
						fieldStart += 1
					if isSelection and self.selectionStart is None:
						self.selectionStart = fieldStart
					elif shouldMoveCursorToFirstContent:
						self.cursorPos = fieldStart
						shouldMoveCursorToFirstContent = False
				# Map this field text to the start of the field's content.
				self._addFieldText(text, self._currentContentPos,)
			elif cmd == "controlEnd":
				# Exiting a controlField should break a run of clickables
				inClickable = False
				field = ctrlFields.pop()
				text = info.getControlFieldBraille(
					field, ctrlFields, False, formatConfig)
				if not text:
					continue
				# Map this field text to the end of the field's content.
				self._addFieldText(text, self._currentContentPos - 1)
			self._endsWithField = True
	if isSelection and self.selectionStart is None:
		# There is no selection. This is a cursor.
		self.cursorPos = len(self.rawText)
	if not self._skipFieldsNotAtStartOfNode:
		# We only render fields that aren't at the start of their nodes for the first part of the reading unit.
		# Otherwise, we'll render fields that have already been rendered.
		self._skipFieldsNotAtStartOfNode = True
	info.obj._brailleFormatFieldAttributesCache = formatFieldAttributesCache


# braille.TextInfoRegion.nextLine()
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
				if braille.handler._auto_scroll:
					braille.handler.toggle_auto_scroll()
				return
		if continue_ and config.conf["brailleExtender"]["skipBlankLinesScroll"] or (
			braille.handler._auto_scroll and (
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
	queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
	queueHandler.queueFunction(queueHandler.eventQueue, sayCurrentLine)


# braille.TextInfoRegion.previousLine()
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
		if continue_ and config.conf["brailleExtender"]["skipBlankLinesScroll"] or (braille.handler._auto_scroll and config.conf["brailleExtender"]["autoScroll"]["ignoreBlankLine"]):
			dest_ = dest.copy()
			dest_.expand(textInfos.UNIT_LINE)
			continue_ = not dest_.text.strip()
		else:
			continue_ = False
	dest.collapse()
	self._setCursor(dest)
	queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
	queueHandler.queueFunction(queueHandler.eventQueue, sayCurrentLine)


# inputCore.InputManager.executeGesture
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
					not config.conf["brailleExtender"]['stopSpeechScroll']
					and script.__func__.__name__ in ["script_braille_scrollBack", "script_braille_scrollForward"]
				)
			)
		):
			gesture.speechEffectWhenExecuted = None
	return True

inputCore.decide_executeGesture.register(executeGesture)


# brailleInput.BrailleInputHandler.sendChars()
def sendChars(self, chars):
	"""Sends the provided unicode characters to the system.
	@param chars: The characters to send to the system.
	"""
	inputs = []
	chars = ''.join(c if ord(c) <= 0xffff else ''.join(
			chr(x) for x in struct.unpack('>2H', c.encode("utf-16be"))) for c in chars)
	for ch in chars:
		for direction in (0, winUser.KEYEVENTF_KEYUP):
			input = winUser.Input()
			input.type = winUser.INPUT_KEYBOARD
			input.ii.ki = winUser.KeyBdInput()
			input.ii.ki.wScan = ord(ch)
			input.ii.ki.dwFlags = winUser.KEYEVENTF_UNICODE | direction
			inputs.append(input)
	winUser.SendInput(inputs)
	focusObj = api.getFocusObject()
	if keyboardHandler.shouldUseToUnicodeEx(focusObj):
		# #10569: When we use ToUnicodeEx to detect typed characters,
		# emulated keypresses aren't detected.
		# Send TypedCharacter events manually.
		for ch in chars:
			focusObj.event_typedCharacter(ch=ch)


# brailleInput.BrailleInputHandler.emulateKey()
def emulateKey(self, key, withModifiers=True):
	"""Emulates a key using the keyboard emulation system.
	If emulation fails (e.g. because of an unknown key), a debug warning is logged
	and the system falls back to sending unicode characters.
	@param withModifiers: Whether this key emulation should include the modifiers that are held virtually.
					Note that this method does not take care of clearing L{self.currentModifiers}.
	@type withModifiers: bool
	"""
	if withModifiers:
		# The emulated key should be the last item in the identifier string.
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


# brailleInput.BrailleInputHandler.input()
def input_(self, dots):
	"""Handle one cell of braille input.
	"""
	# Insert the newly entered cell into the buffer at the cursor position.
	pos = self.untranslatedStart + self.untranslatedCursorPos
	# Space ends the word.
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
	# For uncontracted braille, translate the buffer for each cell added.
	# Any new characters produced are then sent immediately.
	# For contracted braille, translate the buffer only when a word is ended (i.e. a space is typed).
	# This is because later cells can change characters produced by previous cells.
	# For example, in English grade 2, "tg" produces just "tg",
	# but "tgr" produces "together".
	if not self.useContractedForCurrentFocus or endWord:
		if self._translate(endWord):
			if not endWord:
				self.cellsWithText.add(pos)
		elif self.bufferText and not self.useContractedForCurrentFocus and self._table.contracted:
			# Translators: Reported when translation didn't succeed due to unsupported input.
			speech.speakMessage(_("Unsupported input"))
			self.flushBuffer()
		else:
			# This cell didn't produce any text; e.g. number sign.
			self._reportUntranslated(pos)
	else:
		self._reportUntranslated(pos)

# brailleInput.BrailleInputHandler._translate()
# reason for patching: possibility to lock modifiers, display modifiers in braille during input, HUC Braille input


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
		# self.bufferText has been used by _reportContractedCell, so clear it.
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
		# New text was generated by the cells just entered.
		if self.useContractedForCurrentFocus or self.currentModifiers:
			# For contracted braille, an entire word is sent at once.
			# Don't speak characters as this is sent.
			# Also, suppress typed characters when emulating a command gesture.
			speech._suppressSpeakTypedCharacters(len(newText))
		else:
			self._uncontSentTime = time.time()
		self.untranslatedStart = pos
		self.untranslatedCursorPos = 0
		if self.currentModifiers or not self.currentFocusIsTextObj:
			if len(newText) > 1:
				# Emulation of multiple characters at once is unsupported
				# Clear newText, so this function returns C{False} if not at end of word
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
		# We only need to buffer one word.
		# Clear the previous word (anything before the cursor) from the buffer.
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


# louis._createTablesString()
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

origGetTether = braille.BrailleHandler.getTether

def getTetherWithRoleTerminal(self):
	if config.conf["brailleExtender"]["speechHistoryMode"]["enabled"]:
		return speechhistorymode.TETHER_SPEECH
	role = None
	obj = api.getNavigatorObject()
	if obj:
		role = api.getNavigatorObject().role
	if (
		config.conf["brailleExtender"]["reviewModeTerminal"]
		and role == controlTypes.ROLE_TERMINAL
	):
		return braille.handler.TETHER_REVIEW
	return origGetTether(self)


# applying patches
braille.getControlFieldBraille = getControlFieldBraille
braille.getFormatFieldBraille = getFormatFieldBraille
braille.Region.update = update_region
braille.TextInfoRegion._addTextWithFields = _addTextWithFields
braille.TextInfoRegion.update = update_TextInfoRegion
braille.TextInfoRegion.previousLine = previousLine
braille.TextInfoRegion.nextLine = nextLine
NoInputGestureAction = inputCore.NoInputGestureAction
brailleInput.BrailleInputHandler._translate = _translate
brailleInput.BrailleInputHandler.emulateKey = emulateKey
brailleInput.BrailleInputHandler.input = input_
brailleInput.BrailleInputHandler.sendChars = sendChars
globalCommands.GlobalCommands.script_braille_routeTo = script_braille_routeTo
louis._createTablesString = _createTablesString
script_braille_routeTo.__doc__ = origFunc["script_braille_routeTo"].__doc__
braille.NVDAObjectRegion.update = update_NVDAObjectRegion
braille.getPropertiesBraille = getPropertiesBraille

# This variable tells if braille region should parse undefined characters
braille.Region.parseUndefinedChars = True
REASON_CARET = get_output_reason("CARET")

braille.Region.brlex_typeforms = {}
braille.Region._len_brlex_typeforms = 0

braille.BrailleHandler.AutoScroll = autoscroll.AutoScroll
braille.BrailleHandler._auto_scroll = None
braille.BrailleHandler.get_auto_scroll_delay = autoscroll.get_auto_scroll_delay
braille.BrailleHandler.get_dynamic_auto_scroll_delay = autoscroll.get_dynamic_auto_scroll_delay
braille.BrailleHandler.decrease_auto_scroll_delay = autoscroll.decrease_auto_scroll_delay
braille.BrailleHandler.increase_auto_scroll_delay = autoscroll.increase_auto_scroll_delay
braille.BrailleHandler.report_auto_scroll_delay = autoscroll.report_auto_scroll_delay
braille.BrailleHandler.toggle_auto_scroll = autoscroll.toggle_auto_scroll
braille.BrailleHandler._displayWithCursor = _displayWithCursor

REASON_CARET = get_output_reason("CARET")
braille.BrailleHandler.getTether = getTetherWithRoleTerminal
