# coding: utf-8
# utils.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2021 André-Abush CLAUSE, released under GPL.

from __future__ import annotations

import os
import re

import addonHandler
import api
import appModuleHandler
import braille
import brailleInput
import brailleTables
import characterProcessing
import config
import controlTypes
import languageHandler
import louis
import scriptHandler
import speech
import textInfos
import ui
from keyboardHandler import KeyboardInputGesture

addonHandler.initTranslation()
import treeInterceptorHandler
import unicodedata
from .common import (
	INSERT_AFTER,
	INSERT_BEFORE,
	REPLACE_TEXT,
	baseDir,
	default_braille_table_file_for_cur_language,
	NVDA_HAS_AUTOMATIC_BRAILLE_TABLES,
)
from . import huc
from . import volumehelper

get_mute = volumehelper.get_mute
get_volume_level = volumehelper.get_volume_level

# liblouis marks “free” input combinations with back-translated text matching this shape.
_RE_OVERVIEW_UNUSED_COMBO = re.compile(r"^\\.+/$")


def _resolveInputTableFileName(name: str) -> str:
	"""Map config or UI value ``auto`` to a concrete input table file name."""
	if name == "auto":
		return default_braille_table_file_for_cur_language(is_input=True)
	return name


def _liblouisTablePaths(table_file: str) -> list[str]:
	"""Primary table plus ``braille-patterns.cti`` (absolute paths)."""
	tables_dir = brailleTables.TABLES_DIR
	return [
		os.path.join(tables_dir, table_file),
		os.path.join(tables_dir, "braille-patterns.cti"),
	]


def report_volume_level():
	from .addoncfg import CHOICE_braille, CHOICE_speech, CHOICE_speechAndBraille
	if get_mute() and config.conf["brailleExtender"]["volumeChangeFeedback"] in [CHOICE_braille, CHOICE_speechAndBraille]:
		return braille.handler.message(_("Muted sound"))
	volume_level = get_volume_level()
	if config.conf["brailleExtender"]["volumeChangeFeedback"] in [CHOICE_braille, CHOICE_speechAndBraille]:
		msg = make_progress_bar_from_str(volume_level, "%3d%%" % volume_level, INSERT_AFTER)
		braille.handler.message(msg)
	if config.conf["brailleExtender"]["volumeChangeFeedback"] in [CHOICE_speech, CHOICE_speechAndBraille]:
		speech.speakMessage(str(volume_level))


def make_progress_bar_from_str(percentage, text, method, positive='⢼', negative='⠤'):
	if len(positive) != 1 or len(negative) != 1:
		raise ValueError("positive and negative must be a string of size 1")
	brl_repr = getTextInBraille(text)
	brl_repr_size = len(brl_repr)
	display_size = braille.handler.displaySize
	if display_size < brl_repr_size + 3:  return brl_repr
	size = display_size if method == REPLACE_TEXT else (display_size - brl_repr_size) % display_size
	progress_bar = ''
	if size - 2 > 0:
		progress_bar = "⣦%s⣴" % ''.join(
			[positive if k <= int(float(percentage) / 100. * float(size - 2)) - 1
			else negative for k in range(size - 2)]
		)
	if method == INSERT_AFTER:
		return brl_repr + progress_bar
	if method == INSERT_BEFORE:
		return progress_bar + brl_repr
	return progress_bar


def getEffectiveInputTableFileName() -> str:
	"""Return the liblouis input table file name (never the config value ``auto``)."""
	if brailleInput.handler is not None:
		return brailleInput.handler.table.fileName
	return _resolveInputTableFileName(config.conf["braille"]["inputTable"])


def bkToChar(dots, inTable=-1):
	table_file = (
		getEffectiveInputTableFileName()
		if inTable == -1
		else _resolveInputTableFileName(inTable)
	)
	char = chr(dots | 0x8000)
	text = louis.backTranslate(
		_liblouisTablePaths(table_file),
		char, mode=louis.dotsIO)
	chars = text[0]
	if len(chars) == 1 and chars.isupper():
		chars = 'shift+' + chars.lower()
	return chars if chars != ' ' else 'space'


def reload_brailledisplay(bd_name):
	try:
		if braille.handler.setDisplayByName(bd_name):
			speech.speakMessage(_("Reload successful"))
			return True
	except RuntimeError: pass
	ui.message(_("Reload failed"))
	return False

