# coding: utf-8
# undefinedchars.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush CLAUSE, released under GPL.

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

import addonHandler
import characterProcessing
import config
import gui
import languageHandler
import louis
import wx
from logHandler import log

from . import addoncfg
from . import huc
from . import regionhelper
from .utils import getCurrentBrailleTables, getTextInBraille, get_symbol_level

addonHandler.initTranslation()


HUCDotPattern = "12345678-78-12345678"
undefinedCharPattern = huc.cellDescriptionsToUnicodeBraille(HUCDotPattern)
CHOICE_tableBehaviour = 0
CHOICE_allDots8 = 1
CHOICE_allDots6 = 2
CHOICE_emptyCell = 3
CHOICE_otherDots = 4
CHOICE_questionMark = 5
CHOICE_otherSign = 6
CHOICE_liblouis = 7
CHOICE_HUC8 = 8
CHOICE_HUC6 = 9
CHOICE_hex = 10
CHOICE_dec = 11
CHOICE_oct = 12
CHOICE_bin = 13

dotPatternSample = "6-123456"
signPatternSample = "??"

CHOICES_LABELS = {
	CHOICE_tableBehaviour: _("Use braille table behavior (no description possible)"),
	CHOICE_allDots8: _("Dots 1-8 (⣿)"),
	CHOICE_allDots6: _("Dots 1-6 (⠿)"),
	CHOICE_emptyCell: _("Empty cell (⠀)"),
	CHOICE_otherDots: _("Other dot pattern (e.g.: {dotPatternSample})").format(
		dotPatternSample=dotPatternSample
	),
	CHOICE_questionMark: _("Question mark (depending on output table)"),
	CHOICE_otherSign: _("Other sign/pattern (e.g.: {signPatternSample})").format(
		signPatternSample=signPatternSample
	),
	CHOICE_liblouis: _("Hexadecimal, Liblouis style"),
	CHOICE_HUC8: _("Hexadecimal, HUC8"),
	CHOICE_HUC6: _("Hexadecimal, HUC6"),
	CHOICE_hex: _("Hexadecimal"),
	CHOICE_dec: _("Decimal"),
	CHOICE_oct: _("Octal"),
	CHOICE_bin: _("Binary"),
}

def getHardValue() -> str:
	"""Return the dot or sign pattern value for CHOICE_otherDots or CHOICE_otherSign."""
	selected = config.conf["brailleExtender"]["undefinedCharsRepr"]["method"]
	if selected == CHOICE_otherDots:
		return config.conf["brailleExtender"]["undefinedCharsRepr"]["hardDotPatternValue"]
	if selected == CHOICE_otherSign:
		return config.conf["brailleExtender"]["undefinedCharsRepr"]["hardSignPatternValue"]
	return ''


_descCharCache = {}
_undefinedSignCache = {}
_brailledTagCache = {}


def _clearCaches() -> None:
	"""Invalidate all undefined-char caches. Call when settings change."""
	global _descCharCache, _undefinedSignCache, _brailledTagCache
	_descCharCache.clear()
	_undefinedSignCache.clear()
	_brailledTagCache.clear()


def setUndefinedChar(t: Optional[int] = None) -> None:
	"""Compile liblouis undefined-char rule for the current method."""
	if not t or t > CHOICE_HUC6 or t < 0:
		t = config.conf["brailleExtender"]["undefinedCharsRepr"]["method"]
	if t == 0:
		return
	_clearCaches()
	louis.compileString(getCurrentBrailleTables(), bytes(
		f"undefined {HUCDotPattern}", "ASCII"))


def getExtendedSymbolsForString(s: str, lang: str) -> dict[str, tuple[str, list[tuple[int, int]]]]:
	"""Return symbols from rawText with their descriptions and positions."""
	global extendedSymbols, localesFail
	if lang in localesFail:
		lang = "en"
	if lang not in extendedSymbols:
		try:
			extendedSymbols[lang] = getExtendedSymbols(lang)
		except LookupError:
			log.warning("Unable to load extended symbols for: %s, using english", lang)
			localesFail.append(lang)
			lang = "en"
			extendedSymbols[lang] = getExtendedSymbols(lang)
	symbols = extendedSymbols[lang]
	return {
		c: (d, [(m.start(), m.end() - 1) for m in re.finditer(re.escape(c), s)])
		for c, d in symbols.items()
		if c in s
	}


