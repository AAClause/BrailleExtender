# coding: utf-8
# common.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.

from __future__ import annotations

import os
import re

import addonHandler
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
# - 2025.1: speakOnNavigatingByUnit, automatic braille table selection (inputTable/translationTable "auto")
NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING = nvdaVersionAtLeast(2022, 3)
NVDA_HAS_SPEAK_ON_ROUTING = nvdaVersionAtLeast(2024, 4)
NVDA_HAS_SPEAK_ON_NAVIGATING_BY_UNIT = nvdaVersionAtLeast(2025, 1)
NVDA_HAS_AUTOMATIC_BRAILLE_TABLES = nvdaVersionAtLeast(2025, 1)


lang = languageHandler.getLanguage().split('_')[-1].lower()
punctuationSeparator = ' ' if 'fr' in lang else ''


profilesDir = os.path.join(baseDir, "Profiles")

N_ = lambda s: _(s)

CHOICE_none = "none"

# text attributes
CHOICE_liblouis = "liblouis"
CHOICE_dot7 = "dot7"
CHOICE_dot8 = "dot8"
CHOICE_dots78 = "dots78"
CHOICE_tags = "tags"
CHOICE_spacing = "spacing"
TAG_SEPARATOR = chr(5)
CHOICE_likeSpeech = '0'
CHOICE_enabled = '1'
CHOICE_disabled = '2'

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