def currentCharDesc(
		ch: str='',
		display: bool=True
	) -> str:
	if not ch: ch = getCurrentChar()
	if not ch: return ui.message(_("Not a character"))
	c = ord(ch)
	if c:
		try: char_name = unicodedata.name(ch)
		except ValueError: char_name = _("unknown")
		char_category = unicodedata.category(ch)
		HUC_repr = "%s, %s" % (huc.translate(ch, False), huc.translate(ch, True))
		speech_output = getSpeechSymbols(ch)
		brl_repr = getTextInBraille(ch)
		brl_repr_desc = huc.unicodeBrailleToDescription(brl_repr)
		s = (
			f"{ch}: {hex(c)}, {c}, {oct(c)}, {bin(c)}\n"
			f"{speech_output} ({char_name} [{char_category}])\n"
			f"{brl_repr} ({brl_repr_desc})\n"
			f"{HUC_repr}")
		if not display: return s
		if scriptHandler.getLastScriptRepeatCount() == 0: ui.message(s)
		elif scriptHandler.getLastScriptRepeatCount() == 1:
			ui.browseableMessage(s, (r"U+%.4x (%s) - " % (c, ch)) + _("Char info"))
	else: ui.message(_("Not a character"))

def getCurrentChar():
	info = api.getReviewPosition().copy()
	info.expand(textInfos.UNIT_CHARACTER)
	return info.text

def getTextSelection():
	obj = api.getFocusObject()
	treeInterceptor=obj.treeInterceptor
	if isinstance(treeInterceptor,treeInterceptorHandler.DocumentTreeInterceptor) and not treeInterceptor.passThrough:
		obj=treeInterceptor
	try: info=obj.makeTextInfo(textInfos.POSITION_SELECTION)
	except (RuntimeError, NotImplementedError): info=None
	if not info or info.isCollapsed:
		obj = api.getNavigatorObject()
		text = obj.name
		return "%s" % text if text else ''
	return info.text

def getKeysTranslation(n):
	o = n
	n = n.lower()
	nk = 'NVDA+' if 'nvda+' in n else ''
	if not 'br(' in n:
		n = n.replace('kb:', '').replace('nvda+', '')
		try:
			n = KeyboardInputGesture.fromName(n).displayName
			n = re.sub('([^a-zA-Z]|^)f([0-9])', r'\1F\2', n)
		except BaseException:
			return o
		return nk + n

def getTextInBraille(t=None, table=[]):
	if not isinstance(table, list): raise TypeError("Wrong type for table parameter: %s" % repr(table))
	if not t: t = getTextSelection()
	if not t: return ''
	if not table or "current" in table:
		table = getCurrentBrailleTables()
	else:
		for i, e in enumerate(table):
			if '\\' not in e and '/' not in e:
				table[i] = "%s\\%s" % (brailleTables.TABLES_DIR, e)
	t = t.split("\n")
	res = [louis.translateString(table, l, mode=louis.ucBrl|louis.dotsIO) for l in t if l]
	return '\n'.join(res)

def combinationDesign(dots, noDot="⠤"):
	return "".join(str(n) if str(n) in dots else noDot for n in range(1, 9))


def getTableOverview(tbl=""):
	"""
	Return an overview of an input braille table.
	:param tbl: the braille table to use (default: the current input braille table).
	:type tbl: str
	:return: an overview of braille table in the form of a textual table
	:rtype: str
	"""
	table_name = _resolveInputTableFileName(tbl) if tbl else getEffectiveInputTableFileName()
	table_paths = _liblouisTablePaths(table_name)
	header = "Input              Output\n"
	tmp = {}
	available_chars: list[str] = []
	brl_start = 0x2800
	for i in range(brl_start, brl_start + 256):
		ch = chr(i)
		out_text = louis.backTranslate(table_paths, ch, mode=louis.ucBrl)[0]
		if _RE_OVERVIEW_UNUSED_COMBO.match(out_text):
			available_chars.append(ch)
			continue
		dot_desc = huc.unicodeBrailleToDescription(ch)
		left = "%s (%s)" % (ch, combinationDesign(dot_desc))
		raw = out_text.rstrip("\x00")
		if len(out_text) == 1 and out_text:
			hex_note = " (%-10s)" % hex(ord(out_text))
		elif not out_text:
			hex_note = "#ERROR"
		else:
			hex_note = ""
		right = "%s%-8s" % (raw, hex_note)
		tmp[out_text if out_text else "?"] = "%s       %-7s" % (left, right)
	body = "\n".join(tmp[k] for k in sorted(tmp))
	t = header + body
	nb_available = len(available_chars)
	if nb_available > 1:
		t += "\n" + _("Available combinations") + " (%d): %s" % (nb_available, "".join(available_chars))
	elif nb_available == 1:
		t += "\n" + _("One combination available") + ": %s" % available_chars[0]
	return t

