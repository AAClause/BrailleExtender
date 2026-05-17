# coding: utf-8
# settings.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.


import addonHandler
import brailleTables
import config
import gui
import inputCore
import queueHandler
import scriptHandler
import ui
import wx

from . import addoncfg
from . import braille_table_chain
from . import custom_braille_tables
from . import utils
from .common import POST_TABLE_NONE
from .advancedinput import SettingsDlg as AdvancedInputModeDlg
from .common import (
	addonName,
	punctuationSeparator,
	RC_NORMAL,
	nvdaVersionAtLeast,
	NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING,
	NVDA_HAS_SPEAK_ON_ROUTING,
)
from .autoscroll import SettingsDlg as AutoScrollDlg
from .documentformatting import SettingsDlg as DocumentFormattingDlg
from .objectpresentation import SettingsDlg as ObjectPresentationDlg
from .onehand import SettingsDlg as OneHandModeDlg
from .rolelabels import SettingsDlg as RoleLabelsDlg
from .speechhistorymode import SettingsDlg as SpeechHistorymodeDlg
from .undefinedchars import SettingsDlg as UndefinedCharsDlg

addonHandler.initTranslation()

instanceGP = None
addonSettingsDialogActiveConfigProfile = None
addonSettingsDialogWindowHandle = None


def notImplemented(msg="", style=wx.OK | wx.ICON_INFORMATION):
	if not msg:
		msg = _("Feature implementation is in progress. Thanks for your patience.")
	gui.messageBox(msg, _("Braille Extender"), wx.OK | wx.ICON_INFORMATION)


class GeneralDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("General")
	_bds = addoncfg.getValidBrailleDisplayPrefered()
	bds_k = [k for k, v in _bds]
	bds_v = [v for k, v in _bds]

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: label of a dialog.
		choices = [
			_("stable channel, automatic check"),
			_("dev channel, automatic check"),
			_("stable channel, manual check"),
			_("dev channel, manual check"),
		]
		self.updateCheck = sHelper.addLabeledControl(_("Check for upd&ates:"), wx.Choice, choices=choices)
		if config.conf["brailleExtender"]["updateChannel"] in addoncfg.updateChannels.keys():
			itemToSelect = list(addoncfg.updateChannels.keys()).index(
				config.conf["brailleExtender"]["updateChannel"]
			)
		else:
			itemToSelect = list(addoncfg.updateChannels.keys()).index(addoncfg.CHANNEL_stable)
		if not config.conf["brailleExtender"]["autoCheckUpdate"]:
			itemToSelect += len(addoncfg.updateChannels.keys())
		self.updateCheck.SetSelection(itemToSelect)

		# Translators: label of a dialog.
		self.speakScroll = sHelper.addLabeledControl(
			_("Say current line while &scrolling in:"),
			wx.Choice,
			choices=list(addoncfg.focusOrReviewChoices.values()),
		)
		self.speakScroll.SetSelection(
			list(addoncfg.focusOrReviewChoices.keys()).index(config.conf["brailleExtender"]["speakScroll"])
		)
		if nvdaVersionAtLeast(2025, 1):
			sHelper.addItem(
				wx.StaticText(
					self,
					label=_(
						"NVDA 2025.1+ also has a global braille option, “Speak when navigating by line or paragraph”. "
						"Disable that NVDA option if you hear duplicate line announcements."
					),
				)
			)

		# Translators: label of a dialog.
		self.stopSpeechScroll = sHelper.addItem(
			wx.CheckBox(self, label=_("Speech &interrupt when scrolling on same line"))
		)
		self.stopSpeechScroll.SetValue(config.conf["brailleExtender"]["stopSpeechScroll"])
		if NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING:
			self.stopSpeechScroll.Enable(False)
			sHelper.addItem(
				wx.StaticText(
					self,
					label=_('Use NVDA Braille settings → "Interrupt speech while scrolling" (since 2022.3)'),
				)
			)

		# Translators: label of a dialog.
		self.skipBlankLinesScroll = sHelper.addItem(
			wx.CheckBox(self, label=_("S&kip blank lines during text scrolling"))
		)
		self.skipBlankLinesScroll.SetValue(config.conf["brailleExtender"]["skipBlankLinesScroll"])

		# Translators: label of a dialog.
		self.smartCapsLock = sHelper.addItem(wx.CheckBox(self, label=_("Smart Caps Loc&k")))
		self.smartCapsLock.SetValue(config.conf["brailleExtender"]["smartCapsLock"])

		# Translators: label of a dialog.
		self.stopSpeechUnknown = sHelper.addItem(
			wx.CheckBox(self, label=_("Speech i&nterrupt for unknown gestures"))
		)
		self.stopSpeechUnknown.SetValue(config.conf["brailleExtender"]["stopSpeechUnknown"])

		# Translators: label of a dialog.
		self.speakRoutingTo = sHelper.addItem(
			wx.CheckBox(self, label=_("Announce character when &routing braille cursor"))
		)
		self.speakRoutingTo.SetValue(config.conf["brailleExtender"]["speakRoutingTo"])
		if NVDA_HAS_SPEAK_ON_ROUTING:
			self.speakRoutingTo.Enable(False)
			sHelper.addItem(
				wx.StaticText(
					self,
					label=_(
						'Use NVDA Braille settings → "Speak character when routing cursor in text" (since 2024.4)'
					),
				)
			)

		# Translators: label of a dialog.
		label = _("Routing cursors behavior in edit &fields:")
		self.routingCursorsEditFields = sHelper.addLabeledControl(
			label, wx.Choice, choices=list(addoncfg.routingCursorsEditFields_labels.values())
		)
		if (
			config.conf["brailleExtender"]["routingCursorsEditFields"]
			in addoncfg.routingCursorsEditFields_labels
		):
			itemToSelect = list(addoncfg.routingCursorsEditFields_labels.keys()).index(
				config.conf["brailleExtender"]["routingCursorsEditFields"]
			)
		else:
			itemToSelect = list(addoncfg.routingCursorsEditFields_labels.keys()).index(RC_NORMAL)
		self.routingCursorsEditFields.SetSelection(itemToSelect)

		self.reviewModeTerminal = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_(
					"Automatically Switch to review mode in &terminal windows (cmd, bash, PuTTY, PowerShell Maxima…)"
				),
			)
		)
		self.reviewModeTerminal.SetValue(config.conf["brailleExtender"]["reviewModeTerminal"])

		# Translators: label of a dialog.
		self.volumeChangeFeedback = sHelper.addLabeledControl(
			_("Announce &volume changes:"), wx.Choice, choices=list(addoncfg.outputMessage.values())
		)
		if config.conf["brailleExtender"]["volumeChangeFeedback"] in addoncfg.outputMessage:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(
				config.conf["brailleExtender"]["volumeChangeFeedback"]
			)
		else:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(addoncfg.CHOICE_braille)
		self.volumeChangeFeedback.SetSelection(itemToSelect)

		# Translators: label of a dialog.
		self.modifierKeysFeedback = sHelper.addLabeledControl(
			_("Announce m&odifier key presses:"), wx.Choice, choices=list(addoncfg.outputMessage.values())
		)
		if config.conf["brailleExtender"]["modifierKeysFeedback"] in addoncfg.outputMessage:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(
				config.conf["brailleExtender"]["modifierKeysFeedback"]
			)
		else:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(addoncfg.CHOICE_braille)
		# Translators: label of a dialog.
		self.beepsModifiers = sHelper.addItem(wx.CheckBox(self, label=_("Play &beeps for modifier keys")))
		self.beepsModifiers.SetValue(config.conf["brailleExtender"]["beepsModifiers"])

		# Translators: label of a dialog.
		self.modifierKeysFeedback.SetSelection(itemToSelect)
		self.rightMarginCells = sHelper.addLabeledControl(
			_("&Right margin on cells for the active braille display"),
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=100,
			initial=int(config.conf["brailleExtender"]["rightMarginCells_%s" % addoncfg.curBD]),
		)
		if addoncfg.gesturesFileExists:
			lb = [k for k in instanceGP.getKeyboardLayouts()]
			# Translators: label of a dialog.
			self.KBMode = sHelper.addLabeledControl(
				_("Braille &keyboard configuration:"), wx.Choice, choices=lb
			)
			self.KBMode.SetSelection(addoncfg.getKeyboardLayout())

		# Translators: label of a dialog.
		self.reverseScrollBtns = sHelper.addItem(
			wx.CheckBox(self, label=_("&Reverse forward and back scroll buttons"))
		)
		self.reverseScrollBtns.SetValue(config.conf["brailleExtender"]["reverseScrollBtns"])

		self.brailleDisplay1 = sHelper.addLabeledControl(
			_("&Primary favorite display (reload with NVDA+J):"), wx.Choice, choices=self.bds_v
		)
		driver_name = "last"
		if config.conf["brailleExtender"]["brailleDisplay1"] in self.bds_k:
			driver_name = config.conf["brailleExtender"]["brailleDisplay1"]
		self.brailleDisplay1.SetSelection(self.bds_k.index(driver_name))
		self.brailleDisplay2 = sHelper.addLabeledControl(
			_("&Second favorite display (reload with NVDA+Shift+J):"), wx.Choice, choices=self.bds_v
		)
		driver_name = "last"
		if config.conf["brailleExtender"]["brailleDisplay2"] in self.bds_k:
			driver_name = config.conf["brailleExtender"]["brailleDisplay2"]
		self.brailleDisplay2.SetSelection(self.bds_k.index(driver_name))

	def postInit(self):
		self.autoCheckUpdate.SetFocus()

	def onSave(self):
		updateCheckChoice = self.updateCheck.GetSelection()
		size = len(addoncfg.updateChannels.keys())
		config.conf["brailleExtender"]["autoCheckUpdate"] = updateCheckChoice < size
		config.conf["brailleExtender"]["updateChannel"] = list(addoncfg.updateChannels.keys())[
			updateCheckChoice % size
		]

		config.conf["brailleExtender"]["reviewModeTerminal"] = self.reviewModeTerminal.IsChecked()
		if self.reverseScrollBtns.IsChecked():
			instanceGP.reverseScrollBtns()
		else:
			instanceGP.reverseScrollBtns(None, True)
		config.conf["brailleExtender"]["reverseScrollBtns"] = self.reverseScrollBtns.IsChecked()
		config.conf["brailleExtender"]["stopSpeechScroll"] = self.stopSpeechScroll.IsChecked()
		config.conf["brailleExtender"]["skipBlankLinesScroll"] = self.skipBlankLinesScroll.IsChecked()
		config.conf["brailleExtender"]["smartCapsLock"] = self.smartCapsLock.IsChecked()
		config.conf["brailleExtender"]["stopSpeechUnknown"] = self.stopSpeechUnknown.IsChecked()
		config.conf["brailleExtender"]["speakRoutingTo"] = self.speakRoutingTo.IsChecked()

		config.conf["brailleExtender"]["speakScroll"] = list(addoncfg.focusOrReviewChoices.keys())[
			self.speakScroll.GetSelection()
		]

		config.conf["brailleExtender"]["rightMarginCells_%s" % addoncfg.curBD] = self.rightMarginCells.Value
		config.conf["brailleExtender"]["brailleDisplay1"] = self.bds_k[self.brailleDisplay1.GetSelection()]
		config.conf["brailleExtender"]["brailleDisplay2"] = self.bds_k[self.brailleDisplay2.GetSelection()]
		if addoncfg.gesturesFileExists:
			config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD] = list(
				addoncfg.iniProfile["keyboardLayouts"].keys()
			)[self.KBMode.GetSelection()]
		config.conf["brailleExtender"]["routingCursorsEditFields"] = list(
			addoncfg.routingCursorsEditFields_labels.keys()
		)[self.routingCursorsEditFields.GetSelection()]
		config.conf["brailleExtender"]["volumeChangeFeedback"] = list(addoncfg.outputMessage.keys())[
			self.volumeChangeFeedback.GetSelection()
		]
		config.conf["brailleExtender"]["modifierKeysFeedback"] = list(addoncfg.outputMessage.keys())[
			self.modifierKeysFeedback.GetSelection()
		]
		config.conf["brailleExtender"]["beepsModifiers"] = self.beepsModifiers.IsChecked()