def getAlternativeDescChar(c: str, method: int) -> str:
	"""Return braille representation when characterProcessing has no description."""
	if method in [CHOICE_HUC6, CHOICE_HUC8]:
		HUC6 = method == CHOICE_HUC6
		return huc.translate(c, HUC6=HUC6)
	if method in [CHOICE_bin, CHOICE_oct, CHOICE_dec, CHOICE_hex]:
		return getTextInBraille("".join(getUnicodeNotation(c)))
	if method == CHOICE_liblouis:
		return getTextInBraille(getLiblouisStyle(c))
	return getUndefinedCharSign(method)


_DESC_CACHE_MAX = 512


def _getDescCharCore(c: str, lang: str, method: int) -> str:
	"""Return description only (no tags). Cached for performance."""
	key = (c, lang, method)
	if key in _descCharCache:
		return _descCharCache[key]
	level = get_symbol_level("SYMLVL_CHAR")
	desc = characterProcessing.processSpeechSymbols(lang, c, level).strip()
	if not desc or desc == c:
		if hasattr(characterProcessing, "SymbolLevel"):
			allLevel = characterProcessing.SymbolLevel.ALL
			if level != allLevel:
				desc = characterProcessing.processSpeechSymbols(lang, c, allLevel).strip()
		if (not desc or desc == c) and len(c) == 1:
			try:
				desc = unicodedata.name(c)
			except ValueError:
				pass
		if not desc or desc == c:
			desc = getAlternativeDescChar(c, method)
	if len(_descCharCache) >= _DESC_CACHE_MAX:
		_descCharCache.pop(next(iter(_descCharCache)))
	_descCharCache[key] = desc
	return desc


def getDescChar(
	c: str,
	lang: str = "Windows",
	start: str = "",
	end: str = "",
) -> str:
	"""Return character description with optional braille tags. Uses NVDA symbol/CLDR when available."""
	method = config.conf["brailleExtender"]["undefinedCharsRepr"]["method"]
	if lang == "Windows":
		lang = languageHandler.getLanguage()
	desc = _getDescCharCore(c, lang, method)
	return f"{start}{desc}{end}"


def getLiblouisStyle(c: str | int) -> str:
	"""Return Liblouis hex style (e.g. \\x1234) for a character or codepoint."""
	if isinstance(c, str):
		if not c:
			raise ValueError("Empty string received")
		if len(c) > 1:
			return " ".join(getLiblouisStyle(ch) for ch in c)
		c = ord(c)
	if not isinstance(c, int):
		raise TypeError("wrong type")
	if c < 0x10000:
		return r"\x%.4x" % c
	if c <= 0x100000:
		return r"\y%.5x" % c
	return r"\z%.6x" % c


def getUnicodeNotation(s: str, notation: Optional[int] = None) -> str:
	"""Return braille representation of Unicode notation (hex, dec, oct, bin, liblouis)."""
	if not isinstance(s, str):
		raise TypeError("wrong type")
	if not notation:
		notation = config.conf["brailleExtender"]["undefinedCharsRepr"]["method"]
	matches = {
		CHOICE_bin: bin,
		CHOICE_oct: oct,
		CHOICE_dec: lambda s: s,
		CHOICE_hex: hex,
		CHOICE_liblouis: getLiblouisStyle,
	}
	if notation not in matches.keys():
		raise ValueError(f"Wrong value ({notation})")
	fn = matches[notation]
	return getTextInBraille("".join(["'%s'" % fn(ord(c)) for c in s]))


def getUndefinedCharSign(method: int) -> str:
	"""Return braille cell(s) for the undefined-character representation method."""
	cached = _undefinedSignCache.get(method)
	if cached is not None:
		return cached
	if method == CHOICE_allDots8:
		r = '⣿'
	elif method == CHOICE_allDots6:
		r = '⠿'
	elif method == CHOICE_otherDots:
		r = huc.cellDescriptionsToUnicodeBraille(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["hardDotPatternValue"])
	elif method == CHOICE_questionMark:
		r = getTextInBraille('?')
	elif method == CHOICE_otherSign:
		r = getTextInBraille(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["hardSignPatternValue"])
	else:
		r = '⠀'
	_undefinedSignCache[method] = r
	return r