def beautifulSht(t, curBD="noBraille", model=True, sep=" / "):
	if isinstance(t, list): t = ' '.join(t)
	t = t.replace(',', ' ').replace(';', ' ').replace('  ', ' ')
	reps = {
		"b10": "b0",
		"braillespacebar": "space",
		"space": _('space'),
		"leftshiftkey": _("left SHIFT"),
		"rightshiftkey": _("right SHIFT"),
		"leftgdfbutton": _("left selector"),
		"rightgdfbutton": _("right selector"),
		"dot": _("dot")
	}
	mdl = ''
	pattern = r"^.+\.([^)]+)\).+$"
	t = t.replace(';', ',')
	out = []
	for gesture in t.split(' '):
		if not gesture.strip(): continue
		mdl = ''
		if re.match(pattern, gesture): mdl = re.sub(pattern, r'\1', gesture)
		gesture = re.sub(r'.+:', '', gesture)
		gesture = '+'.join(sorted(gesture.split('+')))
		for rep in reps:
			gesture = re.sub(r"(\+|^)%s([0-9]\+|$)" % rep, r"\1%s\2" % reps[rep], gesture)
			gesture = re.sub(r"(\+|^)%s([0-9]\+|$)" % rep, r"\1%s\2" % reps[rep], gesture)
		out.append(_('{gesture} on {brailleDisplay}').format(gesture=gesture, brailleDisplay=mdl) if mdl != '' else gesture)
	return out if not sep else sep.join(out)

def getText():
	obj = api.getFocusObject()
	treeInterceptor = obj.treeInterceptor
	if hasattr(
			treeInterceptor,
			'TextInfo') and not treeInterceptor.passThrough:
		obj = treeInterceptor
	try:
		info = obj.makeTextInfo(textInfos.POSITION_ALL)
		return info.text
	except BaseException:
		pass
	return None


def getTextCarret():
	obj = api.getFocusObject()
	treeInterceptor = obj.treeInterceptor
	if hasattr(treeInterceptor, 'TextInfo') and not treeInterceptor.passThrough: obj = treeInterceptor
	try:
		p1 = obj.makeTextInfo(textInfos.POSITION_ALL)
		p2 = obj.makeTextInfo(textInfos.POSITION_CARET)
		p1.setEndPoint(p2, "endToStart")
		try: return p1.text
		except BaseException: return None
	except BaseException: pass
	return None


def getLine():
	info = api.getReviewPosition().copy()
	info.expand(textInfos.UNIT_LINE)
	return info.text


def getTextPosition():
	try:
		total = len(getText())
		return len(getTextCarret()), total
	except BaseException:
		return 0, 0


def uncapitalize(s): return s[:1].lower() + s[1:] if s else ''


def refreshBD():
	obj = api.getFocusObject()
	if obj.treeInterceptor is not None:
		ti = treeInterceptorHandler.update(obj)
		if not ti.passThrough:
			braille.handler.handleGainFocus(ti)
	else:
		braille.handler.handleGainFocus(api.getFocusObject())

def getSpeechSymbols(text: str | None = None) -> str:
	"""Return speech symbol description for text (or selection). Shows message if no text."""
	if not text: text = getTextSelection()
	if not text: return ui.message(_("No text selected"))
	locale = languageHandler.getLanguage()
	return characterProcessing.processSpeechSymbols(locale, text, get_symbol_level("SYMLVL_CHAR")).strip()

def getTether():
	if hasattr(braille.handler, "getTether"):
		return braille.handler.getTether()
	return braille.handler.tether


def getCharFromValue(s):
	if not isinstance(s, str): raise TypeError("Wrong type")
	if not s or len(s) < 2: raise ValueError("Wrong value")
	supportedBases = {'b': 2, 'd': 10, 'h': 16, 'o': 8, 'x': 16}
	base, n = s[0].lower(), s[1:]
	if base not in supportedBases.keys(): raise ValueError("Wrong base (%s)" % base)
	b = supportedBases[base]
	n = int(n, b)
	return chr(n)


def supportsAutomaticBrailleTables():
	"""Returns True if NVDA supports automatic braille table selection (NVDA 2025.1+)."""
	return NVDA_HAS_AUTOMATIC_BRAILLE_TABLES


