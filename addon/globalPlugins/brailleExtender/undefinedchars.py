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

def _getUndefinedCharsCfg():
	return config.conf["brailleExtender"]["undefinedCharsRepr"]


def getHardValue() -> str:
	selected = _getUndefinedCharsCfg()["method"]
	if selected == CHOICE_otherDots:
		return _getUndefinedCharsCfg()["hardDotPatternValue"]
	if selected == CHOICE_otherSign:
		return _getUndefinedCharsCfg()["hardSignPatternValue"]
	return ''


_descCharCache = {}
_undefinedSignCache = {}
_brailledTagCache = {}
_excludeDescSet: frozenset[int] = frozenset()
_excludeDescRanges: tuple[tuple[int, int], ...] = ()
_excludeDescConfigValue = ""


def _parseCodepoint(s: str) -> int:
	s = s.strip().lower()
	if s.startswith("x"):
		return int(s[1:] or "0", 16)
	if s.startswith("d"):
		return int(s[1:] or "0", 10)
	return int(s, 10)


def _parseExcludeDesc(s: str) -> tuple[frozenset[int], tuple[tuple[int, int], ...]]:
	"""Parse exclude config into (codepoint_set, range_tuples) for O(1) single-char and O(k) range lookups."""
	if not s or not s.strip():
		return (frozenset(), ())
	single: set[int] = set()
	ranges: list[tuple[int, int]] = []
	for part in s.split(","):
		part = part.strip()
		if not part:
			continue
		try:
			if "-" in part:
				a, b = part.split("-", 1)
				start = _parseCodepoint(a.strip())
				end = _parseCodepoint(b.strip())
				if start <= end and 0 <= start <= 0x10FFFF and 0 <= end <= 0x10FFFF:
					ranges.append((start, end))
			elif len(part) > 1 and part.strip().lower()[0] in ("x", "d"):
				cp = _parseCodepoint(part)
				if 0 <= cp <= 0x10FFFF:
					single.add(cp)
			else:
				for ch in part:
					cp = ord(ch)
					if 0 <= cp <= 0x10FFFF:
						single.add(cp)
		except (ValueError, TypeError):
			log.debugWarning("Invalid exclude range: %r", part)
	return (frozenset(single), tuple(ranges))


def _getExcludeDesc() -> tuple[frozenset[int], tuple[tuple[int, int], ...]]:
	global _excludeDescSet, _excludeDescRanges, _excludeDescConfigValue
	val = _getUndefinedCharsCfg().get("excludeDescChars", "") or ""
	if val != _excludeDescConfigValue:
		_excludeDescConfigValue = val
		_excludeDescSet, _excludeDescRanges = _parseExcludeDesc(val)
	return _excludeDescSet, _excludeDescRanges


def _isCharExcludedFromDesc(c: str) -> bool:
	if len(c) != 1:
		return False
	excluded_set, excluded_ranges = _getExcludeDesc()
	if not excluded_set and not excluded_ranges:
		return False
	cp = ord(c)
	return cp in excluded_set or any(s <= cp <= e for s, e in excluded_ranges)


def _clearCaches() -> None:
	global _descCharCache, _undefinedSignCache, _brailledTagCache, _excludeDescConfigValue
	_descCharCache.clear()
	_undefinedSignCache.clear()
	_brailledTagCache.clear()
	_excludeDescConfigValue = ""


def setUndefinedChar(t: Optional[int] = None) -> None:
	if not t or t > CHOICE_HUC6 or t < 0:
		t = _getUndefinedCharsCfg()["method"]
	if t == 0:
		return
	_clearCaches()
	louis.compileString(getCurrentBrailleTables(), bytes(
		f"undefined {HUCDotPattern}", "ASCII"))


def getExtendedSymbolsForString(s: str, lang: str) -> dict[str, tuple[str, list[tuple[int, int]]]]:
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
	if method in (CHOICE_HUC6, CHOICE_HUC8):
		HUC6 = method == CHOICE_HUC6
		return huc.translate(c, HUC6=HUC6)
	if method in (CHOICE_bin, CHOICE_oct, CHOICE_dec, CHOICE_hex):
		return getTextInBraille("".join(getUnicodeNotation(c)))
	if method == CHOICE_liblouis:
		return getTextInBraille(getLiblouisStyle(c))
	return getUndefinedCharSign(method)