def getReplacement(
	text: str,
	method: Optional[int] = None,
	startTag: Optional[str] = None,
	endTag: Optional[str] = None,
	lang: Optional[str] = None,
	table: Optional[list[str]] = None,
) -> str:
	"""Return braille representation for an undefined character or text span."""
	if not method:
		method = config.conf["brailleExtender"]["undefinedCharsRepr"]["method"]
	if not text:
		return ''
	cfg = config.conf["brailleExtender"]["undefinedCharsRepr"]
	if cfg["desc"]:
		if startTag is None:
			st, et = cfg["start"], cfg["end"]
			startTag = getTextInBraille(st) if st else ""
			endTag = getTextInBraille(et) if et else ""
		if lang is None:
			lang = cfg["lang"] if cfg["lang"] != "Windows" else languageHandler.getLanguage()
		if table is None:
			table = [cfg["table"]]
		return getTextInBraille(getDescChar(
			text, lang=lang, start=startTag, end=endTag
		), table)
	if method in [CHOICE_HUC6, CHOICE_HUC8]:
		HUC6 = method == CHOICE_HUC6
		return huc.translate(text, HUC6=HUC6)
	if method in [CHOICE_bin, CHOICE_oct, CHOICE_dec, CHOICE_hex, CHOICE_liblouis]:
		return getUnicodeNotation(text)
	return getUndefinedCharSign(method)


