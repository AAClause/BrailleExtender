# coding: utf-8
# utils.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2021 André-Abush CLAUSE, released under GPL.

from __future__ import annotations

import os
import re

import addonHandler
import api
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
	default_braille_table_file_for_cur_language,
	NVDA_HAS_AUTOMATIC_BRAILLE_TABLES,
)
from . import huc
from . import volumehelper

get_mute = volumehelper.get_mute
get_volume_level = volumehelper.get_volume_level

# liblouis marks “free” input combinations with back-translated text matching this shape.
_RE_OVERVIEW_UNUSED_COMBO = re.compile(r"^\\.+/$")


def _resolveInputTableFileName(table_file: str) -> str:
	"""Map config or UI value ``auto`` to a concrete input table file name."""
	if table_file == "auto":
		return default_braille_table_file_for_cur_language(is_input=True)
	return table_file


def _liblouisTablePaths(table_file: str) -> list[str]:
	"""Primary table plus ``braille-patterns.cti`` (absolute paths)."""
	tables_dir = brailleTables.TABLES_DIR
	return [
		os.path.join(tables_dir, table_file),
		os.path.join(tables_dir, "braille-patterns.cti"),
	]


def report_volume_level():
	from .addoncfg import CHOICE_braille, CHOICE_speech, CHOICE_speechAndBraille

	feedback = config.conf["brailleExtender"]["volumeChangeFeedback"]
	braille_feedback = feedback in (CHOICE_braille, CHOICE_speechAndBraille)
	speech_feedback = feedback in (CHOICE_speech, CHOICE_speechAndBraille)

	if get_mute() and braille_feedback:
		return braille.handler.message(_("Muted sound"))
	volume_level = get_volume_level()
	if braille_feedback:
		msg = make_progress_bar_from_str(volume_level, "%3d%%" % volume_level, INSERT_AFTER)
		braille.handler.message(msg)
	if speech_feedback:
		speech.speakMessage(str(volume_level))


def make_progress_bar_from_str(percentage, text, method, positive="⢼", negative="⠤"):
	if len(positive) != 1 or len(negative) != 1:
		raise ValueError("positive and negative must be a string of size 1")
	braille_text = getTextInBraille(text)
	text_cell_count = len(braille_text)
	display_cell_count = braille.handler.displaySize
	if display_cell_count < text_cell_count + 3:
		return braille_text
	bar_cell_count = (
		display_cell_count
		if method == REPLACE_TEXT
		else (display_cell_count - text_cell_count) % display_cell_count
	)
	progress_bar = ""
	inner_width = bar_cell_count - 2
	if inner_width > 0:
		filled_last_index = int(float(percentage) / 100.0 * float(inner_width)) - 1
		progress_bar = "⣦%s⣴" % "".join(
			positive if slot_index <= filled_last_index else negative for slot_index in range(inner_width)
		)
	if method == INSERT_AFTER:
		return braille_text + progress_bar
	if method == INSERT_BEFORE:
		return progress_bar + braille_text
	return progress_bar


def getEffectiveInputTableFileName() -> str:
	"""Return the liblouis input table file name (never the config value ``auto``)."""
	if brailleInput.handler is not None:
		return brailleInput.handler.table.fileName
	return _resolveInputTableFileName(config.conf["braille"]["inputTable"])


def reload_braille_display(display_driver_name: str) -> bool:
	try:
		if braille.handler.setDisplayByName(display_driver_name):
			speech.speakMessage(_("Reload successful"))
			return True
	except RuntimeError:
		pass
	ui.message(_("Reload failed"))
	return False


def currentCharDesc(character: str = "", display: bool = True) -> str | None:
	if not character:
		character = getCurrentChar()
	if not character:
		return ui.message(_("Not a character"))
	codepoint = ord(character)
	if not codepoint:
		ui.message(_("Not a character"))
		return None
	try:
		char_name = unicodedata.name(character)
	except ValueError:
		char_name = _("unknown")
	char_category = unicodedata.category(character)
	huc_repr = "%s, %s" % (
		huc.translate(character, HUC6=False),
		huc.translate(character, HUC6=True),
	)
	speech_output = getSpeechSymbols(character)
	braille_cells = getTextInBraille(character)
	braille_cell_desc = huc.unicodeBrailleToDescription(braille_cells)
	summary = (
		f"{character}: {hex(codepoint)}, {codepoint}, {oct(codepoint)}, {bin(codepoint)}\n"
		f"{speech_output} ({char_name} [{char_category}])\n"
		f"{braille_cells} ({braille_cell_desc})\n"
		f"{huc_repr}"
	)
	if not display:
		return summary
	repeat = scriptHandler.getLastScriptRepeatCount()
	if repeat == 0:
		ui.message(summary)
	elif repeat == 1:
		ui.browseableMessage(
			summary,
			(r"U+%.4x (%s) - " % (codepoint, character)) + _("Char info"),
		)
	return None


