# coding: utf-8
# settings.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.

import hashlib
import json
import os

import addonHandler
import braille
import config
import controlTypes
import core
import glob
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
from .common import addonName, baseDir, punctuationSeparator, RC_NORMAL
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
	bds_k = [k for k, v in addoncfg.getValidBrailleDisplayPrefered()]
	bds_v = [v for k, v in addoncfg.getValidBrailleDisplayPrefered()]

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

		# Translators: label of a dialog.
		self.stopSpeechScroll = sHelper.addItem(wx.CheckBox(self, label=_("Speech &interrupt when scrolling on same line")))
		self.stopSpeechScroll.SetValue(config.conf["brailleExtender"]["stopSpeechScroll"])

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

		# Translators: label of a dialog.
		label = _("Routing cursors behavior in edit &fields:")
		self.routingCursorsEditFields = sHelper.addLabeledControl(label, wx.Choice, choices=list(addoncfg.routingCursorsEditFields_labels.values()))
		if config.conf["brailleExtender"]["routingCursorsEditFields"] in addoncfg.routingCursorsEditFields_labels:
			itemToSelect = list(addoncfg.routingCursorsEditFields_labels.keys()).index(config.conf["brailleExtender"]["routingCursorsEditFields"])
		else:
			itemToSelect = list(addoncfg.routingCursorsEditFields_labels.keys()).index(RC_NORMAL)
		self.routingCursorsEditFields.SetSelection(itemToSelect)

		# Translators: label of a dialog.
		self.hourDynamic = sHelper.addItem(wx.CheckBox(self, label=_("&Display time and date infinitely")))
		self.hourDynamic.SetValue(config.conf["brailleExtender"]["hourDynamic"])
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

		config.conf["brailleExtender"]["hourDynamic"] = self.hourDynamic.IsChecked()
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
			config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD] = addoncfg.iniProfile["keyboardLayouts"].keys()[self.KBMode.GetSelection()]
		config.conf["brailleExtender"]["routingCursorsEditFields"] = list(addoncfg.routingCursorsEditFields_labels.keys())[self.routingCursorsEditFields.GetSelection()]
		config.conf["brailleExtender"]["volumeChangeFeedback"] = list(addoncfg.outputMessage.keys())[self.volumeChangeFeedback.GetSelection()]
		config.conf["brailleExtender"]["modifierKeysFeedback"] = list(addoncfg.outputMessage.keys())[self.modifierKeysFeedback.GetSelection()]
		config.conf["brailleExtender"]["beepsModifiers"] = self.beepsModifiers.IsChecked()


