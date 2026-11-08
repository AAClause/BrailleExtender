# coding: utf-8
"""Unit tests for dual braille input tables feature (Issue #127)."""

import pytest
import config
import ui
import speech

from globalPlugins.brailleExtender.common import SECONDARY_INPUT_TABLE_NONE
from globalPlugins.brailleExtender import utils
from globalPlugins.brailleExtender import addoncfg
from globalPlugins.brailleExtender import GlobalPlugin


@pytest.fixture(autouse=True)
def reset_config_state():
	"""Reset configuration and handlers before and after each test."""
	config.conf["braille"]["inputTable"] = "en-us-comp8.utb"
	config.conf["brailleExtender"]["activeInputTable"] = ""
	config.conf["brailleExtender"]["primaryInputTable"] = ""
	config.conf["brailleExtender"]["secondaryInputTable"] = SECONDARY_INPUT_TABLE_NONE
	addoncfg.noUnicodeTable = False
	ui.message.reset_mock()
	speech.speakMessage.reset_mock()
	yield
	config.conf["braille"]["inputTable"] = "en-us-comp8.utb"
	config.conf["brailleExtender"]["activeInputTable"] = ""
	config.conf["brailleExtender"]["primaryInputTable"] = ""
	config.conf["brailleExtender"]["secondaryInputTable"] = SECONDARY_INPUT_TABLE_NONE
	ui.message.reset_mock()
	speech.speakMessage.reset_mock()


class TestDualInputTableConfig:
	"""Test configuration and persistence of primary and secondary input tables."""

	def test_default_config_values(self):
		assert utils.getPrimaryInputTable() == ""
		assert utils.getSecondaryInputTable() == SECONDARY_INPUT_TABLE_NONE

	def test_set_and_get_secondary_input_table(self):
		utils.setSecondaryInputTable("unicode-braille.utb")
		assert utils.getSecondaryInputTable() == "unicode-braille.utb"
		assert config.conf["brailleExtender"]["secondaryInputTable"] == "unicode-braille.utb"

		# Reset to none
		utils.setSecondaryInputTable("")
		assert utils.getSecondaryInputTable() == SECONDARY_INPUT_TABLE_NONE

	def test_set_and_get_primary_input_table(self):
		utils.setPrimaryInputTable("en-us-comp8.utb")
		assert utils.getPrimaryInputTable() == "en-us-comp8.utb"
		assert config.conf["brailleExtender"]["primaryInputTable"] == "en-us-comp8.utb"


class TestDualInputTableAnnouncement:
	"""Test announcement message formatting."""

	def test_format_input_table_announcement(self):
		msg = utils.format_input_table_announcement("Unicode braille")
		assert msg == "Input table: Unicode braille"

	def test_announcement_with_various_names(self):
		msg = utils.format_input_table_announcement("English (U.S.) 8 dot computer braille")
		assert msg == "Input table: English (U.S.) 8 dot computer braille"


class TestDualInputTableToggling:
	"""Test toggling between primary and secondary input tables."""

	def test_toggle_between_explicit_primary_and_secondary(self):
		utils.setPrimaryInputTable("en-us-comp8.utb")
		utils.setSecondaryInputTable("unicode-braille.utb")
		utils.apply_braille_input_table("en-us-comp8.utb")

		assert utils.getActiveInputTableForSwitch() == "en-us-comp8.utb"

		# First toggle: primary -> secondary
		target, msg = utils.toggle_input_table()
		assert target == "unicode-braille.utb"
		assert "Unicode braille" in msg
		assert utils.getActiveInputTableForSwitch() == "unicode-braille.utb"

		# Second toggle: secondary -> primary
		target, msg = utils.toggle_input_table()
		assert target == "en-us-comp8.utb"
		assert "English (U.S.) 8 dot computer braille" in msg
		assert utils.getActiveInputTableForSwitch() == "en-us-comp8.utb"

		# Third toggle: primary -> secondary again
		target, msg = utils.toggle_input_table()
		assert target == "unicode-braille.utb"
		assert utils.getActiveInputTableForSwitch() == "unicode-braille.utb"

	def test_toggle_with_inferred_primary_table(self):
		# Primary not set; active table is en-ueb-g2.ctb
		utils.apply_braille_input_table("en-ueb-g2.ctb")
		utils.setSecondaryInputTable("unicode-braille.utb")

		assert utils.getPrimaryInputTable() == ""

		# First toggle: should remember current table as primary and switch to secondary
		target, msg = utils.toggle_input_table()
		assert target == "unicode-braille.utb"
		assert utils.getPrimaryInputTable() == "en-ueb-g2.ctb"
		assert utils.getActiveInputTableForSwitch() == "unicode-braille.utb"

		# Second toggle: switches back to remembered primary
		target, msg = utils.toggle_input_table()
		assert target == "en-ueb-g2.ctb"
		assert utils.getActiveInputTableForSwitch() == "en-ueb-g2.ctb"

	def test_consecutive_multi_toggles(self):
		utils.setPrimaryInputTable("ar-ar-g1.utb")
		utils.setSecondaryInputTable("unicode-braille.utb")
		utils.apply_braille_input_table("ar-ar-g1.utb")

		for _ in range(5):
			target, msg = utils.toggle_input_table()
			assert target == "unicode-braille.utb"
			assert "Unicode braille" in msg

			target, msg = utils.toggle_input_table()
			assert target == "ar-ar-g1.utb"
			assert "Arabic 6 dot" in msg