def getCurrentChar():
	character_info = api.getReviewPosition().copy()
	character_info.expand(textInfos.UNIT_CHARACTER)
	return character_info.text


def getTextSelection():
	focus_object = api.getFocusObject()
	tree_interceptor = focus_object.treeInterceptor
	if (
		isinstance(tree_interceptor, treeInterceptorHandler.DocumentTreeInterceptor)
		and not tree_interceptor.passThrough
	):
		focus_object = tree_interceptor
	try:
		selection_info = focus_object.makeTextInfo(textInfos.POSITION_SELECTION)
	except (RuntimeError, NotImplementedError):
		selection_info = None
	if not selection_info or selection_info.isCollapsed:
		navigator = api.getNavigatorObject()
		name = navigator.name
		return name if name else ""
	return selection_info.text


def getKeysTranslation(gesture_identifier: str) -> str | None:
	original = gesture_identifier
	lowered = gesture_identifier.lower()
	nvda_prefix = "NVDA+" if "nvda+" in lowered else ""
	if "br(" in lowered:
		return None
	normalized = lowered.replace("kb:", "").replace("nvda+", "")
	try:
		display_name = KeyboardInputGesture.fromName(normalized).displayName
		display_name = re.sub(r"([^a-zA-Z]|^)f([0-9])", r"\1F\2", display_name)
	except Exception:
		return original
	return nvda_prefix + display_name


def getTextInBraille(text=None, table=None):
	if table is None:
		table = []
	if not isinstance(table, list):
		raise TypeError("Wrong type for table parameter: %s" % repr(table))
	if not text:
		text = getTextSelection()
	if not text:
		return ""
	if not table or "current" in table:
		liblouis_tables = getCurrentBrailleTables()
	else:
		liblouis_tables = []
		tables_root = brailleTables.TABLES_DIR
		for entry in table:
			if "\\" not in entry and "/" not in entry:
				liblouis_tables.append("%s\\%s" % (tables_root, entry))
			else:
				liblouis_tables.append(entry)
	return "\n".join(
		louis.translateString(liblouis_tables, line, mode=louis.ucBrl | louis.dotsIO)
		for line in text.split("\n")
		if line
	)


def format_braille_dot_legend(cell_dot_description: str, vacant_slot: str = "⠤") -> str:
	"""Eight-character summary of dots 1–8 for a single braille cell.

	``cell_dot_description`` is typically from :func:`huc.unicodeBrailleToDescription`
	(e.g. ``-146``). Each output position is the dot digit if that dot is raised,
	otherwise ``vacant_slot`` (Unicode ``⠤`` by default).
	"""
	raised_dots = frozenset(c for c in cell_dot_description if "1" <= c <= "8")
	return "".join(
		str(dot_number) if str(dot_number) in raised_dots else vacant_slot for dot_number in range(1, 9)
	)