class BrailleTablesDlg(gui.settingsDialogs.SettingsPanel):

	# Translators: title of a dialog.
	title = _("Braille tables")

	def makeSettings(self, settingsSizer):
		self.oTables = set(addoncfg.outputTables)
		self.iTables = set(addoncfg.inputTables)
		lt = [_("Use the current input table")]
		for table in addoncfg.tables:
			if table.output and not table.contracted: lt.append(table[1])
			if config.conf["brailleExtender"]["inputTableShortcuts"] in addoncfg.tablesUFN:
				iSht = addoncfg.tablesUFN.index(config.conf["brailleExtender"]["inputTableShortcuts"]) + 1
			else: iSht = 0
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		bHelper1 = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)

		self.tables = sHelper.addLabeledControl(_("Prefered braille &tables (press F1 for help):"), wx.Choice, choices=self.getTablesWithSwitches())
		self.tables.SetSelection(0)
		self.tables.Bind(wx.EVT_CHAR, self.onTables)

		self.inputTableShortcuts = sHelper.addLabeledControl(_("Input braille table for &keyboard shortcut keys:"), wx.Choice, choices=lt)
		self.inputTableShortcuts.SetSelection(iSht)
		lt = [_('None')]
		for table in addoncfg.tables:
			if table.output: lt.append(table[1])
		self.postTable = sHelper.addLabeledControl(_("&Secondary output table:"), wx.Choice, choices=lt)
		self.postTable.SetSelection(addoncfg.tablesFN.index(config.conf["brailleExtender"]["postTable"]) if config.conf["brailleExtender"]["postTable"] in addoncfg.tablesFN else 0)

		# Translators: label of a dialog.
		self.tabSpace = sHelper.addItem(wx.CheckBox(self, label=_("Display &tabs as spaces")))
		self.tabSpace.SetValue(config.conf["brailleExtender"]["tabSpace"])

		# Translators: label of a dialog.
		self.tabSize = sHelper.addLabeledControl(_("&Spaces per tab for the active braille display:"), gui.nvdaControls.SelectOnFocusSpinCtrl, min=1, max=42, initial=int(config.conf["brailleExtender"]["tabSize_%s" % addoncfg.curBD]))
		self.customBrailleTablesBtn = bHelper1.addButton(self, wx.NewId(), _("Alternative and &custom braille tables..."), wx.DefaultPosition)
		self.customBrailleTablesBtn.Bind(wx.EVT_BUTTON, self.onCustomBrailleTablesBtn)
		sHelper.addItem(bHelper1)

	def postInit(self): self.tables.SetFocus()

	def onSave(self):
		config.conf["brailleExtender"]["outputTables"] = ','.join(self.oTables)
		config.conf["brailleExtender"]["inputTables"] = ','.join(self.iTables)
		config.conf["brailleExtender"]["inputTableShortcuts"] = addoncfg.tablesUFN[self.inputTableShortcuts.GetSelection() - 1] if self.inputTableShortcuts.GetSelection() > 0 else '?'
		addoncfg.loadPreferedTables()
		postTableID = self.postTable.GetSelection()
		postTable = "None" if postTableID == 0 else addoncfg.tablesFN[postTableID]
		config.conf["brailleExtender"]["postTable"] = postTable
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

	def getTablesWithSwitches(self):
		out = []
		for i, tbl in enumerate(addoncfg.tablesTR):
			out.append("%s%s: %s" % (tbl, punctuationSeparator, self.getInSwitchesText(addoncfg.tablesFN[i])))
		return out

	def getCurrentSelection(self):
		idx = self.tables.GetSelection()
		tbl = addoncfg.tablesFN[self.tables.GetSelection()]
		return idx, tbl

	def setCurrentSelection(self, tbl, newLoc):
		if newLoc == "io":
			self.iTables.add(tbl)
			self.oTables.add(tbl)
		elif newLoc == "i":
			self.iTables.add(tbl)
			self.oTables.discard(tbl)
		elif newLoc == "o":
			self.oTables.add(tbl)
			self.iTables.discard(tbl)
		elif newLoc == "n":
			self.iTables.discard(tbl)
			self.oTables.discard(tbl)

	def inSwitches(self, tbl):
		inp = tbl in self.iTables
		out = tbl in self.oTables
		return [inp, out]

	def getInSwitchesText(self, tbl):
		inS = self.inSwitches(tbl)
		if all(inS): inSt = _("input and output")
		elif not any(inS): inSt = _("none")
		elif inS[0]: inSt = _("input only")
		elif inS[1]: inSt = _("output only")
		return inSt

	def changeSwitch(self, tbl, direction=1, loop=True):
		dirs = ['n', 'i', 'o', "io"]
		iCurDir = 0
		inS = self.inSwitches(tbl)
		if all(inS): iCurDir = dirs.index("io")
		elif not any(inS): iCurDir = dirs.index('n')
		elif inS[0]: iCurDir = dirs.index('i')
		elif inS[1]: iCurDir = dirs.index('o')

		if len(dirs)-1 == iCurDir and direction == 1 and loop: newDir = dirs[0]
		elif iCurDir == 0 and direction == 0 and loop: newDir = dirs[-1]
		elif iCurDir < len(dirs)-1 and direction == 1: newDir = dirs[iCurDir+1]
		elif iCurDir > 0 and iCurDir < len(dirs) and direction == 0: newDir = dirs[iCurDir-1]
		else: return
		self.setCurrentSelection(tbl, newDir)

	def onCustomBrailleTablesBtn(self, evt):
		customBrailleTablesDlg = CustomBrailleTablesDlg(self, multiInstanceAllowed=True)
		customBrailleTablesDlg.ShowModal()

	def onTables(self, evt):
		keycode = evt.GetKeyCode()
		if keycode in [ord(','), ord(';')]:
			idx, tbl = self.getCurrentSelection()
			if keycode == ord(','):
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, "%s" % tbl)
			else:
				ui.browseableMessage('\n'.join([
					_("Table name: %s") % addoncfg.tablesTR[idx],
					_("File name: %s") % tbl,
					_("In switches: %s") % self.getInSwitchesText(tbl)
					]), _("About this table"), False)
		if keycode == wx.WXK_F1:
			ui.browseableMessage(
				_("""Braille tables usable from NVDA are listed. Press space, left arrow, or right arrow keys to include (or exclude) the selected table in switches.\n
			You can also press 'comma' key to get the file name of the selected table, and 'semicolon' key to view miscellaneous information on the selected table."""),
			_("Contextual help"), False)
		if keycode in [wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_SPACE]:
			idx, tbl = self.getCurrentSelection()
			if keycode == wx.WXK_LEFT: self.changeSwitch(tbl, 0, False)
			elif keycode == wx.WXK_RIGHT: self.changeSwitch(tbl, 1, False)
			elif keycode == wx.WXK_SPACE: self.changeSwitch(tbl, 1, True)
			newSwitch = self.getInSwitchesText(tbl)
			self.tables.SetString(self.tables.GetSelection(), "%s%s: %s" % (addoncfg.tablesTR[idx], punctuationSeparator, newSwitch))
			queueHandler.queueFunction(queueHandler.eventQueue, ui.message, "%s" % newSwitch)
			utils.refreshBD()
		else: evt.Skip()