_DESC_CACHE_MAX = 512


def _getDescCharCore(c: str, lang: str, method: int) -> tuple[str, bool]:
	"""Return (text, use_tags). use_tags=False when using alternative repr (no prefix/suffix)."""
	key = (c, lang, method)
	if key in _descCharCache:
		return _descCharCache[key]
	if _isCharExcludedFromDesc(c):
		desc = getAlternativeDescChar(c, method)
		result = (desc, False)
		if len(_descCharCache) >= _DESC_CACHE_MAX:
			_descCharCache.pop(next(iter(_descCharCache)))
		_descCharCache[key] = result
		return result
	level = get_symbol_level("SYMLVL_CHAR")
	desc = characterProcessing.processSpeechSymbols(lang, c, level).strip()
	use_tags = bool(desc and desc != c)
	if not desc or desc == c:
		if hasattr(characterProcessing, "SymbolLevel"):
			allLevel = characterProcessing.SymbolLevel.ALL
			if level != allLevel:
				desc = characterProcessing.processSpeechSymbols(lang, c, allLevel).strip()
				use_tags = bool(desc and desc != c)
		if (not desc or desc == c) and len(c) == 1:
			if _getUndefinedCharsCfg().get("unicodeDataDescLastResort", False):
				try:
					desc = unicodedata.name(c)
					use_tags = True
				except ValueError:
					pass
		if not desc or desc == c:
			desc = getAlternativeDescChar(c, method)
			use_tags = False
	result = (desc, use_tags)
	if len(_descCharCache) >= _DESC_CACHE_MAX:
		_descCharCache.pop(next(iter(_descCharCache)))
	_descCharCache[key] = result
	return result


def getDescChar(c: str, lang: str = "Windows", start: str = "", end: str = "") -> str:
	method = _getUndefinedCharsCfg()["method"]
	if lang == "Windows":
		lang = languageHandler.getLanguage()
	desc, use_tags = _getDescCharCore(c, lang, method)
	return f"{start}{desc}{end}" if use_tags else desc


def getLiblouisStyle(c: str | int) -> str:
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
	if not isinstance(s, str):
		raise TypeError("wrong type")
	if not notation:
		notation = _getUndefinedCharsCfg()["method"]
	matches = {
		CHOICE_bin: bin,
		CHOICE_oct: oct,
		CHOICE_dec: lambda s: s,
		CHOICE_hex: hex,
		CHOICE_liblouis: getLiblouisStyle,
	}
	if notation not in matches:
		raise ValueError(f"Wrong value ({notation})")
	fn = matches[notation]
	return getTextInBraille("".join(["'%s'" % fn(ord(c)) for c in s]))


def getUndefinedCharSign(method: int) -> str:
	cached = _undefinedSignCache.get(method)
	if cached is not None:
		return cached
	if method == CHOICE_allDots8:
		r = '⣿'
	elif method == CHOICE_allDots6:
		r = '⠿'
	elif method == CHOICE_otherDots:
		r = huc.cellDescriptionsToUnicodeBraille(
			_getUndefinedCharsCfg()["hardDotPatternValue"])
	elif method == CHOICE_questionMark:
		r = getTextInBraille('?')
	elif method == CHOICE_otherSign:
		r = getTextInBraille(_getUndefinedCharsCfg()["hardSignPatternValue"])
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
	if not method:
		method = _getUndefinedCharsCfg()["method"]
	if not text:
		return ''
	cfg = _getUndefinedCharsCfg()
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
	if method in (CHOICE_HUC6, CHOICE_HUC8):
		HUC6 = method == CHOICE_HUC6
		return huc.translate(text, HUC6=HUC6)
	if method in (CHOICE_bin, CHOICE_oct, CHOICE_dec, CHOICE_hex, CHOICE_liblouis):
		return getUnicodeNotation(text)
	return getUndefinedCharSign(method)