def getTableOverview(table_file: str = "") -> str:
	"""
	Return an overview of an input braille table.
	:param table_file: the braille table to use (default: the current input braille table).
	:type table_file: str
	:return: an overview of braille table in the form of a textual table
	:rtype: str
	"""
	table_name = _resolveInputTableFileName(table_file) if table_file else getEffectiveInputTableFileName()
	table_paths = _liblouisTablePaths(table_name)
	header = "Input              Output\n"
	overview_lines: dict[str, str] = {}
	unused_combo_chars: list[str] = []
	braille_block_start = 0x2800
	for codepoint in range(braille_block_start, braille_block_start + 256):
		braille_char = chr(codepoint)
		back_translated = louis.backTranslate(table_paths, braille_char, mode=louis.ucBrl)[0]
		if _RE_OVERVIEW_UNUSED_COMBO.match(back_translated):
			unused_combo_chars.append(braille_char)
			continue
		cell_dot_description = huc.unicodeBrailleToDescription(braille_char)
		input_column = "%s (%s)" % (braille_char, format_braille_dot_legend(cell_dot_description))
		translated_raw = back_translated.rstrip("\x00")
		if len(back_translated) == 1 and back_translated:
			hex_note = " (%-10s)" % hex(ord(back_translated))
		elif not back_translated:
			hex_note = "#ERROR"
		else:
			hex_note = ""
		output_column = "%s%-8s" % (translated_raw, hex_note)
		row_key = back_translated if back_translated else "?"
		overview_lines[row_key] = "%s       %-7s" % (input_column, output_column)
	body = "\n".join(overview_lines[key] for key in sorted(overview_lines))
	overview_text = header + body
	unused_count = len(unused_combo_chars)
	if unused_count > 1:
		overview_text += (
			"\n"
			+ _("Available combinations")
			+ " (%d): %s"
			% (
				unused_count,
				"".join(unused_combo_chars),
			)
		)
	elif unused_count == 1:
		overview_text += "\n" + _("One combination available") + ": %s" % unused_combo_chars[0]
	return overview_text


def format_gesture_identifiers(gesture_text, sep=" / "):
	"""Turn raw NVDA gesture id strings into short, readable text (labels, docs, UI)."""
	if isinstance(gesture_text, list):
		gesture_text = " ".join(gesture_text)
	gesture_text = gesture_text.replace(",", " ").replace(";", " ").replace("  ", " ")
	token_replacements = {
		"b10": "b0",
		"braillespacebar": "space",
		"space": _("space"),
		"leftshiftkey": _("left SHIFT"),
		"rightshiftkey": _("right SHIFT"),
		"leftgdfbutton": _("left selector"),
		"rightgdfbutton": _("right selector"),
		"dot": _("dot"),
	}
	display_model_re = re.compile(r"^.+\.([^)]+)\).+$")
	gesture_text = gesture_text.replace(";", ",")
	formatted_gestures = []
	for token in gesture_text.split(" "):
		if not token.strip():
			continue
		display_model = ""
		model_match = display_model_re.match(token)
		if model_match:
			display_model = model_match.group(1)
		token = re.sub(r".+:", "", token)
		token = "+".join(sorted(token.split("+")))
		for internal_token, label in token_replacements.items():
			token = re.sub(
				r"(\+|^)%s([0-9]\+|$)" % internal_token,
				r"\1%s\2" % label,
				token,
			)
		formatted_gestures.append(
			_("{gesture} on {brailleDisplay}").format(gesture=token, brailleDisplay=display_model)
			if display_model
			else token
		)
	return formatted_gestures if not sep else sep.join(formatted_gestures)


def getText():
	focus_object = api.getFocusObject()
	tree_interceptor = focus_object.treeInterceptor
	if hasattr(tree_interceptor, "TextInfo") and not tree_interceptor.passThrough:
		focus_object = tree_interceptor
	try:
		document_info = focus_object.makeTextInfo(textInfos.POSITION_ALL)
		return document_info.text
	except Exception:
		pass
	return None


def getTextCaret():
	focus_object = api.getFocusObject()
	tree_interceptor = focus_object.treeInterceptor
	if hasattr(tree_interceptor, "TextInfo") and not tree_interceptor.passThrough:
		focus_object = tree_interceptor
	try:
		document_all = focus_object.makeTextInfo(textInfos.POSITION_ALL)
		caret_pos = focus_object.makeTextInfo(textInfos.POSITION_CARET)
		document_all.setEndPoint(caret_pos, "endToStart")
		try:
			return document_all.text
		except Exception:
			return None
	except Exception:
		pass
	return None


def getTextPosition():
	try:
		document_text = getText()
		caret_text = getTextCaret() or ""
		total_length = len(document_text) if document_text is not None else 0
		return len(caret_text), total_length
	except Exception:
		return 0, 0


def uncapitalize(text: str) -> str:
	return text[:1].lower() + text[1:] if text else ""


def refresh_braille_for_current_focus() -> None:
	"""Re-run braille focus handling for the document or foreground object (after display or config changes)."""
	focus_object = api.getFocusObject()
	tree_interceptor = focus_object.treeInterceptor
	if tree_interceptor is not None:
		updated_interceptor = treeInterceptorHandler.update(focus_object)
		if not updated_interceptor.passThrough:
			braille.handler.handleGainFocus(updated_interceptor)
	else:
		braille.handler.handleGainFocus(api.getFocusObject())