class AddCustomBrailleTableDlg(wx.Dialog):
	"""Choose how to initialize a new custom braille table."""

	SOURCE_COPY = 0
	SOURCE_SCRATCH = 1

	def __init__(self, parent):
		# Translators: title of the dialog when adding a custom braille table.
		super().__init__(parent, title=_("Add custom braille table"))

		self._tables = custom_braille_tables.list_registered_tables_for_copy()
		self._table_file_names = [table.fileName for table in self._tables]
		table_labels = [f"{table.displayName} ({table.fileName})" for table in self._tables]

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: label for options when creating a new custom braille table.
		source_choices = [
			_("Copy from an existing table"),
			_("Create an empty table"),
		]
		self.sourceRadioBox = sHelper.addItem(
			wx.RadioBox(self, label=_("&How do you want to create the table?"), choices=source_choices)
		)
		self.sourceRadioBox.SetSelection(self.SOURCE_COPY)

		# Translators: label for the list of tables to copy when adding a custom braille table.
		self.tableChoice = sHelper.addLabeledControl(
			_("&Table to copy:"),
			wx.Choice,
			choices=table_labels,
		)
		default_index = self._default_source_table_index()
		if table_labels:
			self.tableChoice.SetSelection(default_index)

		self.sourceRadioBox.Bind(wx.EVT_RADIOBOX, self._on_source_changed)
		self._on_source_changed()

		sHelper.addItem(
			wx.StaticText(
				self,
				label=_(
					"NVDA registers braille tables as .utb, .ctb, or occasionally .tbl. "
					"Copying keeps the source extension. "
					"The list includes built-in tables, tables from other add-ons, and your "
					"Braille Extender custom tables—use Copy to clone a table you already manage. "
					"An empty table is created as .utb, or as .ctb if you mark it contracted."
				),
			)
		)

		sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=gui.guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.sourceRadioBox.SetFocus()

	def _default_source_table_index(self) -> int:
		try:
			return self._table_file_names.index(braille_table_chain.get_translation_table_file())
		except ValueError:
			return 0

	def _on_source_changed(self, evt: wx.CommandEvent | None = None) -> None:
		copy_from_existing = self.sourceRadioBox.GetSelection() == self.SOURCE_COPY
		self.tableChoice.Enable(copy_from_existing and self.tableChoice.GetCount() > 0)

	@property
	def source_mode(self) -> int:
		return self.sourceRadioBox.GetSelection()

	@property
	def selected_table_file_name(self) -> str | None:
		if self.source_mode != self.SOURCE_COPY or not self._table_file_names:
			return None
		return self._table_file_names[self.tableChoice.GetSelection()]


class CustomBrailleTablePropertiesDlg(wx.Dialog):
	"""Set display name and input/output flags for a custom braille table."""

	def __init__(
		self,
		parent,
		title: str,
		*,
		display_name: str = "",
		contracted: bool = False,
		input_table: bool = True,
		output_table: bool = True,
	):
		super().__init__(parent, title=title)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.displayNameCtrl = sHelper.addLabeledControl(_("&Display name:"), wx.TextCtrl)
		self.displayNameCtrl.SetValue(display_name)
		self.contractedCheck = sHelper.addItem(wx.CheckBox(self, label=_("Con&tracted braille")))
		self.contractedCheck.SetValue(contracted)
		self.inputCheck = sHelper.addItem(wx.CheckBox(self, label=_("&Input table")))
		self.inputCheck.SetValue(input_table)
		self.outputCheck = sHelper.addItem(wx.CheckBox(self, label=_("&Output table")))
		self.outputCheck.SetValue(output_table)
		sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=gui.guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.displayNameCtrl.SetFocus()

	@property
	def properties(self) -> dict:
		return {
			"displayName": self.displayNameCtrl.GetValue(),
			"contracted": self.contractedCheck.IsChecked(),
			"input": self.inputCheck.IsChecked(),
			"output": self.outputCheck.IsChecked(),
		}