def undefinedCharProcess(self: Any) -> None:
	"""Replace undefined braille cells with configured representation (HUC, desc, etc.)."""
	cfg = config.conf["brailleExtender"]["undefinedCharsRepr"]
	undefinedCharsPos = list(regionhelper.findBrailleCellsPattern(
		self, undefinedCharPattern))
	if not undefinedCharsPos:
		return
	undefinedCharsPosSet = set(undefinedCharsPos)
	Repl = regionhelper.BrailleCellReplacement
	fullExtendedDesc = cfg["fullExtendedDesc"]
	showSize = cfg["showSize"]
	lang = cfg["lang"] if cfg["lang"] != "Windows" else languageHandler.getLanguage()
	table = [cfg["table"]]
	startTag = endTag = ""
	if cfg["desc"] or cfg["extendedDesc"]:
		startTagRaw, endTagRaw = cfg["start"], cfg["end"]
		tagKey = (startTagRaw, endTagRaw, cfg["table"])
		try:
			startTag, endTag = _brailledTagCache[tagKey]
		except KeyError:
			startTag = getTextInBraille(startTagRaw) if startTagRaw else ""
			endTag = getTextInBraille(endTagRaw) if endTagRaw else ""
			_brailledTagCache[tagKey] = (startTag, endTag)
			if len(_brailledTagCache) > 32:
				_brailledTagCache.pop(next(iter(_brailledTagCache)))
	replacements = []
	method = cfg["method"]
	getReplKw = {"method": method}
	if cfg["desc"]:
		getReplKw["startTag"] = startTag
		getReplKw["endTag"] = endTag
		getReplKw["lang"] = lang
		getReplKw["table"] = table
	for pos in undefinedCharsPos:
		replacements.append(Repl(pos, replaceBy=getReplacement(
			self.rawText[pos], **getReplKw)))
	if cfg["desc"] and cfg["extendedDesc"]:
		extendedSymbolsRawText = getExtendedSymbolsForString(self.rawText, lang)
		for c, v in extendedSymbolsRawText.items():
			desc, positions = v[0], v[1]
			toAdd = f":{len(c)}" if showSize and len(c) > 1 else ''
			replaceByBraille = getTextInBraille(
				f"{startTag}{desc}{toAdd}{endTag}", table)
			for start, end in positions:
				if start in undefinedCharsPosSet:
					replacements.append(Repl(
						start,
						start if fullExtendedDesc else end,
						replaceBy=getReplacement(c[0], **getReplKw) if fullExtendedDesc else replaceByBraille,
						insertBefore=replaceByBraille if fullExtendedDesc else ''
					))
	regionhelper.replaceBrailleCells(self, replacements)


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	"""Settings panel for undefined character representation options."""

	# Translators: title of a dialog.
	title = _("Undefined character representation")

	def makeSettings(self, settingsSizer: wx.Sizer) -> None:
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: label of a dialog.
		label = _("Representation &method:")
		self.undefinedCharReprList = sHelper.addLabeledControl(
			label, wx.Choice, choices=list(CHOICES_LABELS.values())
		)
		self.undefinedCharReprList.SetSelection(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["method"]
		)
		self.undefinedCharReprList.Bind(
			wx.EVT_CHOICE, self.onUndefinedCharReprList)
		# Translators: label of a dialog.
		self.undefinedCharReprEdit = sHelper.addLabeledControl(
			_("Specify another &pattern"), wx.TextCtrl, value=self.getHardValue()
		)
		self.undefinedCharDesc = sHelper.addItem(
			wx.CheckBox(self, label=(
				_("Show punctuation/symbol &name for undefined characters if available (can cause a lag)")
			))
		)
		self.undefinedCharDesc.SetValue(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"]
		)
		self.undefinedCharDesc.Bind(wx.EVT_CHECKBOX, self.onUndefinedCharDesc)
		self.extendedDesc = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("Also describe e&xtended characters (e.g.: country flags)")
			)
		)
		self.extendedDesc.SetValue(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["extendedDesc"]
		)
		self.extendedDesc.Bind(wx.EVT_CHECKBOX, self.onExtendedDesc)
		self.fullExtendedDesc = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("&Full extended description")
			)
		)
		self.fullExtendedDesc.SetValue(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["fullExtendedDesc"]
		)
		self.showSize = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("Show the si&ze taken")
			)
		)
		self.showSize.SetValue(
			config.conf["brailleExtender"]["undefinedCharsRepr"]["showSize"]
		)
		self.startTag = sHelper.addLabeledControl(
			_("&Start tag:"),
			wx.TextCtrl,
			value=config.conf["brailleExtender"]["undefinedCharsRepr"]["start"],
		)
		self.endTag = sHelper.addLabeledControl(
			_("&End tag:"),
			wx.TextCtrl,
			value=config.conf["brailleExtender"]["undefinedCharsRepr"]["end"],
		)
		availableLangs = languageHandler.getAvailableLanguages()
		self._langValues = [lang[1] for lang in availableLangs]
		self._langKeys = [lang[0] for lang in availableLangs]
		undefinedCharLang = config.conf["brailleExtender"]["undefinedCharsRepr"]["lang"]
		if undefinedCharLang not in self._langKeys:
			undefinedCharLang = keys[-1]
		undefinedCharLangID = self._langKeys.index(undefinedCharLang)
		self.undefinedCharLang = sHelper.addLabeledControl(
			_("&Language:"), wx.Choice, choices=self._langValues
		)
		self.undefinedCharLang.SetSelection(undefinedCharLangID)
		values = [_("Use the current output table")] + [
			table.displayName for table in addoncfg.tables if table.output
		]
		keys = ["current"] + [
			table.fileName for table in addoncfg.tables if table.output
		]
		undefinedCharTable = config.conf["brailleExtender"]["undefinedCharsRepr"][
			"table"
		]
		if undefinedCharTable not in addoncfg.tablesFN + ["current"]:
			undefinedCharTable = "current"
		undefinedCharTableID = keys.index(undefinedCharTable)
		self.undefinedCharTable = sHelper.addLabeledControl(
			_("Braille &table:"), wx.Choice, choices=values
		)
		self.undefinedCharTable.SetSelection(undefinedCharTableID)

		# Translators: label of a dialog.
		label = _("Character limit at which descriptions are disabled (to avoid freezes, >):")
		self.characterLimit = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000000,
			initial=config.conf["brailleExtender"]["undefinedCharsRepr"]["characterLimit"]
		)

		self.onExtendedDesc()
		self.onUndefinedCharDesc()
		self.onUndefinedCharReprList()

	def getHardValue(self) -> str:
		"""Return current dot/sign pattern for the pattern editor."""
		selected = self.undefinedCharReprList.GetSelection()
		if selected == CHOICE_otherDots:
			return config.conf["brailleExtender"]["undefinedCharsRepr"][
				"hardDotPatternValue"
			]
		if selected == CHOICE_otherSign:
			return config.conf["brailleExtender"]["undefinedCharsRepr"][
				"hardSignPatternValue"
			]
		return ""

	def onUndefinedCharDesc(self, evt: Optional[wx.CommandEvent] = None, forceDisable: bool = False) -> None:
		l = [
			self.extendedDesc,
			self.fullExtendedDesc,
			self.showSize,
			self.startTag,
			self.endTag,
			self.undefinedCharLang,
			self.undefinedCharTable,
		]
		for e in l:
			if self.undefinedCharDesc.IsChecked() and not forceDisable:
				e.Enable()
			else:
				e.Disable()

	def onExtendedDesc(self, evt: Optional[wx.CommandEvent] = None) -> None:
		if self.extendedDesc.IsChecked():
			self.fullExtendedDesc.Enable()
			self.showSize.Enable()
		else:
			self.fullExtendedDesc.Disable()
			self.showSize.Disable()

	def onUndefinedCharReprList(self, evt: Optional[wx.CommandEvent] = None) -> None:
		selected = self.undefinedCharReprList.GetSelection()
		if selected == CHOICE_tableBehaviour:
			self.undefinedCharDesc.Disable()
			self.onUndefinedCharDesc(forceDisable=True)
		else:
			self.undefinedCharDesc.Enable()
			self.onUndefinedCharDesc()
		if selected in [CHOICE_otherDots, CHOICE_otherSign]:
			self.undefinedCharReprEdit.Enable()
		else:
			self.undefinedCharReprEdit.Disable()
		self.undefinedCharReprEdit.SetValue(self.getHardValue())

	def postInit(self) -> None:
		self.undefinedCharDesc.SetFocus()

	def onSave(self) -> None:
		_clearCaches()
		config.conf["brailleExtender"]["undefinedCharsRepr"][
			"method"
		] = self.undefinedCharReprList.GetSelection()
		repr_ = self.undefinedCharReprEdit.Value
		if self.undefinedCharReprList.GetSelection() == CHOICE_otherDots:
			repr_ = re.sub(r"[^0-8\-]", "", repr_).strip("-")
			repr_ = re.sub(r"\-+", "-", repr_)
			config.conf["brailleExtender"]["undefinedCharsRepr"][
				"hardDotPatternValue"
			] = repr_
		else:
			config.conf["brailleExtender"]["undefinedCharsRepr"][
				"hardSignPatternValue"
			] = repr_
		config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"] = self.undefinedCharDesc.IsChecked()
		config.conf["brailleExtender"]["undefinedCharsRepr"]["extendedDesc"] = self.extendedDesc.IsChecked()
		config.conf["brailleExtender"]["undefinedCharsRepr"]["fullExtendedDesc"] = self.fullExtendedDesc.IsChecked()
		config.conf["brailleExtender"]["undefinedCharsRepr"]["showSize"] = self.showSize.IsChecked()
		config.conf["brailleExtender"]["undefinedCharsRepr"][
			"start"
		] = self.startTag.Value
		config.conf["brailleExtender"]["undefinedCharsRepr"][
			"end"
		] = self.endTag.Value
		config.conf["brailleExtender"]["undefinedCharsRepr"]["lang"] = self._langKeys[
			self.undefinedCharLang.GetSelection()
		]
		undefinedCharTable = self.undefinedCharTable.GetSelection()
		keys = ["current"] + [
			table.fileName for table in addoncfg.tables if table.output
		]
		config.conf["brailleExtender"]["undefinedCharsRepr"]["table"] = keys[
			undefinedCharTable
		]
		config.conf["brailleExtender"]["undefinedCharsRepr"]["characterLimit"] = self.characterLimit.Value


