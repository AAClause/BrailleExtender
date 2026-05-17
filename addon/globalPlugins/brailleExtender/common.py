# coding: utf-8
# common.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.

from __future__ import annotations

import os
import re

import addonHandler
import brailleTables
import versionInfo
import controlTypes
import globalVars
import languageHandler


def get_is_current_no():
	if hasattr(controlTypes, "IsCurrent"):
		return controlTypes.IsCurrent.NO
	return False


IS_CURRENT_NO = get_is_current_no()

configDir = "%s/brailleExtender" % globalVars.appArgs.configPath
baseDir = os.path.dirname(__file__)
addonDir = os.path.join(baseDir, "..", "..")
addonName = addonHandler.Addon(addonDir).manifest["name"]
addonSummary = addonHandler.Addon(addonDir).manifest["summary"]
addonVersion = addonHandler.Addon(addonDir).manifest["version"]
addonURL = addonHandler.Addon(addonDir).manifest["url"]
addonGitHubURL = "https://github.com/aaclause/BrailleExtender/"
addonAuthor = addonHandler.Addon(addonDir).manifest["author"]
addonDesc = addonHandler.Addon(addonDir).manifest["description"]
addonUpdateChannel = addonHandler.Addon(addonDir).manifest["updateChannel"]


def nvdaVersionAtLeast(year: int, major: int, minor: int = 0) -> bool:
	"""Check if current NVDA version is >= year.major.minor.
	Import from common for custom version checks, e.g. nvdaVersionAtLeast(2024, 4).
	"""
	try:
		parts = versionInfo.version.split(".", 2)

		def _intPart(s):
			m = re.search(r"\d+", s)
			return int(m.group()) if m else 0

		vYear = _intPart(parts[0]) if len(parts) > 0 else 0
		vMajor = _intPart(parts[1]) if len(parts) > 1 else 0
		vMinor = _intPart(parts[2]) if len(parts) > 2 else 0
		return (vYear, vMajor, vMinor) >= (year, major, minor)
	except (ValueError, IndexError, AttributeError):
		return False


# NVDA core features (from changelog), used for addon compatibility:
# - 2022.3: interruptSpeechWhileScrolling (speech interrupt when scrolling)
# - 2024.4: speakOnRouting (announce character when routing cursor)
# - 2024.3: custom braille tables (brailleTables.addTable, per-addon/scratchpad directories)
# - 2025.1: speakOnNavigatingByUnit (NVDA braille), automatic braille table selection (inputTable/translationTable "auto")
# BrailleExtender speakScroll stays independent; turn off NVDA's "Speak when navigating by line or paragraph" to avoid duplicates.
NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING = nvdaVersionAtLeast(2022, 3)
NVDA_HAS_SPEAK_ON_ROUTING = nvdaVersionAtLeast(2024, 4)
NVDA_HAS_CUSTOM_BRAILLE_TABLES = nvdaVersionAtLeast(2024, 3)
NVDA_HAS_AUTOMATIC_BRAILLE_TABLES = nvdaVersionAtLeast(2025, 1)

# Config value for disabled additional Liblouis output pass (``brailleExtender.postTable``).
POST_TABLE_NONE = "None"


def default_braille_table_file_for_cur_language(*, is_input: bool) -> str:
	"""Return a concrete braille table file name for the current NVDA language.

	On NVDA 2025.1 and later this follows NVDA’s automatic table selection.
	On NVDA 2024.x (no ``TableType`` / ``getDefaultTableForCurLang``) this returns
	addon-consistent fallbacks and must not touch those APIs.
	"""
	if NVDA_HAS_AUTOMATIC_BRAILLE_TABLES:
		table_type = brailleTables.TableType.INPUT if is_input else brailleTables.TableType.OUTPUT
		return brailleTables.getDefaultTableForCurLang(table_type)
	if is_input:
		# Matches historical ``addoncfg.loadGestures`` fallback when ``inputTable == "auto"``.
		return "en-us-comp8.utb"
	return brailleTables.DEFAULT_TABLE


lang = languageHandler.getLanguage().split("_")[-1].lower()
punctuationSeparator = " " if "fr" in lang else ""


profilesDir = os.path.join(baseDir, "Profiles")


def N_(s):
	return _(s)


CHOICE_none = "none"

# text attributes
CHOICE_liblouis = "liblouis"
CHOICE_dot7 = "dot7"
CHOICE_dot8 = "dot8"
CHOICE_dots78 = "dots78"
CHOICE_tags = "tags"
CHOICE_spacing = "spacing"  # legacy alignment config value; treated like ``CHOICE_linePad`` at runtime
CHOICE_linePad = "linePad"  # alignment-only: prepend braille blanks to suggest visual position on the display
TAG_SEPARATOR = chr(5)
# Stored as '0' in config. Means “match NVDA Document formatting” + core braille markers when present — not “mirror speech output”.
CHOICE_likeSpeech = "0"
CHOICE_enabled = "1"
CHOICE_disabled = "2"

# Bitmasks OR'd onto Liblouis output cells (dots 1–6 occupy bits 0–5; dots 7–8 are the “brlex” overlay).
BRLEX_DOT7_CELL_MASK = 0x40
BRLEX_DOT8_CELL_MASK = 0x80
BRLEX_DOTS78_CELL_MASK = BRLEX_DOT7_CELL_MASK | BRLEX_DOT8_CELL_MASK

BRLEX_CELL_MASK_BY_METHOD: dict[str, int] = {
	CHOICE_dot7: BRLEX_DOT7_CELL_MASK,
	CHOICE_dot8: BRLEX_DOT8_CELL_MASK,
	CHOICE_dots78: BRLEX_DOTS78_CELL_MASK,
}

REPLACE_TEXT = 0
INSERT_AFTER = 1
INSERT_BEFORE = 2

ADDON_ORDER_PROPERTIES = "states,cellCoordsText,value,name,roleText,description,keyboardShortcut,positionInfo,positionInfoLevel,current,placeholder"

ROLE_LABEL = 0
FORMATTING_LABEL = 1

# auto scroll
DEFAULT_AUTO_SCROLL_DELAY = 3000
MIN_AUTO_SCROLL_DELAY = 200
MAX_AUTO_SCROLL_DELAY = 42000
DEFAULT_STEP_DELAY_CHANGE = 100
MIN_STEP_DELAY_CHANGE = 25
MAX_STEP_DELAY_CHANGE = 7000

# Routing cursors behavior in edit fields
RC_NORMAL = "normal"
RC_EMULATE_ARROWS_BEEP = "arrows_beeps"
RC_EMULATE_ARROWS_SILENT = "arrows_silent"


def parse_braille_table_list(raw: str | list[str]) -> list[str]:
	"""Parse a Braille Extender comma-separated table list from config (``inputTables``, etc.)."""
	if isinstance(raw, list):
		return [entry for entry in raw if entry]
	return [entry for entry in raw.replace(", ", ",").split(",") if entry]
