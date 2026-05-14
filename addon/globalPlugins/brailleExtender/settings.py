# coding: utf-8
# settings.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.

import os

import addonHandler
import braille
import brailleInput
import config
import controlTypes
import core
import gui
import inputCore
import queueHandler
import scriptHandler
import ui
import wx
from logHandler import log

from . import addoncfg
from . import utils
from .advancedinput import SettingsDlg as AdvancedInputModeDlg
from .common import (
	addonName, punctuationSeparator, RC_NORMAL, nvdaVersionAtLeast,
	NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING, NVDA_HAS_SPEAK_ON_ROUTING,
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

def notImplemented(msg='', style=wx.OK|wx.ICON_INFORMATION):
	if not msg: msg = _("Feature implementation is in progress. Thanks for your patience.")
	gui.messageBox(msg, _("Braille Extender"), wx.OK|wx.ICON_INFORMATION)

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
			itemToSelect = list(addoncfg.updateChannels.keys()).index(config.conf["brailleExtender"]["updateChannel"])
		else:
			itemToSelect = list(addoncfg.updateChannels.keys()).index(addoncfg.CHANNEL_stable)
		if not config.conf["brailleExtender"]["autoCheckUpdate"]: itemToSelect += len(addoncfg.updateChannels.keys())
		self.updateCheck.SetSelection(itemToSelect)

		# Translators: label of a dialog.
		self.speakScroll = sHelper.addLabeledControl(_("Say current line while &scrolling in:"), wx.Choice, choices=list(addoncfg.focusOrReviewChoices.values()))
		self.speakScroll.SetSelection(list(addoncfg.focusOrReviewChoices.keys()).index(config.conf["brailleExtender"]["speakScroll"]))
		if nvdaVersionAtLeast(2025, 1):
			sHelper.addItem(wx.StaticText(
				self,
				label=_(
					"NVDA 2025.1+ also has a global braille option, “Speak when navigating by line or paragraph”. "
					"Disable that NVDA option if you hear duplicate line announcements."
				),
			))

		# Translators: label of a dialog.
		self.stopSpeechScroll = sHelper.addItem(wx.CheckBox(self, label=_("Speech &interrupt when scrolling on same line")))
		self.stopSpeechScroll.SetValue(config.conf["brailleExtender"]["stopSpeechScroll"])
		if NVDA_HAS_INTERRUPT_SPEECH_WHILE_SCROLLING:
			self.stopSpeechScroll.Enable(False)
			sHelper.addItem(wx.StaticText(self, label=_("Use NVDA Braille settings → \"Interrupt speech while scrolling\" (since 2022.3)")))

		# Translators: label of a dialog.
		self.skipBlankLinesScroll = sHelper.addItem(wx.CheckBox(self, label=_("S&kip blank lines during text scrolling")))
		self.skipBlankLinesScroll.SetValue(config.conf["brailleExtender"]["skipBlankLinesScroll"])

		# Translators: label of a dialog.
		self.smartCapsLock = sHelper.addItem(wx.CheckBox(self, label=_("Smart Caps Loc&k")))
		self.smartCapsLock.SetValue(config.conf["brailleExtender"]["smartCapsLock"])

		# Translators: label of a dialog.
		self.stopSpeechUnknown = sHelper.addItem(wx.CheckBox(self, label=_("Speech i&nterrupt for unknown gestures")))
		self.stopSpeechUnknown.SetValue(config.conf["brailleExtender"]["stopSpeechUnknown"])

		# Translators: label of a dialog.
		self.speakRoutingTo = sHelper.addItem(wx.CheckBox(self, label=_("Announce character when &routing braille cursor")))
		self.speakRoutingTo.SetValue(config.conf["brailleExtender"]["speakRoutingTo"])
		if NVDA_HAS_SPEAK_ON_ROUTING:
			self.speakRoutingTo.Enable(False)
			sHelper.addItem(wx.StaticText(self, label=_("Use NVDA Braille settings → \"Speak character when routing cursor in text\" (since 2024.4)")))

		# Translators: label of a dialog.
		label = _("Routing cursors behavior in edit &fields:")
		self.routingCursorsEditFields = sHelper.addLabeledControl(label, wx.Choice, choices=list(addoncfg.routingCursorsEditFields_labels.values()))
		if config.conf["brailleExtender"]["routingCursorsEditFields"] in addoncfg.routingCursorsEditFields_labels:
			itemToSelect = list(addoncfg.routingCursorsEditFields_labels.keys()).index(config.conf["brailleExtender"]["routingCursorsEditFields"])
		else:
			itemToSelect = list(addoncfg.routingCursorsEditFields_labels.keys()).index(RC_NORMAL)
		self.routingCursorsEditFields.SetSelection(itemToSelect)

		self.reviewModeTerminal = sHelper.addItem(wx.CheckBox(self, label=_("Automatically Switch to review mode in &terminal windows (cmd, bash, PuTTY, PowerShell Maxima…)")))
		self.reviewModeTerminal.SetValue(config.conf["brailleExtender"]["reviewModeTerminal"])

		# Translators: label of a dialog.
		self.volumeChangeFeedback = sHelper.addLabeledControl(_("Announce &volume changes:"), wx.Choice, choices=list(addoncfg.outputMessage.values()))
		if config.conf["brailleExtender"]["volumeChangeFeedback"] in addoncfg.outputMessage:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(config.conf["brailleExtender"]["volumeChangeFeedback"])
		else:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(addoncfg.CHOICE_braille)
		self.volumeChangeFeedback.SetSelection(itemToSelect)

		# Translators: label of a dialog.
		self.modifierKeysFeedback = sHelper.addLabeledControl(_("Announce m&odifier key presses:"), wx.Choice, choices=list(addoncfg.outputMessage.values()))
		if config.conf["brailleExtender"]["modifierKeysFeedback"] in addoncfg.outputMessage:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(config.conf["brailleExtender"]["modifierKeysFeedback"])
		else:
			itemToSelect = list(addoncfg.outputMessage.keys()).index(addoncfg.CHOICE_braille)
		# Translators: label of a dialog.
		self.beepsModifiers = sHelper.addItem(wx.CheckBox(self, label=_("Play &beeps for modifier keys")))
		self.beepsModifiers.SetValue(config.conf["brailleExtender"]["beepsModifiers"])

		# Translators: label of a dialog.
		self.modifierKeysFeedback.SetSelection(itemToSelect)
		self.rightMarginCells = sHelper.addLabeledControl(_("&Right margin on cells for the active braille display"), gui.nvdaControls.SelectOnFocusSpinCtrl, min=0, max=100, initial=int(config.conf["brailleExtender"]["rightMarginCells_%s" % addoncfg.curBD]))
		if addoncfg.gesturesFileExists:
			lb = [k for k in instanceGP.getKeyboardLayouts()]
			# Translators: label of a dialog.
			self.KBMode = sHelper.addLabeledControl(_("Braille &keyboard configuration:"), wx.Choice, choices=lb)
			self.KBMode.SetSelection(addoncfg.getKeyboardLayout())

		# Translators: label of a dialog.
		self.reverseScrollBtns = sHelper.addItem(wx.CheckBox(self, label=_("&Reverse forward and back scroll buttons")))
		self.reverseScrollBtns.SetValue(config.conf["brailleExtender"]["reverseScrollBtns"])

		self.brailleDisplay1 = sHelper.addLabeledControl(_("Preferred &primary braille display:"), wx.Choice, choices=self.bds_v)
		driver_name = "last"
		if config.conf["brailleExtender"]["brailleDisplay1"] in self.bds_k:
			driver_name = config.conf["brailleExtender"]["brailleDisplay1"]
		self.brailleDisplay1.SetSelection(self.bds_k.index(driver_name))
		self.brailleDisplay2 = sHelper.addLabeledControl(_("Preferred &secondary braille display:"), wx.Choice, choices=self.bds_v)
		driver_name = "last"
		if config.conf["brailleExtender"]["brailleDisplay2"] in self.bds_k:
			driver_name = config.conf["brailleExtender"]["brailleDisplay2"]
		self.brailleDisplay2.SetSelection(self.bds_k.index(driver_name))

	def postInit(self): self.autoCheckUpdate.SetFocus()

	def onSave(self):
		updateCheckChoice = self.updateCheck.GetSelection()
		size = len(addoncfg.updateChannels.keys())
		config.conf["brailleExtender"]["autoCheckUpdate"] = updateCheckChoice < size
		config.conf["brailleExtender"]["updateChannel"] = list(addoncfg.updateChannels.keys())[updateCheckChoice % size]

		config.conf["brailleExtender"]["reviewModeTerminal"] = self.reviewModeTerminal.IsChecked()
		if self.reverseScrollBtns.IsChecked(): instanceGP.reverseScrollBtns()
		else: instanceGP.reverseScrollBtns(None, True)
		config.conf["brailleExtender"]["reverseScrollBtns"] = self.reverseScrollBtns.IsChecked()
		config.conf["brailleExtender"]["stopSpeechScroll"] = self.stopSpeechScroll.IsChecked()
		config.conf["brailleExtender"]["skipBlankLinesScroll"] = self.skipBlankLinesScroll.IsChecked()
		config.conf["brailleExtender"]["smartCapsLock"] = self.smartCapsLock.IsChecked()
		config.conf["brailleExtender"]["stopSpeechUnknown"] = self.stopSpeechUnknown.IsChecked()
		config.conf["brailleExtender"]["speakRoutingTo"] = self.speakRoutingTo.IsChecked()

		config.conf["brailleExtender"]["speakScroll"] = list(addoncfg.focusOrReviewChoices.keys())[self.speakScroll.GetSelection()]

		config.conf["brailleExtender"]["rightMarginCells_%s" % addoncfg.curBD] = self.rightMarginCells.Value
		config.conf["brailleExtender"]["brailleDisplay1"] = self.bds_k[self.brailleDisplay1.GetSelection()]
		config.conf["brailleExtender"]["brailleDisplay2"] = self.bds_k[self.brailleDisplay2.GetSelection()]
		if addoncfg.gesturesFileExists:
			config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD] = list(addoncfg.iniProfile["keyboardLayouts"].keys())[self.KBMode.GetSelection()]
		config.conf["brailleExtender"]["routingCursorsEditFields"] = list(addoncfg.routingCursorsEditFields_labels.keys())[self.routingCursorsEditFields.GetSelection()]
		config.conf["brailleExtender"]["volumeChangeFeedback"] = list(addoncfg.outputMessage.keys())[self.volumeChangeFeedback.GetSelection()]
		config.conf["brailleExtender"]["modifierKeysFeedback"] = list(addoncfg.outputMessage.keys())[self.modifierKeysFeedback.GetSelection()]
		config.conf["brailleExtender"]["beepsModifiers"] = self.beepsModifiers.IsChecked()


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
			_("Preferred &output braille tables:"),
			gui.nvdaControls.CustomCheckListBox,
			choices=outputChoices
		)
		self.outputTablesList.CheckedItems = [i for i, (fn, _dn) in enumerate(outputData) if fn in self.oTables]

		inputChoices = [t[1] for t in inputData]
		self.inputTablesList = sHelper.addLabeledControl(
			_("Preferred &input braille tables:"),
			gui.nvdaControls.CustomCheckListBox,
			choices=inputChoices
		)
		self.inputTablesList.CheckedItems = [i for i, (fn, _dn) in enumerate(inputData) if fn in self.iTables]

		lt = [_("Use the current input table")]
		for t in addoncfg.tables:
			if t.output and not t.contracted:
				lt.append(t[1])
		iSht = addoncfg.tablesUFN.index(config.conf["brailleExtender"]["inputTableShortcuts"]) + 1 if config.conf["brailleExtender"]["inputTableShortcuts"] in addoncfg.tablesUFN else 0
		self.inputTableShortcuts = sHelper.addLabeledControl(_("Input braille table for &keyboard shortcut keys:"), wx.Choice, choices=lt)
		self.inputTableShortcuts.SetSelection(iSht)

		postOutputFNs = [t[0] for t in addoncfg.tables if t.output]
		lt = [_('None')] + [t[1] for t in addoncfg.tables if t.output]
		postTableVal = config.conf["brailleExtender"]["postTable"]
		postIdx = postOutputFNs.index(postTableVal) + 1 if postTableVal in postOutputFNs else 0
		self.postTable = sHelper.addLabeledControl(_("&Secondary output table:"), wx.Choice, choices=lt)
		self.postTable.SetSelection(postIdx)

		self.tabSpace = sHelper.addItem(wx.CheckBox(self, label=_("Display &tabs as spaces")))
		self.tabSpace.SetValue(config.conf["brailleExtender"]["tabSpace"])

		self.tabSize = sHelper.addLabeledControl(_("&Spaces per tab for the active braille display:"), gui.nvdaControls.SelectOnFocusSpinCtrl, min=1, max=42, initial=int(config.conf["brailleExtender"]["tabSize_%s" % addoncfg.curBD]))

	def postInit(self):
		self.outputTablesList.SetFocus()

	def onSave(self):
		outputData = self._getOutputTablesData()
		inputData = self._getInputTablesData()
		self.oTables = {outputData[i][0] for i in range(self.outputTablesList.GetCount()) if self.outputTablesList.IsChecked(i)}
		self.iTables = {inputData[i][0] for i in range(self.inputTablesList.GetCount()) if self.inputTablesList.IsChecked(i)}

		config.conf["brailleExtender"]["outputTables"] = ','.join(sorted(self.oTables))
		config.conf["brailleExtender"]["inputTables"] = ','.join(sorted(self.iTables))
		config.conf["brailleExtender"]["inputTableShortcuts"] = addoncfg.tablesUFN[self.inputTableShortcuts.GetSelection() - 1] if self.inputTableShortcuts.GetSelection() > 0 else '?'
		addoncfg.loadPreferedTables()

		postOutputFNs = [t[0] for t in addoncfg.tables if t.output]
		postTableID = self.postTable.GetSelection()
		config.conf["brailleExtender"]["postTable"] = "None" if postTableID == 0 else postOutputFNs[postTableID - 1]
		if self.tabSpace.IsChecked() and config.conf["brailleExtender"]["tabSpace"] != self.tabSpace.IsChecked():
			restartRequired = True
		else: restartRequired = False
		config.conf["brailleExtender"]["tabSpace"] = self.tabSpace.IsChecked()
		config.conf["brailleExtender"]["tabSize_%s" % addoncfg.curBD] = self.tabSize.Value
		if restartRequired:
			res = gui.messageBox(
				_("NVDA must be restarted for changes to take effect. Would you like to restart now?"),
				_("Braille Extender"),
				style=wx.YES_NO|wx.ICON_INFORMATION
			)
			if res == wx.YES: core.restart()

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
		self.quickKeys = sHelper.addLabeledControl(_("&Gestures:"), wx.Choice, choices=self.getQuickLaunchList())
		self.quickKeys.SetSelection(0)
		self.quickKeys.Bind(wx.EVT_CHOICE, self.onQuickKeys)
		self.target = sHelper.addLabeledControl(_("&Location (file path, URL or command)"), wx.TextCtrl, value=self.quickLaunchLocations[0] if self.quickLaunchLocations != [] else '')
		self.target.Bind(wx.EVT_TEXT, self.onTarget)
		self.browseBtn = bHelper1.addButton(self, wx.ID_ANY, _("&Browse..."), wx.DefaultPosition)
		self.removeGestureBtn = bHelper1.addButton(self, wx.ID_ANY, _("&Remove this gesture"), wx.DefaultPosition)
		self.addGestureBtn = bHelper1.addButton(self, wx.ID_ANY, _("&Add a quick launch"), wx.DefaultPosition)
		self.browseBtn.Bind(wx.EVT_BUTTON, self.onBrowseBtn)
		self.removeGestureBtn.Bind(wx.EVT_BUTTON, self.onRemoveGestureBtn)
		self.addGestureBtn.Bind(wx.EVT_BUTTON, self.onAddGestureBtn)
		sHelper.addItem(bHelper1)

	def postInit(self): self.quickKeys.SetFocus()

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
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Unable to associate this gesture. Please enter another gesture"))
				return False
			if gesture.isModifier: return False
			if gesture.normalizedIdentifiers[0].startswith("kb") and not gesture.normalizedIdentifiers[0].endswith(":escape"):
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _(f"Please enter a gesture from your {addoncfg.curBD} braille display. Press space to cancel."))
				return False
			if gesture.normalizedIdentifiers[0].endswith(":space"):
				inputCore.manager._captureFunc = None
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Out of capture"))
			elif not gesture.normalizedIdentifiers[0].endswith(":escape"):
				self.quickLaunchGestures.append(gesture.normalizedIdentifiers[0])
				self.quickLaunchLocations.append('')
				self.quickKeys.SetItems(self.getQuickLaunchList())
				self.quickKeys.SetSelection(len(self.quickLaunchGestures)-1)
				self.onQuickKeys(None)
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("The gesture captured is %s") % utils.format_gesture_identifiers(gesture.normalizedIdentifiers[0]))
				inputCore.manager._captureFunc = None
				self.captureEnabled = False
				self.addGestureBtn.SetLabel(self.captureLabelBtn)
				self.target.SetFocus()
			return True
		inputCore.manager._captureFunc = getCaptured

	def getQuickLaunchList(s):
		quickLaunchGesturesKeys = list(s.quickLaunchGestures)
		return ['%s%s: %s' % (utils.format_gesture_identifiers(quickLaunchGesturesKeys[i]), punctuationSeparator, v) for i, v in enumerate(s.quickLaunchLocations)]

	def onRemoveGestureBtn(self, event):
		if self.quickKeys.GetSelection() < 0:
			self.askCreateQuickLaunch()
			return
		def askConfirmation():
			choice = gui.messageBox(_("Are you sure you wish to delete this shortcut?"), '%s – %s' % (addonName, _("Remove shortcut")), wx.YES_NO|wx.ICON_QUESTION)
			if choice == wx.YES: confirmed()
		def confirmed():
			i = self.quickKeys.GetSelection()
			g = self.quickLaunchGestures.pop(i)
			self.quickLaunchLocations.pop(i)
			listQuickLaunches = self.getQuickLaunchList()
			self.quickKeys.SetItems(listQuickLaunches)
			if len(listQuickLaunches) > 0: self.quickKeys.SetSelection(i-1 if i > 0 else 0)
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _(f'{g} removed'))
			self.onQuickKeys(None)
		wx.CallAfter(askConfirmation)
		self.quickKeys.SetFocus()

	def onAddGestureBtn(self, event):
		if self.captureEnabled:
			self.captureEnabled = False
			self.addGestureBtn.SetLabel(self.captureLabelBtn)
			return
		self.captureNow()
		queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Please enter the desired gesture for the new quick launch. Press \"space bar\" to cancel"))
		self.captureEnabled=True
		self.captureLabelBtn = self.addGestureBtn.GetLabel()
		self.addGestureBtn.SetLabel(_("Don't add a quick launch"))
		return

	def onTarget(self, event):
		oldS = self.quickKeys.GetSelection()
		if oldS < 0:
			self.target.SetValue('')
			return
		self.quickLaunchLocations[self.quickKeys.GetSelection()] = self.target.GetValue()
		self.quickKeys.SetItems(self.getQuickLaunchList())
		self.quickKeys.SetSelection(oldS)

	def onQuickKeys(self, event):
		if self.quickKeys.GetSelection() < 0:
			self.target.SetValue('')
			return
		if not self.quickKeys.GetStringSelection().strip().startswith(':'):
			self.target.SetValue(self.quickKeys.GetStringSelection().split(': ')[1])
		else: self.target.SetValue('')
		return

	def onBrowseBtn(self, event):
		oldS = self.quickKeys.GetSelection()
		if oldS < 0:
			self.askCreateQuickLaunch()
			return
		dlg = wx.FileDialog(None, _("Choose a file for {0}").format(self.quickLaunchGestures[self.quickKeys.GetSelection()]), "%PROGRAMFILES%", "", "*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return self.quickKeys.SetFocus()
		self.target.SetValue(dlg.GetDirectory() + '\\' + dlg.GetFilename())
		self.quickLaunchLocations[self.quickKeys.GetSelection()] = dlg.GetDirectory() + '\\' + dlg.GetFilename()
		self.quickKeys.SetItems(self.getQuickLaunchList())
		self.quickKeys.SetSelection(oldS)
		dlg.Destroy()
		return self.quickKeys.SetFocus()

	@staticmethod
	def askCreateQuickLaunch():
		gui.messageBox(_("Please create or select a quick launch first"), '%s – %s' % (addonName, _("Error")), wx.OK|wx.ICON_ERROR)


class AdvancedDlg(gui.settingsDialogs.SettingsPanel):

	# Translators: title of a dialog.
	title = _("Advanced")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.fixCursorPositions = sHelper.addItem(wx.CheckBox(self, label=_("Avoid &cursor positions issues with some characters such as variation selectors")))
		self.fixCursorPositions.SetValue(config.conf["brailleExtender"]["advanced"]["fixCursorPositions"])

		self.refreshForegroundObjNameChange = sHelper.addItem(wx.CheckBox(self, label="event_nameChange: " + _("force the refresh of braille region related to &foreground object")))
		self.refreshForegroundObjNameChange.SetValue(config.conf["brailleExtender"]["advanced"]["refreshForegroundObjNameChange"])

	def onSave(self):
		config.conf["brailleExtender"]["advanced"]["fixCursorPositions"] = self.fixCursorPositions.IsChecked()
		config.conf["brailleExtender"]["advanced"]["refreshForegroundObjNameChange"] = self.refreshForegroundObjNameChange.IsChecked()


class AddonSettingsDialog(gui.settingsDialogs.MultiCategorySettingsDialog):
	categoryClasses=[
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
			configProfile=addonSettingsDialogActiveConfigProfile
		)

	def onCategoryChange(self,evt):
		super().onCategoryChange(evt)
		if evt.Skipped:
			return
		self._doOnCategoryChange()
