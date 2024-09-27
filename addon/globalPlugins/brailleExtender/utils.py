# coding: utf-8
# utils.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2021 André-Abush CLAUSE, released under GPL.

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
from .addoncfg import CHOICE_braille, CHOICE_speech, CHOICE_speechAndBraille
from .common import INSERT_AFTER, INSERT_BEFORE, REPLACE_TEXT, baseDir
from . import huc
from . import tabledictionaries
from . import tablegroups
from . import volumehelper
from logHandler import log

get_mute = volumehelper.get_mute
get_volume_level = volumehelper.get_volume_level


def report_volume_level():
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


def bkToChar(dots, inTable=-1):
	if inTable == -1: inTable = config.conf["braille"]["inputTable"]
	char = chr(dots | 0x8000)
	text = louis.backTranslate(
		[os.path.join(r"louis\tables", inTable),
		 "braille-patterns.cti"],
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

def combinationDesign(dots, noDot = '⠤'):
	out = ""
	i = 1
	while i < 9:
		out += str(i) if str(i) in dots else noDot
		i += 1
	return out

def getTableOverview(tbl = ''):
	"""
	Return an overview of a input braille table.
	:param tbl: the braille table to use (default: the current input braille table).
	:type tbl: str
	:return: an overview of braille table in the form of a textual table
	:rtype: str
	"""
	t = ""
	tmp = {}
	available = ""
	i = 0x2800
	while i<0x2800+256:
		text = louis.backTranslate([os.path.join(r"louis\tables", config.conf["braille"]["inputTable"]), "braille-patterns.cti"], chr(i), mode=louis.ucBrl)
		if i != 0x2800:
			t = 'Input              Output\n'
		if not re.match(r'^\\.+/$', text[0]):
			tmp['%s' % text[0] if text[0] != '' else '?'] = '%s       %-7s' % (
			'%s (%s)' % (chr(i), combinationDesign(huc.unicodeBrailleToDescription(chr(i)))),
			'%s%-8s' % (text[0].rstrip('\x00'), '%s' % (' (%-10s)' % str(hex(ord(text[0]))) if len(text[0]) == 1 else '' if text[0] != '' else '#ERROR'))
			)
		else:
			available += chr(i)
		i += 1
	t += '\n'.join(tmp[k] for k in sorted(tmp))
	nbAvailable = len(available)
	if nbAvailable>1:
		t += '\n'+_("Available combinations")+" (%d): %s" % (nbAvailable, available)
	elif nbAvailable == 1:
		t += '\n'+_("One combination available")+": %s" % available
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

def getSpeechSymbols(text = None):
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

def getCurrentBrailleTables(input_=False, brf=False):
	tables = []
	if brf:
		tables.append(
			os.path.join(baseDir, "res", "brf.ctb").encode("UTF-8")
		)
	else:
		app = appModuleHandler.getAppModuleForNVDAObject(api.getNavigatorObject())
		if app and app.appName != "nvda": tables += tabledictionaries.dictTables
		if input_:
			groupTable = tablegroups._currentGroup[0]
			if groupTable:
				tables.extend(groupTable.get_tables())
			else:
				tables.append(
					os.path.join(brailleTables.TABLES_DIR, brailleInput.handler._table.fileName)
				)
		else:
			groupTable = tablegroups._currentGroup[1]
			if groupTable:
				tables.extend(groupTable.get_tables())
			else:
				tables.append(
					os.path.join(brailleTables.TABLES_DIR, config.conf["braille"]["translationTable"])
				)
	tables.append(
		os.path.join(brailleTables.TABLES_DIR, "braille-patterns.cti")
	)
	return tables


def get_output_reason(reason_name):
	old_attr = "REASON_%s" % reason_name
	if hasattr(controlTypes, "OutputReason") and hasattr(controlTypes.OutputReason, reason_name):
		return getattr(controlTypes.OutputReason, reason_name)
	elif hasattr(controlTypes, old_attr):
		return getattr(controlTypes, old_attr)
	else:
		raise AttributeError("Reason \"%s\" unknown" % reason_name)


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