class CustomBrailleTablesDlg(gui.settingsDialogs.SettingsDialog):
	"""Manage user-defined Liblouis braille tables."""

	# Translators: title of a dialog opened from the Braille Extender submenu or Braille tables settings.
	title = _("Custom braille tables")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._build_ui(sHelper)

	def postInit(self):
		if self.activeInputTableChoice is not None:
			self.activeInputTableChoice.SetFocus()
		elif self.customTablesList is not None:
			self.customTablesList.SetFocus()

	def onOk(self, evt: wx.CommandEvent) -> None:
		if self._save_active_custom_table_selections() and instanceGP is not None:
			instanceGP.reloadBrailleTables(apply_handlers=True)
		super().onOk(evt)

	def _build_ui(self, sHelper: gui.guiHelper.BoxSizerHelper) -> None:
		self.activeInputTableChoice = None
		self.activeOutputTableChoice = None
		self._active_input_file_names: list[str] = []
		self._active_output_file_names: list[str] = []
		self.customTablesList = None
		self._custom_table_buttons: list[wx.Button] = []
		if not utils.supports_custom_braille_tables():
			sHelper.addItem(
				wx.StaticText(
					self,
					label=_(
						"Custom braille tables require NVDA 2024.3 or later. "
						"Update NVDA to add your own Liblouis tables."
					),
				)
			)
			return

		sHelper.addItem(
			wx.StaticText(
				self,
				label=_(
					"Choose which custom table to use here. "
					"They do not appear in NVDA Braille settings. "
					"Select None to use your usual NVDA tables instead."
				),
			)
		)
		self._reload_active_table_choices()
		self.activeInputTableChoice = sHelper.addLabeledControl(
			_("Active custom &input table:"),
			wx.Choice,
			choices=self._active_input_labels,
		)
		self.activeOutputTableChoice = sHelper.addLabeledControl(
			_("Active custom &output table:"),
			wx.Choice,
			choices=self._active_output_labels,
		)
		self._set_active_table_choice_selections()

		self._custom_table_file_names: list[str] = []
		self.customTablesList = sHelper.addLabeledControl(
			_("Registered &custom tables:"),
			wx.ListCtrl,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
			size=(550, 200),
		)
		self.customTablesList.InsertColumn(0, _("Name"), width=200)
		self.customTablesList.InsertColumn(1, _("File"), width=180)
		self.customTablesList.InsertColumn(2, _("Input"), width=55)
		self.customTablesList.InsertColumn(3, _("Output"), width=55)
		self._reload_custom_tables_list()

		btnHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		for label, handler in (
			(_("&Add…"), self._on_custom_table_add),
			(_("&Remove"), self._on_custom_table_remove),
			(_("&Edit…"), self._on_custom_table_edit_file),
			(_("P&roperties…"), self._on_custom_table_properties),
		):
			button = btnHelper.addButton(self, label=label)
			button.Bind(wx.EVT_BUTTON, handler)
			self._custom_table_buttons.append(button)
		sHelper.addItem(btnHelper)

	def _reload_active_table_choices(self) -> None:
		self._active_input_file_names, self._active_input_labels = (
			custom_braille_tables.build_active_table_choice_lists(for_input=True)
		)
		self._active_output_file_names, self._active_output_labels = (
			custom_braille_tables.build_active_table_choice_lists(for_input=False)
		)

	def _set_active_table_choice_selections(self) -> None:
		if self.activeInputTableChoice is None:
			return
		active_input = custom_braille_tables.get_active_custom_input_table()
		active_output = custom_braille_tables.get_active_custom_output_table()
		try:
			self.activeInputTableChoice.SetSelection(self._active_input_file_names.index(active_input))
		except ValueError:
			self.activeInputTableChoice.SetSelection(0)
		try:
			self.activeOutputTableChoice.SetSelection(self._active_output_file_names.index(active_output))
		except ValueError:
			self.activeOutputTableChoice.SetSelection(0)

	def _refresh_active_table_choice_controls(self) -> None:
		if self.activeInputTableChoice is None:
			return
		input_index = self.activeInputTableChoice.GetSelection()
		output_index = self.activeOutputTableChoice.GetSelection()
		input_file = (
			self._active_input_file_names[input_index]
			if 0 <= input_index < len(self._active_input_file_names)
			else custom_braille_tables.ACTIVE_TABLE_NONE
		)
		output_file = (
			self._active_output_file_names[output_index]
			if 0 <= output_index < len(self._active_output_file_names)
			else custom_braille_tables.ACTIVE_TABLE_NONE
		)
		self._reload_active_table_choices()
		self.activeInputTableChoice.SetItems(self._active_input_labels)
		self.activeOutputTableChoice.SetItems(self._active_output_labels)
		try:
			self.activeInputTableChoice.SetSelection(self._active_input_file_names.index(input_file))
		except ValueError:
			self.activeInputTableChoice.SetSelection(0)
		try:
			self.activeOutputTableChoice.SetSelection(self._active_output_file_names.index(output_file))
		except ValueError:
			self.activeOutputTableChoice.SetSelection(0)

	def _save_active_custom_table_selections(self) -> bool:
		if self.activeInputTableChoice is None:
			return False
		input_index = self.activeInputTableChoice.GetSelection()
		output_index = self.activeOutputTableChoice.GetSelection()
		new_input = self._active_input_file_names[input_index]
		new_output = self._active_output_file_names[output_index]
		old_input = custom_braille_tables.get_active_custom_input_table()
		old_output = custom_braille_tables.get_active_custom_output_table()
		if new_input == old_input and new_output == old_output:
			return False
		custom_braille_tables.set_active_custom_input_table(new_input)
		custom_braille_tables.set_active_custom_output_table(new_output)
		return True

	def _reload_custom_tables_list(self, *, select_file_name: str | None = None) -> None:
		if self.customTablesList is None:
			return
		self.customTablesList.DeleteAllItems()
		self._custom_table_file_names = []
		for index, (file_name, meta) in enumerate(custom_braille_tables.list_entries()):
			self._custom_table_file_names.append(file_name)
			row = (
				str(meta.get("displayName", file_name)),
				file_name,
				_("Yes") if meta.get("input", True) else _("No"),
				_("Yes") if meta.get("output", True) else _("No"),
			)
			self.customTablesList.InsertItem(index, row[0])
			for column, value in enumerate(row[1:], start=1):
				self.customTablesList.SetItem(index, column, value)
		if select_file_name:
			self._select_custom_table(select_file_name)

	def _select_custom_table(self, file_name: str) -> None:
		if self.customTablesList is None:
			return
		try:
			index = self._custom_table_file_names.index(file_name)
		except ValueError:
			return
		selected = self.customTablesList.GetFirstSelected()
		while selected >= 0:
			self.customTablesList.Select(selected, on=0)
			selected = self.customTablesList.GetNextSelected(selected)
		self.customTablesList.Select(index)
		self.customTablesList.Focus(index)
		self.customTablesList.EnsureVisible(index)
		self.customTablesList.SetFocus()

	def _selected_custom_table_file_name(self) -> str | None:
		if self.customTablesList is None:
			return None
		index = self.customTablesList.GetFirstSelected()
		if index < 0:
			return None
		return self._custom_table_file_names[index]

	def _apply_custom_table_changes(self, *, select_file_name: str | None = None) -> None:
		self._reload_custom_tables_list(select_file_name=select_file_name)
		self._refresh_active_table_choice_controls()
		instanceGP.reloadBrailleTables(apply_handlers=True)

	def _on_custom_table_add(self, evt: wx.CommandEvent) -> None:
		source_dlg = AddCustomBrailleTableDlg(self)
		if source_dlg.ShowModal() != wx.ID_OK:
			return

		source_table = None
		if source_dlg.source_mode == AddCustomBrailleTableDlg.SOURCE_COPY:
			source_file_name = source_dlg.selected_table_file_name
			if not source_file_name:
				return
			try:
				source_table = brailleTables.getTable(source_file_name)
			except LookupError:
				return
			default_name = source_table.displayName
		else:
			default_name = _("New custom table")

		props_dlg = CustomBrailleTablePropertiesDlg(
			self,
			_("Add custom braille table"),
			display_name=default_name,
			contracted=source_table.contracted if source_table else False,
			input_table=source_table.input if source_table else True,
			output_table=source_table.output if source_table else True,
		)
		if props_dlg.ShowModal() != wx.ID_OK:
			return
		props = props_dlg.properties
		if not props["input"] and not props["output"]:
			gui.messageBox(
				_("A table must be enabled for input and/or output."),
				_("Braille Extender"),
				style=wx.OK | wx.ICON_ERROR,
			)
			return
		try:
			if source_dlg.source_mode == AddCustomBrailleTableDlg.SOURCE_COPY:
				new_file_name = custom_braille_tables.add_table_from_registered(
					source_dlg.selected_table_file_name,
					props["displayName"],
					contracted=props["contracted"],
					input_table=props["input"],
					output_table=props["output"],
				)
			else:
				new_file_name = custom_braille_tables.add_table_from_scratch(
					props["displayName"],
					contracted=props["contracted"],
					input_table=props["input"],
					output_table=props["output"],
				)
		except (OSError, ValueError, LookupError, FileNotFoundError) as error:
			gui.messageBox(str(error), _("Braille Extender"), style=wx.OK | wx.ICON_ERROR)
			return
		if props["input"]:
			custom_braille_tables.set_active_custom_input_table(new_file_name)
		if props["output"]:
			custom_braille_tables.set_active_custom_output_table(new_file_name)
		self._apply_custom_table_changes(select_file_name=new_file_name)

	def _on_custom_table_remove(self, evt: wx.CommandEvent) -> None:
		file_name = self._selected_custom_table_file_name()
		if not file_name:
			return
		if (
			gui.messageBox(
				_("Remove custom table %(name)s? The Liblouis file will be deleted.") % {"name": file_name},
				_("Braille Extender"),
				style=wx.YES_NO | wx.ICON_WARNING,
			)
			!= wx.YES
		):
			return
		custom_braille_tables.remove_table(file_name)
		self._apply_custom_table_changes()

	def _on_custom_table_edit_file(self, evt: wx.CommandEvent) -> None:
		file_name = self._selected_custom_table_file_name()
		if not file_name:
			return
		try:
			custom_braille_tables.open_table_file(file_name)
		except OSError as error:
			gui.messageBox(str(error), _("Braille Extender"), style=wx.OK | wx.ICON_ERROR)

	def _on_custom_table_properties(self, evt: wx.CommandEvent) -> None:
		file_name = self._selected_custom_table_file_name()
		if not file_name:
			return
		meta = dict(custom_braille_tables.load_config()["tables"][file_name])
		props_dlg = CustomBrailleTablePropertiesDlg(
			self,
			_("Custom braille table properties"),
			display_name=str(meta.get("displayName", file_name)),
			contracted=bool(meta.get("contracted", False)),
			input_table=bool(meta.get("input", True)),
			output_table=bool(meta.get("output", True)),
		)
		if props_dlg.ShowModal() != wx.ID_OK:
			return
		props = props_dlg.properties
		if not props["input"] and not props["output"]:
			gui.messageBox(
				_("A table must be enabled for input and/or output."),
				_("Braille Extender"),
				style=wx.OK | wx.ICON_ERROR,
			)
			return
		try:
			custom_braille_tables.update_table_metadata(
				file_name,
				display_name=props["displayName"],
				contracted=props["contracted"],
				input_table=props["input"],
				output_table=props["output"],
			)
		except (KeyError, ValueError) as error:
			gui.messageBox(str(error), _("Braille Extender"), style=wx.OK | wx.ICON_ERROR)
			return
		self._apply_custom_table_changes()


class BrailleTablesDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("Braille tables")

	def _getOutputTablesData(self):
		data = [(t[0], t[1]) for t in addoncfg.tables if t.output]
		if utils.supportsAutomaticBrailleTables():
			data.insert(0, ("auto", utils.getAutomaticTableDisplayName(is_input=False)))
		return data

	def _getInputTablesData(self):
		data = [(t[0], t[1]) for t in addoncfg.tables if t.input]
		if utils.supportsAutomaticBrailleTables():
			data.insert(0, ("auto", utils.getAutomaticTableDisplayName(is_input=True)))
		return data

	def makeSettings(self, settingsSizer):
		outputData = self._getOutputTablesData()
		inputData = self._getInputTablesData()
		outputFNs = [t[0] for t in outputData]
		inputFNs = [t[0] for t in inputData]

		activeOutput = utils.getActiveOutputTableForSwitch()
		activeInput = utils.getActiveInputTableForSwitch()
		self.oTables = set(addoncfg.outputTables or []) | {activeOutput}
		self.iTables = set(addoncfg.inputTables or []) | {activeInput}
		self.oTables &= set(outputFNs)
		self.iTables &= set(inputFNs)
		self.oTables.add(activeOutput)
		self.iTables.add(activeInput)

		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		outputChoices = [t[1] for t in outputData]
		self.outputTablesList = sHelper.addLabeledControl(
			_("Preferred &output braille tables:"), gui.nvdaControls.CustomCheckListBox, choices=outputChoices
		)
		self.outputTablesList.CheckedItems = [
			i for i, (fn, _dn) in enumerate(outputData) if fn in self.oTables
		]

		inputChoices = [t[1] for t in inputData]
		self.inputTablesList = sHelper.addLabeledControl(
			_("Preferred &input braille tables:"), gui.nvdaControls.CustomCheckListBox, choices=inputChoices
		)
		self.inputTablesList.CheckedItems = [i for i, (fn, _dn) in enumerate(inputData) if fn in self.iTables]

		lt = [_("Use the current input table")]
		for t in addoncfg.tables:
			if t.output and not t.contracted:
				lt.append(t[1])
		iSht = (
			addoncfg.tablesUFN.index(config.conf["brailleExtender"]["inputTableShortcuts"]) + 1
			if config.conf["brailleExtender"]["inputTableShortcuts"] in addoncfg.tablesUFN
			else 0
		)
		self.inputTableShortcuts = sHelper.addLabeledControl(
			_("Input braille table for &keyboard shortcut keys:"), wx.Choice, choices=lt
		)
		self.inputTableShortcuts.SetSelection(iSht)

		postOutputFNs = braille_table_chain.list_output_table_file_names()
		lt = [_("None")] + [t[1] for t in addoncfg.tables if t.output]
		postTableVal = config.conf["brailleExtender"]["postTable"]
		postIdx = postOutputFNs.index(postTableVal) + 1 if postTableVal in postOutputFNs else 0
		self.postTable = sHelper.addLabeledControl(
			_("&Additional Liblouis output pass:"), wx.Choice, choices=lt
		)
		self.postTable.SetSelection(postIdx)
		sHelper.addItem(
			wx.StaticText(
				self,
				label=_(
					"After the main output table, the selected table is applied again to the braille. "
					"Use None to show only the main table result."
				),
			)
		)

		self.tabSpace = sHelper.addItem(wx.CheckBox(self, label=_("Display &tabs as spaces")))
		self.tabSpace.SetValue(config.conf["brailleExtender"]["tabSpace"])

		self.tabSize = sHelper.addLabeledControl(
			_("&Spaces per tab for the active braille display:"),
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=1,
			max=42,
			initial=int(config.conf["brailleExtender"]["tabSize_%s" % addoncfg.curBD]),
		)

		if utils.supports_custom_braille_tables():
			manage_btn = sHelper.addItem(wx.Button(self, label=_("&Manage custom braille tables…")))
			manage_btn.Bind(wx.EVT_BUTTON, self._on_manage_custom_braille_tables)
		else:
			sHelper.addItem(
				wx.StaticText(
					self,
					label=_(
						"Custom braille tables require NVDA 2024.3 or later. "
						"Update NVDA to add your own Liblouis tables."
					),
				)
			)

	def _on_manage_custom_braille_tables(self, evt: wx.CommandEvent) -> None:
		getattr(gui.mainFrame, "popupSettingsDialog", gui.mainFrame._popupSettingsDialog)(
			CustomBrailleTablesDlg
		)

	def postInit(self):
		self.outputTablesList.SetFocus()

	def onSave(self):
		outputData = self._getOutputTablesData()
		inputData = self._getInputTablesData()
		self.oTables = {
			outputData[i][0]
			for i in range(self.outputTablesList.GetCount())
			if self.outputTablesList.IsChecked(i)
		}
		self.iTables = {
			inputData[i][0]
			for i in range(self.inputTablesList.GetCount())
			if self.inputTablesList.IsChecked(i)
		}

		config.conf["brailleExtender"]["outputTables"] = ",".join(sorted(self.oTables))
		config.conf["brailleExtender"]["inputTables"] = ",".join(sorted(self.iTables))
		config.conf["brailleExtender"]["inputTableShortcuts"] = (
			addoncfg.tablesUFN[self.inputTableShortcuts.GetSelection() - 1]
			if self.inputTableShortcuts.GetSelection() > 0
			else "?"
		)
		postOutputFNs = braille_table_chain.list_output_table_file_names()
		postTableID = self.postTable.GetSelection()
		config.conf["brailleExtender"]["postTable"] = (
			POST_TABLE_NONE if postTableID == 0 else postOutputFNs[postTableID - 1]
		)
		config.conf["brailleExtender"]["tabSpace"] = self.tabSpace.IsChecked()
		config.conf["brailleExtender"]["tabSize_%s" % addoncfg.curBD] = self.tabSize.Value
		instanceGP.reloadBrailleTables()


class RotorDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("Rotor")
	# Translators: Shown as the short description for this category in Braille Extender settings.
	panelDescription = _("Configure which items appear in the rotor and in what order.")

	def makeSettings(self, settingsSizer):
		from . import rotor

		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._ids = list(rotor.master_order_from_config())
		self._normalize_default_first_ids()
		enabled = rotor.enabled_ids_from_config()
		labels = [rotor.ROTOR_LABELS[i] for i in self._ids]
		self.rotorList = sHelper.addLabeledControl(
			_("Rotor &items (checked entries are included when you cycle the rotor):"),
			gui.nvdaControls.CustomCheckListBox,
			choices=labels,
		)
		for i, oid in enumerate(self._ids):
			if oid in enabled:
				self.rotorList.Check(i)
		self.rotorList.Check(0)
		self.rotorList.Bind(wx.EVT_CHECKLISTBOX, self._on_rotor_item_checked)
		bMove = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.moveBeforeBtn = bMove.addButton(self, label=_("Move &before"))
		self.moveBeforeBtn.Bind(wx.EVT_BUTTON, self.onMoveBefore)
		self.moveAfterBtn = bMove.addButton(self, label=_("Move &after"))
		self.moveAfterBtn.Bind(wx.EVT_BUTTON, self.onMoveAfter)
		sHelper.addItem(bMove)

	def postInit(self):
		self.rotorList.SetFocus()
		if self.rotorList.GetCount() > 0:
			self.rotorList.SetSelection(0)

	def _normalize_default_first_ids(self):
		from . import rotor

		dv = rotor.RotorId.default.value
		if dv not in self._ids:
			return
		if self._ids[0] == dv:
			return
		self._ids = [dv] + [x for x in self._ids if x != dv]

	def _on_rotor_item_checked(self, evt: wx.CommandEvent):
		from . import rotor

		evt.Skip()
		ix = evt.GetSelection()
		dv = rotor.RotorId.default.value
		if 0 <= ix < len(self._ids) and self._ids[ix] == dv and not self.rotorList.IsChecked(ix):
			self.rotorList.Check(ix)

	def _refresh_list_preserving_checks(self):
		from . import rotor

		dv = rotor.RotorId.default.value
		checks = {self._ids[i]: self.rotorList.IsChecked(i) for i in range(len(self._ids))}
		checks[dv] = True
		self._normalize_default_first_ids()
		labels = [rotor.ROTOR_LABELS[i] for i in self._ids]
		self.rotorList.SetItems(labels)
		for i, oid in enumerate(self._ids):
			if checks.get(oid):
				self.rotorList.Check(i)
		self.rotorList.Check(0)

	def _checked_row_indices(self):
		return [i for i in range(self.rotorList.GetCount()) if self.rotorList.IsChecked(i)]

	def _prev_checked_index(self, i: int):
		chk = self._checked_row_indices()
		if i not in chk:
			return None
		pos = chk.index(i)
		if pos == 0:
			return None
		return chk[pos - 1]

	def _next_checked_index(self, i: int):
		chk = self._checked_row_indices()
		if i not in chk:
			return None
		pos = chk.index(i)
		if pos >= len(chk) - 1:
			return None
		return chk[pos + 1]

	def onMoveBefore(self, evt):
		from . import rotor

		dv = rotor.RotorId.default.value
		i = self.rotorList.GetSelection()
		prev = self._prev_checked_index(i)
		if prev is None:
			return
		if self._ids[prev] == dv:
			return
		moved = self._ids[i]
		self._ids[i], self._ids[prev] = self._ids[prev], self._ids[i]
		self._refresh_list_preserving_checks()
		self.rotorList.SetSelection(self._ids.index(moved))

	def onMoveAfter(self, evt):
		from . import rotor

		dv = rotor.RotorId.default.value
		i = self.rotorList.GetSelection()
		if self._ids[i] == dv:
			return
		nxt = self._next_checked_index(i)
		if nxt is None:
			return
		moved = self._ids[i]
		self._ids[i], self._ids[nxt] = self._ids[nxt], self._ids[i]
		self._refresh_list_preserving_checks()
		self.rotorList.SetSelection(self._ids.index(moved))

	def onSave(self):
		from . import rotor

		self._refresh_list_preserving_checks()
		order_str, enabled_str = rotor.format_config_order_and_enabled(
			self._ids,
			[self.rotorList.IsChecked(i) for i in range(len(self._ids))],
		)
		config.conf["brailleExtender"]["rotor"]["itemOrder"] = order_str
		config.conf["brailleExtender"]["rotor"]["itemEnabled"] = enabled_str
		rotor.reload_from_config()
		if instanceGP is not None:
			rotor.clamp_rotor_index()
			instanceGP.bindRotorGES()