def _shouldIncludeExtendedSymbol(k: str, v: Any) -> bool:
	"""Return True for multi-char symbols (e.g. flags) or single-char emoji (U+1F300+)."""
	if not k or not v or not getattr(v, 'replacement', None):
		return False
	try:
		rep = v.replacement.replace('\u202f', '').strip()
	except (AttributeError, TypeError):
		return False
	if not rep:
		return False
	if ' ' in k:
		return False
	if len(k) > 1:
		return True
	return len(k) == 1 and ord(k[0]) >= 0x1F300


def getExtendedSymbols(locale: str) -> dict[str, str]:
	"""Load extended symbol descriptions (emoji, flags) from NVDA characterProcessing."""
	if locale == "Windows":
		locale = languageHandler.getLanguage()
	try:
		symbolsForLocale = characterProcessing._getSpeechSymbolsForLocale(locale)
	except LookupError:
		if '_' in locale:
			return getExtendedSymbols(locale.split('_')[0])
		raise
	except Exception:
		log.debugWarning("Failed to load extended symbols for %s", locale, exc_info=True)
		return {}
	a = {}
	for source in symbolsForLocale:
		try:
			symbols = getattr(source, 'symbols', {})
			for k, v in symbols.items():
				if _shouldIncludeExtendedSymbol(k, v):
					rep = v.replacement.replace('\u202f', '').strip()
					a[k.strip()] = rep
		except (AttributeError, TypeError):
			continue
	return a


extendedSymbols = {}
localesFail = []