class CustomBrailleTablesDlg(gui.settingsDialogs.SettingsDialog):

	# Translators: title of a dialog.
	title = "Braille Extender - %s" % _("Custom braille tables")
	providedTablesPath = "%s/res/brailleTables.json" % baseDir
	userTablesPath = "%s/brailleTables.json" % addoncfg.configDir

	def makeSettings(self, settingsSizer):
		self.providedTables = self.getBrailleTablesFromJSON(self.providedTablesPath)
		self.userTables = self.getBrailleTablesFromJSON(self.userTablesPath)
		wx.CallAfter(notImplemented)
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		bHelper1 = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.inTable = sHelper.addItem(wx.CheckBox(self, label=_("Use a custom table as &input table")))
		self.outTable = sHelper.addItem(wx.CheckBox(self, label=_("Use a custom table as &output table")))
		self.addBrailleTablesBtn = bHelper1.addButton(self, wx.NewId(), _("&Add a braille table..."), wx.DefaultPosition)
		self.addBrailleTablesBtn.Bind(wx.EVT_BUTTON, self.onAddBrailleTablesBtn)
		sHelper.addItem(bHelper1)

	@staticmethod
	def getBrailleTablesFromJSON(path):
		if not os.path.exists(path):
			path = "%s/%s" % (baseDir, path)
			if not os.path.exists(path): return {}
		f = open(path)
		return json.load(f)

	def onAddBrailleTablesBtn(self, evt):
		addBrailleTablesDlg = AddBrailleTablesDlg(self, multiInstanceAllowed=True)
		addBrailleTablesDlg.ShowModal()

	def postInit(self): self.inTable.SetFocus()

	def onOk(self, event):
		super().onOk(evt)