class TestDualInputTableFallbacks:
	"""Test fallback behaviors when tables are unconfigured or unavailable."""

	def test_fallback_when_secondary_is_none(self):
		utils.setPrimaryInputTable("en-us-comp8.utb")
		utils.setSecondaryInputTable(SECONDARY_INPUT_TABLE_NONE)
		utils.apply_braille_input_table("unicode-braille.utb")

		# Toggling with no secondary table configured should fall back to primary/default
		target, msg = utils.toggle_input_table()
		assert target == "en-us-comp8.utb"
		assert "English (U.S.) 8 dot computer braille" in msg

	def test_fallback_when_secondary_is_unavailable(self):
		utils.setPrimaryInputTable("en-us-comp8.utb")
		utils.setSecondaryInputTable("nonexistent-table.utb")
		utils.apply_braille_input_table("en-us-comp8.utb")

		# Toggling with unavailable secondary table should fall back to default table
		target, msg = utils.toggle_input_table()
		default_table = utils.default_braille_table_file_for_cur_language(is_input=True)
		assert target in (default_table, "en-us-comp8.utb", "auto")
		assert utils.getActiveInputTableForSwitch() in (default_table, "en-us-comp8.utb", "auto")

	def test_fallback_when_primary_is_unavailable(self):
		utils.setPrimaryInputTable("nonexistent-primary.utb")
		utils.setSecondaryInputTable("unicode-braille.utb")
		utils.apply_braille_input_table("unicode-braille.utb")

		# When on secondary and toggling back to an invalid primary, fall back to default
		target, msg = utils.toggle_input_table()
		default_table = utils.default_braille_table_file_for_cur_language(is_input=True)
		assert target in (default_table, "en-us-comp8.utb", "auto")


class TestScriptToggleInputBrailleTable:
	"""Test script execution and gesture binding on GlobalPlugin."""

	def test_script_decorator_metadata(self):
		plugin = GlobalPlugin()
		script_func = getattr(plugin, "script_toggleInputBrailleTable", None)
		assert script_func is not None
		assert hasattr(script_func, "_script_kwargs")
		kwargs = script_func._script_kwargs
		assert kwargs.get("gesture") == "kb:control+shift+NVDA+i"
		assert "input braille table" in kwargs.get("description", "").lower()

	def test_script_execution_announces_feedback(self):
		plugin = GlobalPlugin()
		plugin.reloadBrailleTables = lambda *args, **kwargs: None

		utils.setPrimaryInputTable("en-us-comp8.utb")
		utils.setSecondaryInputTable("unicode-braille.utb")
		utils.apply_braille_input_table("en-us-comp8.utb")

		plugin.script_toggleInputBrailleTable(None)

		# ui.message should have been called with the feedback announcement
		ui.message.assert_called_once()
		announced = ui.message.call_args[0][0]
		assert "Input table:" in announced
		assert "Unicode braille" in announced

	def test_script_requires_unicode_support(self):
		plugin = GlobalPlugin()
		addoncfg.noUnicodeTable = True

		plugin.script_toggleInputBrailleTable(None)
		ui.message.assert_called_once()
		announced = ui.message.call_args[0][0]
		assert "NVDA 2017.3 or later is required" in announced