class QuickLaunchesDlg(gui.settingsDialogs.SettingsDialog):
	# Translators: title of a dialog.
	title = _("Braille Extender - Quick launches")
	quickLaunchGestures = []
	quickLaunchLocations = []
	captureEnabled = False
	captureLabelBtn = None

	def makeSettings(self, settingsSizer):
		self.quickLaunchGestures = list(config.conf["brailleExtender"]["quickLaunches"].copy().keys())
		self.quickLaunchLocations = list(config.conf["brailleExtender"]["quickLaunches"].copy().values())
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		bHelper1 = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.quickKeys = sHelper.addLabeledControl(
			_("&Gestures:"), wx.Choice, choices=self.getQuickLaunchList()
		)
		self.quickKeys.SetSelection(0)
		self.quickKeys.Bind(wx.EVT_CHOICE, self.onQuickKeys)
		self.target = sHelper.addLabeledControl(
			_("&Location (file path, URL or command)"),
			wx.TextCtrl,
			value=self.quickLaunchLocations[0] if self.quickLaunchLocations != [] else "",
		)
		self.target.Bind(wx.EVT_TEXT, self.onTarget)
		self.browseBtn = bHelper1.addButton(self, wx.ID_ANY, _("&Browse..."), wx.DefaultPosition)
		self.removeGestureBtn = bHelper1.addButton(
			self, wx.ID_ANY, _("&Remove this gesture"), wx.DefaultPosition
		)
		self.addGestureBtn = bHelper1.addButton(self, wx.ID_ANY, _("&Add a quick launch"), wx.DefaultPosition)
		self.browseBtn.Bind(wx.EVT_BUTTON, self.onBrowseBtn)
		self.removeGestureBtn.Bind(wx.EVT_BUTTON, self.onRemoveGestureBtn)
		self.addGestureBtn.Bind(wx.EVT_BUTTON, self.onAddGestureBtn)
		sHelper.addItem(bHelper1)

	def postInit(self):
		self.quickKeys.SetFocus()

	def onOk(self, evt):
		if inputCore.manager._captureFunc:
			inputCore.manager._captureFunc = None
		config.conf["brailleExtender"]["quickLaunches"] = {}
		for gesture, location in zip(self.quickLaunchGestures, self.quickLaunchLocations):
			config.conf["brailleExtender"]["quickLaunches"][gesture] = location
		instanceGP.loadQuickLaunchesGes()
		super().onOk(evt)

	def onCancel(self, evt):
		if inputCore.manager._captureFunc:
			inputCore.manager._captureFunc = None
		super().onCancel(evt)

	def captureNow(self):
		def getCaptured(gesture):
			script = scriptHandler.findScript(gesture)
			if script and hasattr(script, "bypassInputHelp") and script.bypassInputHelp:
				queueHandler.queueFunction(queueHandler.eventQueue, gesture.script, gesture)
				return False
			if script is not None:
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					_("Unable to associate this gesture. Please enter another gesture"),
				)
				return False
			if gesture.isModifier:
				return False
			if gesture.normalizedIdentifiers[0].startswith("kb") and not gesture.normalizedIdentifiers[
				0
			].endswith(":escape"):
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					_(
						f"Please enter a gesture from your {addoncfg.curBD} braille display. Press space to cancel."
					),
				)
				return False
			if gesture.normalizedIdentifiers[0].endswith(":space"):
				inputCore.manager._captureFunc = None
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Out of capture"))
			elif not gesture.normalizedIdentifiers[0].endswith(":escape"):
				self.quickLaunchGestures.append(gesture.normalizedIdentifiers[0])
				self.quickLaunchLocations.append("")
				self.quickKeys.SetItems(self.getQuickLaunchList())
				self.quickKeys.SetSelection(len(self.quickLaunchGestures) - 1)
				self.onQuickKeys(None)
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					ui.message,
					_("The gesture captured is %s")
					% utils.format_gesture_identifiers(gesture.normalizedIdentifiers[0]),
				)
				inputCore.manager._captureFunc = None
				self.captureEnabled = False
				self.addGestureBtn.SetLabel(self.captureLabelBtn)
				self.target.SetFocus()
			return True

		inputCore.manager._captureFunc = getCaptured

	def getQuickLaunchList(s):
		quickLaunchGesturesKeys = list(s.quickLaunchGestures)
		return [
			"%s%s: %s"
			% (utils.format_gesture_identifiers(quickLaunchGesturesKeys[i]), punctuationSeparator, v)
			for i, v in enumerate(s.quickLaunchLocations)
		]

	def onRemoveGestureBtn(self, event):
		if self.quickKeys.GetSelection() < 0:
			self.askCreateQuickLaunch()
			return

		def askConfirmation():
			choice = gui.messageBox(
				_("Are you sure you wish to delete this shortcut?"),
				"%s – %s" % (addonName, _("Remove shortcut")),
				wx.YES_NO | wx.ICON_QUESTION,
			)
			if choice == wx.YES:
				confirmed()

		def confirmed():
			i = self.quickKeys.GetSelection()
			g = self.quickLaunchGestures.pop(i)
			self.quickLaunchLocations.pop(i)
			listQuickLaunches = self.getQuickLaunchList()
			self.quickKeys.SetItems(listQuickLaunches)
			if len(listQuickLaunches) > 0:
				self.quickKeys.SetSelection(i - 1 if i > 0 else 0)
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _(f"{g} removed"))
			self.onQuickKeys(None)

		wx.CallAfter(askConfirmation)
		self.quickKeys.SetFocus()

	def onAddGestureBtn(self, event):
		if self.captureEnabled:
			self.captureEnabled = False
			self.addGestureBtn.SetLabel(self.captureLabelBtn)
			return
		self.captureNow()
		queueHandler.queueFunction(
			queueHandler.eventQueue,
			ui.message,
			_('Please enter the desired gesture for the new quick launch. Press "space bar" to cancel'),
		)
		self.captureEnabled = True
		self.captureLabelBtn = self.addGestureBtn.GetLabel()
		self.addGestureBtn.SetLabel(_("Don't add a quick launch"))
		return

	def onTarget(self, event):
		oldS = self.quickKeys.GetSelection()
		if oldS < 0:
			self.target.SetValue("")
			return
		self.quickLaunchLocations[self.quickKeys.GetSelection()] = self.target.GetValue()
		self.quickKeys.SetItems(self.getQuickLaunchList())
		self.quickKeys.SetSelection(oldS)

	def onQuickKeys(self, event):
		if self.quickKeys.GetSelection() < 0:
			self.target.SetValue("")
			return
		if not self.quickKeys.GetStringSelection().strip().startswith(":"):
			self.target.SetValue(self.quickKeys.GetStringSelection().split(": ")[1])
		else:
			self.target.SetValue("")
		return

	def onBrowseBtn(self, event):
		oldS = self.quickKeys.GetSelection()
		if oldS < 0:
			self.askCreateQuickLaunch()
			return
		dlg = wx.FileDialog(
			None,
			_("Choose a file for {0}").format(self.quickLaunchGestures[self.quickKeys.GetSelection()]),
			"%PROGRAMFILES%",
			"",
			"*",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return self.quickKeys.SetFocus()
		self.target.SetValue(dlg.GetDirectory() + "\\" + dlg.GetFilename())
		self.quickLaunchLocations[self.quickKeys.GetSelection()] = (
			dlg.GetDirectory() + "\\" + dlg.GetFilename()
		)
		self.quickKeys.SetItems(self.getQuickLaunchList())
		self.quickKeys.SetSelection(oldS)
		dlg.Destroy()
		return self.quickKeys.SetFocus()

	@staticmethod
	def askCreateQuickLaunch():
		gui.messageBox(
			_("Please create or select a quick launch first"),
			"%s – %s" % (addonName, _("Error")),
			wx.OK | wx.ICON_ERROR,
		)


class AdvancedDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("Advanced")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.fixCursorPositions = sHelper.addItem(
			wx.CheckBox(
				self,
				label=_("Avoid &cursor positions issues with some characters such as variation selectors"),
			)
		)
		self.fixCursorPositions.SetValue(config.conf["brailleExtender"]["advanced"]["fixCursorPositions"])

		self.refreshForegroundObjNameChange = sHelper.addItem(
			wx.CheckBox(
				self,
				label="event_nameChange: "
				+ _("force the refresh of braille region related to &foreground object"),
			)
		)
		self.refreshForegroundObjNameChange.SetValue(
			config.conf["brailleExtender"]["advanced"]["refreshForegroundObjNameChange"]
		)

	def onSave(self):
		config.conf["brailleExtender"]["advanced"]["fixCursorPositions"] = self.fixCursorPositions.IsChecked()
		config.conf["brailleExtender"]["advanced"]["refreshForegroundObjNameChange"] = (
			self.refreshForegroundObjNameChange.IsChecked()
		)


class AddonSettingsDialog(gui.settingsDialogs.MultiCategorySettingsDialog):
	categoryClasses = [
		GeneralDlg,
		RotorDlg,
		AutoScrollDlg,
		SpeechHistorymodeDlg,
		DocumentFormattingDlg,
		ObjectPresentationDlg,
		BrailleTablesDlg,
		UndefinedCharsDlg,
		AdvancedInputModeDlg,
		OneHandModeDlg,
		RoleLabelsDlg,
		AdvancedDlg,
	]

	def __init__(self, parent, initialCategory=None):
		# Translators: title of add-on settings dialog.
		self.title = _("Braille Extender settings")
		super().__init__(parent, initialCategory)

	def makeSettings(self, settingsSizer):
		# Ensure that after the settings dialog is created the name is set correctly
		super().makeSettings(settingsSizer)
		self._doOnCategoryChange()
		global addonSettingsDialogWindowHandle
		addonSettingsDialogWindowHandle = self.GetHandle()

	def _doOnCategoryChange(self):
		global addonSettingsDialogActiveConfigProfile
		addonSettingsDialogActiveConfigProfile = config.conf.profiles[-1].name
		if not addonSettingsDialogActiveConfigProfile:
			# Translators: The profile name for normal configuration
			addonSettingsDialogActiveConfigProfile = _("normal configuration")
		self.SetTitle(self._getDialogTitle())

	def _getDialogTitle(self):
		return "{dialogTitle}: {panelTitle} ({configProfile})".format(
			dialogTitle=self.title,
			panelTitle=self.currentCategory.title,
			configProfile=addonSettingsDialogActiveConfigProfile,
		)

	def onCategoryChange(self, evt):
		super().onCategoryChange(evt)
		if evt.Skipped:
			return
		self._doOnCategoryChange()