class AddBrailleTablesDlg(gui.settingsDialogs.SettingsDialog):
	# Translators: title of a dialog.
	title = "Braille Extender - %s" % _("Add a braille table")
	tbl = []

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		bHelper1 = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.name = sHelper.addLabeledControl(_("Display &name"), wx.TextCtrl)
		self.description = sHelper.addLabeledControl(_("&Description"), wx.TextCtrl, style = wx.TE_MULTILINE|wx.TE_PROCESS_ENTER, size = (360, 90), pos=(-1,-1))
		self.path = sHelper.addLabeledControl(_("&Path"), wx.TextCtrl)
		self.browseBtn = bHelper1.addButton(self, wx.NewId(), _("&Browse..."), wx.DefaultPosition)
		self.browseBtn.Bind(wx.EVT_BUTTON, self.onBrowseBtn)
		sHelper.addItem(bHelper1)
		self.isContracted = sHelper.addItem(wx.CheckBox(self, label=_("This is a &contracted (grade 2) braille table")))
		# Translators: label of a dialog.
		self.inputOrOutput = sHelper.addLabeledControl(_("&Available for:"), wx.Choice, choices=[_("Input and output"), _("Input only"), _("Output only")])
		self.inputOrOutput.SetSelection(0)

	def postInit(self): self.name.SetFocus()

	def onBrowseBtn(self, event):
		dlg = wx.FileDialog(None, _("Choose a braille table file"), "%PROGRAMFILES%", "", "%s (*.ctb, *.cti, *.utb, *.uti)|*.ctb;*.cti;*.utb;*.uti" % _("Liblouis table files"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return self.path.SetFocus()
		self.path.SetValue(dlg.GetDirectory() + '\\' + dlg.GetFilename())
		dlg.Destroy()
		self.path.SetFocus()

	def onOk(self, event):
		path = self.path.GetValue().strip().encode("UTF-8")
		displayName = self.name.GetValue().strip()
		if not displayName:
			gui.messageBox(_("Please specify a display name."), _("Invalid display name"), wx.OK|wx.ICON_ERROR)
			self.name.SetFocus()
			return
		if not os.path.exists(path.decode("UTF-8").encode("mbcs")):
			gui.messageBox(_("The specified path is not valid (%s).") % path.decode("UTF-8"), _("Invalid path"), wx.OK|wx.ICON_ERROR)
			self.path.SetFocus()
			return
		switch_possibleValues = ["both", "input", "output"]
		v = "%s|%s|%s|%s" % (
			switch_possibleValues[self.inputOrOutput.GetSelection()],
			self.isContracted.IsChecked(), path.decode("UTF-8"), displayName
		)
		k = hashlib.md5(path).hexdigest()[:15]
		config.conf["brailleExtender"]["brailleTables"][k] = v
		super().onOk(evt)

	@staticmethod
	def getAvailableBrailleTables():
		out = []
		brailleTablesDir = addoncfg.brailleTables.TABLES_DIR
		ls = glob.glob(brailleTablesDir+'\\*.ctb')+glob.glob(brailleTablesDir+'\\*.cti')+glob.glob(brailleTablesDir+'\\*.utb')
		for i, e in enumerate(ls):
			e = str(e.split('\\')[-1])
			if e in addoncfg.tablesFN or e.lower() in addoncfg.tablesFN: del ls[i]
			else: out.append(e.lower())
		out = sorted(out)
		return out


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
		self.browseBtn = bHelper1.addButton(self, wx.NewId(), _("&Browse..."), wx.DefaultPosition)
		self.removeGestureBtn = bHelper1.addButton(self, wx.NewId(), _("&Remove this gesture"), wx.DefaultPosition)
		self.addGestureBtn = bHelper1.addButton(self, wx.NewId(), _("&Add a quick launch"), wx.DefaultPosition)
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
				queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("The gesture captured is %s") % utils.beautifulSht(gesture.normalizedIdentifiers[0]))
				inputCore.manager._captureFunc = None
				self.captureEnabled = False
				self.addGestureBtn.SetLabel(self.captureLabelBtn)
				self.target.SetFocus()
			return True
		inputCore.manager._captureFunc = getCaptured

	def getQuickLaunchList(s):
		quickLaunchGesturesKeys = list(s.quickLaunchGestures)
		return ['%s%s: %s' % (utils.beautifulSht(quickLaunchGesturesKeys[i]), punctuationSeparator, v) for i, v in enumerate(s.quickLaunchLocations)]

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

	def onSave(self):
		config.conf["brailleExtender"]["advanced"]["fixCursorPositions"] = self.fixCursorPositions.IsChecked()


class AddonSettingsDialog(gui.settingsDialogs.MultiCategorySettingsDialog):
	categoryClasses=[
		GeneralDlg,
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