def undefinedCharProcess(self: Any) -> None:
	cfg = _getUndefinedCharsCfg()
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
		excluded_set, excluded_ranges = _getExcludeDesc()
		for c, v in extendedSymbolsRawText.items():
			desc, positions = v[0], v[1]
			excluded = any(
				ord(ch) in excluded_set or any(s <= ord(ch) <= e for s, e in excluded_ranges)
				for ch in c
			)
			if excluded:
				replaceByBraille = getReplacement(c[0], **getReplKw)
			else:
				toAdd = f":{len(c)}" if showSize and len(c) > 1 else ''
				replaceByBraille = getTextInBraille(
					f"{startTag}{desc}{toAdd}{endTag}", table)
			replForFullDesc = replaceByBraille if (fullExtendedDesc and excluded) else (
				getReplacement(c[0], **getReplKw) if fullExtendedDesc else None
			)
			for start, end in positions:
				if start in undefinedCharsPosSet:
					replacements.append(Repl(
						start,
						start if fullExtendedDesc else end,
						replaceBy=replForFullDesc if fullExtendedDesc else replaceByBraille,
						insertBefore=replaceByBraille if fullExtendedDesc else ''
					))
	regionhelper.replaceBrailleCells(self, replacements)


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of dialog
	title = _("Undefined character representation")

	def makeSettings(self, settingsSizer: wx.Sizer) -> None:
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		cfg = _getUndefinedCharsCfg()
		# Translators: label of dialog
		label = _("Representation &method:")
		self.undefinedCharReprList = sHelper.addLabeledControl(
			label, wx.Choice, choices=list(CHOICES_LABELS.values())
		)
		self.undefinedCharReprList.SetSelection(cfg["method"])
		self.undefinedCharReprList.Bind(wx.EVT_CHOICE, self.onUndefinedCharReprList)
		# Translators: label of dialog
		self.undefinedCharReprEdit = sHelper.addLabeledControl(
			_("Specify another &pattern"), wx.TextCtrl, value=self.getHardValue()
		)
		self.undefinedCharDesc = sHelper.addItem(
			wx.CheckBox(self, label=(
				_("Show punctuation/symbol &name for undefined characters if available (can cause a lag)")
			))
		)
		self.undefinedCharDesc.SetValue(cfg["desc"])
		self.undefinedCharDesc.Bind(wx.EVT_CHECKBOX, self.onUndefinedCharDesc)
		# Translators: label for checkbox
		self.unicodeDataDescLastResort = sHelper.addItem(
			wx.CheckBox(self, label=_("Use Unicode character name at last resort (when no other description is available)"))
		)
		self.unicodeDataDescLastResort.SetValue(cfg.get("unicodeDataDescLastResort", False))
		# Translators: label for text field (format: x=hex, d=decimal, or direct chars)
		excludeLabel = _("E&xclude characters from description (x=hex, d=decimal, or direct characters, comma-separated):") + " e.g.: x00-x1f, xfffc, +"
		self.excludeDescChars = sHelper.addLabeledControl(
			excludeLabel,
			wx.TextCtrl,
			value=cfg.get("excludeDescChars", ""),
		)
		self.extendedDesc = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("Also describe e&xtended characters (e.g.: country flags)")
			)
		)
		self.extendedDesc.SetValue(cfg["extendedDesc"])
		self.extendedDesc.Bind(wx.EVT_CHECKBOX, self.onExtendedDesc)
		self.fullExtendedDesc = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("&Full extended description")
			)
		)
		self.fullExtendedDesc.SetValue(cfg["fullExtendedDesc"])
		self.showSize = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("Show the si&ze taken")
			)
		)
		self.showSize.SetValue(cfg["showSize"])
		self.startTag = sHelper.addLabeledControl(
			_("&Start tag:"), wx.TextCtrl, value=cfg["start"],
		)
		self.endTag = sHelper.addLabeledControl(
			_("&End tag:"), wx.TextCtrl, value=cfg["end"],
		)
		availableLangs = languageHandler.getAvailableLanguages()
		self._langValues = [lang[1] for lang in availableLangs]
		self._langKeys = [lang[0] for lang in availableLangs]
		undefinedCharLang = cfg["lang"]
		if undefinedCharLang not in self._langKeys:
			undefinedCharLang = self._langKeys[-1]
		undefinedCharLangID = self._langKeys.index(undefinedCharLang)
		self.undefinedCharLang = sHelper.addLabeledControl(
			_("&Language:"), wx.Choice, choices=self._langValues
		)
		self.undefinedCharLang.SetSelection(undefinedCharLangID)
		tableKeys = ["current"] + [
			t.fileName for t in addoncfg.tables if t.output
		]
		values = [_("Use the current output table")] + [
			t.displayName for t in addoncfg.tables if t.output
		]
		undefinedCharTable = cfg["table"]
		if undefinedCharTable not in addoncfg.tablesFN + ["current"]:
			undefinedCharTable = "current"
		undefinedCharTableID = tableKeys.index(undefinedCharTable)
		self.undefinedCharTable = sHelper.addLabeledControl(
			_("Braille &table:"), wx.Choice, choices=values
		)
		self.undefinedCharTable.SetSelection(undefinedCharTableID)
		# Translators: label of dialog
		label = _("Character limit at which descriptions are disabled (to avoid freezes, >):")
		self.characterLimit = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000000,
			initial=cfg["characterLimit"]
		)

		self.onExtendedDesc()
		self.onUndefinedCharDesc()
		self.onUndefinedCharReprList()

	def getHardValue(self) -> str:
		selected = self.undefinedCharReprList.GetSelection()
		if selected == CHOICE_otherDots:
			return _getUndefinedCharsCfg()["hardDotPatternValue"]
		if selected == CHOICE_otherSign:
			return _getUndefinedCharsCfg()["hardSignPatternValue"]
		return ""

	def onUndefinedCharDesc(self, evt: Optional[wx.CommandEvent] = None, forceDisable: bool = False) -> None:
		l = [
			self.unicodeDataDescLastResort,
			self.excludeDescChars,
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
		if selected in (CHOICE_otherDots, CHOICE_otherSign):
			self.undefinedCharReprEdit.Enable()
		else:
			self.undefinedCharReprEdit.Disable()
		self.undefinedCharReprEdit.SetValue(self.getHardValue())

	def postInit(self) -> None:
		self.undefinedCharDesc.SetFocus()

	def onSave(self) -> None:
		_clearCaches()
		cfg = _getUndefinedCharsCfg()
		cfg["method"] = self.undefinedCharReprList.GetSelection()
		repr_ = self.undefinedCharReprEdit.Value
		if self.undefinedCharReprList.GetSelection() == CHOICE_otherDots:
			repr_ = re.sub(r"[^0-8\-]", "", repr_).strip("-")
			repr_ = re.sub(r"\-+", "-", repr_)
			cfg["hardDotPatternValue"] = repr_
		else:
			cfg["hardSignPatternValue"] = repr_
		cfg["desc"] = self.undefinedCharDesc.IsChecked()
		cfg["extendedDesc"] = self.extendedDesc.IsChecked()
		cfg["fullExtendedDesc"] = self.fullExtendedDesc.IsChecked()
		cfg["showSize"] = self.showSize.IsChecked()
		cfg["unicodeDataDescLastResort"] = self.unicodeDataDescLastResort.IsChecked()
		cfg["excludeDescChars"] = self.excludeDescChars.Value.strip()
		cfg["start"] = self.startTag.Value
		cfg["end"] = self.endTag.Value
		cfg["lang"] = self._langKeys[self.undefinedCharLang.GetSelection()]
		tableKeys = ["current"] + [t.fileName for t in addoncfg.tables if t.output]
		cfg["table"] = tableKeys[self.undefinedCharTable.GetSelection()]
		cfg["characterLimit"] = self.characterLimit.Value


def _shouldIncludeExtendedSymbol(k: str, v: Any) -> bool:
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