def getAutomaticTableDisplayName(*, is_input: bool) -> str:
	"""Get the display string for automatic table, e.g. 'Automatic (en-us-comp8.utb)'."""
	# Translators: An option to select a braille table automatically, according to the current language.
	file_name = default_braille_table_file_for_cur_language(is_input=is_input)
	return _("Automatic ({name})").format(
		name=brailleTables.getTable(file_name).displayName,
	)


def getTranslationTable():
	translationTable = config.conf["braille"]["translationTable"]
	if translationTable == "auto":
		return default_braille_table_file_for_cur_language(is_input=False)
	return translationTable


def getActiveOutputTableForSwitch():
	"""Returns the effective output table identifier for switching: 'auto' or table fileName."""
	tt = config.conf["braille"]["translationTable"]
	if tt == "auto":
		return "auto"
	if supportsAutomaticBrailleTables():
		defaultTable = default_braille_table_file_for_cur_language(is_input=False)
		if braille.handler.table.fileName == defaultTable:
			return "auto"
	return tt


def getActiveInputTableForSwitch():
	"""Returns the effective input table identifier for switching: 'auto' or table fileName."""
	it = config.conf["braille"]["inputTable"]
	if it == "auto":
		return "auto"
	if supportsAutomaticBrailleTables():
		defaultTable = default_braille_table_file_for_cur_language(is_input=True)
		if brailleInput.handler.table.fileName == defaultTable:
			return "auto"
	return brailleInput.handler.table.fileName


def getCurrentBrailleTables(input_=False, brf=False):
	from . import tabledictionaries
	if brf:
		tables = [
			os.path.join(baseDir, "res", "brf.ctb").encode("UTF-8"),
			os.path.join(brailleTables.TABLES_DIR, "braille-patterns.cti")
		]
	else:
		tables = []
		try:
			app = appModuleHandler.getAppModuleForNVDAObject(api.getNavigatorObject())
		except OSError:
			app = None
		if app and app.appName != "nvda": tables += tabledictionaries.dictTables
		if input_:
			tfile = brailleInput.handler._table.fileName
		else:
			tfile = getTranslationTable()
		tables += _liblouisTablePaths(tfile)
	return tables


def get_output_reason(reason_name):
	old_attr = "REASON_%s" % reason_name
	if hasattr(controlTypes, "OutputReason") and hasattr(controlTypes.OutputReason, reason_name):
		return getattr(controlTypes.OutputReason, reason_name)
	elif hasattr(controlTypes, old_attr):
		return getattr(controlTypes, old_attr)
	else:
		raise AttributeError("Reason \"%s\" unknown" % reason_name)


def is_braille_unicode_normalization_enabled() -> bool:
	"""Whether NVDA's braille Unicode normalization feature is active (2025.2+ / 2026.x).

	When True, Region.update normalizes text before liblouis translation and remaps offsets.
	"""
	try:
		value = config.conf["braille"]["unicodeNormalization"]
	except (KeyError, LookupError, AttributeError, TypeError):
		return False
	if hasattr(value, "calculated"):
		try:
			return bool(value.calculated())
		except Exception:
			return bool(value)
	return bool(value)


def get_speech_mode():
	if hasattr(speech, "getState"):
		return speech.getState().speechMode
	return speech.speechMode


def is_speechMode_talk() -> bool:
	speechMode = get_speech_mode()
	if hasattr(speech, "SpeechMode"):
		return speechMode == speech.SpeechMode.talk
	return speechMode == speech.speechMode_talk


def set_speech_off():
	if hasattr(speech, "SpeechMode"):
		return speech.setSpeechMode(speech.SpeechMode.off)
	speech.speechMode = speech.speechMode_off


def set_speech_talk():
	if hasattr(speech, "SpeechMode"):
		return speech.setSpeechMode(speech.SpeechMode.talk)
	speech.speechMode = speech.speechMode_talk

newControlTypes = hasattr(controlTypes, "Role")
def get_control_type(control_type):
	if not isinstance(control_type, str):
		raise TypeError()
	if newControlTypes:
		attr = '_'.join(control_type.split('_')[1:])
		if control_type.startswith("ROLE_"):
			return getattr(controlTypes.Role, attr)
		elif control_type.startswith("STATE_"):
			return getattr(controlTypes.State, attr)
		else:
			raise ValueError(control_type)
	return getattr(controlTypes, control_type)

newSymbolLevel = hasattr(characterProcessing, "SymbolLevel")
def get_symbol_level(symbol_level):
	if not isinstance(symbol_level, str):
		raise TypeError()
	if newSymbolLevel:
		return getattr(characterProcessing.SymbolLevel, '_'.join(symbol_level.split('_')[1:]))
	return getattr(characterProcessing, symbol_level)