def getSpeechSymbols(text: str | None = None) -> str:
	"""Return speech symbol description for text (or selection). Shows message if no text."""
	if not text:
		text = getTextSelection()
	if not text:
		return ui.message(_("No text selected"))
	locale = languageHandler.getLanguage()
	return characterProcessing.processSpeechSymbols(
		locale,
		text,
		get_symbol_level("SYMLVL_CHAR"),
	).strip()


def getTether():
	if hasattr(braille.handler, "getTether"):
		return braille.handler.getTether()
	return braille.handler.tether


def getCharFromValue(value_spec: str) -> str:
	if not isinstance(value_spec, str):
		raise TypeError("Wrong type")
	if not value_spec or len(value_spec) < 2:
		raise ValueError("Wrong value")
	radix_by_prefix = {"b": 2, "d": 10, "h": 16, "o": 8, "x": 16}
	prefix, digits = value_spec[0].lower(), value_spec[1:]
	if prefix not in radix_by_prefix:
		raise ValueError("Wrong base (%s)" % prefix)
	radix = radix_by_prefix[prefix]
	codepoint = int(digits, radix)
	return chr(codepoint)


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
	from . import braille_table_chain

	return braille_table_chain.get_translation_table_file()


def getActiveOutputTableForSwitch():
	"""Returns the effective output table identifier for switching: 'auto' or table fileName."""
	configured = config.conf["braille"]["translationTable"]
	if configured == "auto":
		return "auto"
	if supportsAutomaticBrailleTables():
		default_file = default_braille_table_file_for_cur_language(is_input=False)
		if braille.handler.table.fileName == default_file:
			return "auto"
	return configured


def getActiveInputTableForSwitch():
	"""Returns the effective input table identifier for switching: 'auto' or table fileName."""
	configured = config.conf["braille"]["inputTable"]
	if configured == "auto":
		return "auto"
	if supportsAutomaticBrailleTables():
		default_file = default_braille_table_file_for_cur_language(is_input=True)
		if brailleInput.handler.table.fileName == default_file:
			return "auto"
	return brailleInput.handler.table.fileName


def getCurrentBrailleTables(for_input: bool = False, brf: bool = False):
	from . import braille_table_chain

	return braille_table_chain.get_liblouis_table_chain(for_input=for_input, brf=brf)


def get_output_reason(reason_name):
	legacy_attr = "REASON_%s" % reason_name
	if hasattr(controlTypes, "OutputReason") and hasattr(controlTypes.OutputReason, reason_name):
		return getattr(controlTypes.OutputReason, reason_name)
	if hasattr(controlTypes, legacy_attr):
		return getattr(controlTypes, legacy_attr)
	raise AttributeError('Reason "%s" unknown' % reason_name)


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
	speech_mode = get_speech_mode()
	if hasattr(speech, "SpeechMode"):
		return speech_mode == speech.SpeechMode.talk
	return speech_mode == speech.speechMode_talk


def set_speech_off():
	if hasattr(speech, "SpeechMode"):
		return speech.setSpeechMode(speech.SpeechMode.off)
	speech.speechMode = speech.speechMode_off


def set_speech_talk():
	if hasattr(speech, "SpeechMode"):
		return speech.setSpeechMode(speech.SpeechMode.talk)
	speech.speechMode = speech.speechMode_talk


def get_control_type(control_type):
	if not isinstance(control_type, str):
		raise TypeError("control_type must be a string")
	if hasattr(controlTypes, "Role"):
		attr = "_".join(control_type.split("_")[1:])
		if control_type.startswith("ROLE_"):
			return getattr(controlTypes.Role, attr)
		if control_type.startswith("STATE_"):
			return getattr(controlTypes.State, attr)
		raise ValueError(control_type)
	return getattr(controlTypes, control_type)


def get_symbol_level(symbol_level):
	if not isinstance(symbol_level, str):
		raise TypeError("symbol_level must be a string")
	if hasattr(characterProcessing, "SymbolLevel"):
		return getattr(
			characterProcessing.SymbolLevel,
			"_".join(symbol_level.split("_")[1:]),
		)
	return getattr(characterProcessing, symbol_level)
