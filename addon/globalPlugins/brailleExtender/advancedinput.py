# coding: utf-8
# advancedinput.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush CLAUSE, released under GPL.
import codecs
import json
import os
from copy import deepcopy
from logHandler import log

import addonHandler
import brailleInput
import brailleTables
import config
import gui
import ui
import wx

from .common import configDir, addonName
from .utils import getTextInBraille

addonHandler.initTranslation()

PATH_DICT = os.path.join(configDir, "advancedInputMode.json")
NO_DUPLICATE = -1


class AdvancedInputDictEntry:

	def __init__(self, abreviation: str, replacement: str, table: str):
		self.abreviation = abreviation
		self.replacement = replacement
		self.table = table

	@property
	def abreviation(self):
		return self._abreviation

	@abreviation.setter
	def abreviation(self, abreviation):
		self._abreviation = abreviation

	@property
	def replacement(self):
		return self._replacement

	@replacement.setter
	def replacement(self, replacement):
		self._replacement = replacement

	@property
	def table(self):
		return self._table

	@table.setter
	def table(self, table):
		self._table = table

	def update(self, newEntry):
		if not isinstance(newEntry, AdvancedInputDictEntry):
			raise TypeError("entry: wrong type")
		self.abreviation = newEntry.abreviation
		self.replacement = newEntry.replacement
		self.table = newEntry.table

	def __repr__(self):
		return '(abreviation="{abreviation}", replacement="{replacement}", table="{table}")'.format(
			abreviation=self.abreviation, replacement=self.replacement, table=self.table)


class AdvancedInputDict:

	def __init__(self, entries=None):
		self.entries = []
		if entries:
			self.update(entries)

	def update(self, entries):
		for entry in entries:
			self._addEntry(entry)

	def _addEntry(self, entry):
		if isinstance(entry, dict):
			entryDict = AdvancedInputDictEntry(
				entry["abreviation"],
				entry["replacement"]
				if "replacement" in entry else entry["replaceBy"],
				entry["table"])
		elif isinstance(entry, AdvancedInputDictEntry):
			entryDict = entry
		else:
			log.error("entry: wrong type")
		self.addEntry(entryDict)

	def addEntry(self, newEntry):
		if not isinstance(newEntry, AdvancedInputDictEntry):
			raise TypeError("newEntry: wrong type")
		duplicateIndex = self.checkDuplicate(newEntry)
		if duplicateIndex != NO_DUPLICATE:
			self.entries[duplicateIndex].update(newEntry)
			return duplicateIndex
		self.entries.append(newEntry)
		self.sort()
		return self.entries.index(newEntry)

	def editEntry(self, editIndex, entry):
		self.entries[editIndex].update(entry)

	def removeEntry(self, entry):
		del self.entries[entry]

	def checkDuplicate(self, newEntry, excludedIndex=NO_DUPLICATE):
		for i, entry in enumerate(self.entries):
			if i == excludedIndex:
				continue
			if newEntry.abreviation == entry.abreviation and newEntry.table == entry.table:
				return i
		return NO_DUPLICATE

	def sort(self):
		self.entries = sorted(self.entries, key=lambda e: e.replacement)

	def getEntries(self):
		return self.entries

	def terminate(self):
		del self.entries
		del self


advancedInputDictHandler = None


def initialize():
	global advancedInputDictHandler
	advancedInputDictHandler = AdvancedInputDict()
	if not os.path.exists(PATH_DICT):
		return
	json_ = json.load(codecs.open(PATH_DICT, "r", "UTF-8"))
	advancedInputDictHandler.update(json_)


def terminate(save=False):
	global advancedInputDictHandler
	if save:
		saveDict(advancedInputDictHandler)
	advancedInputDictHandler.terminate()
	advancedInputDictHandler = None


def saveDict(dictToSave, fp=None):
	entries = [
		{
			"abreviation": entry.abreviation,
			"replacement": entry.replacement,
			"table": entry.table,
		}
		for entry in dictToSave.getEntries()
	]
	if not fp:
		fp = PATH_DICT
	with codecs.open(fp, "w", "UTF-8") as outfile:
		json.dump(entries, outfile, ensure_ascii=False, indent=2)


def getReplacements(abreviations, strict=False):
	if isinstance(abreviations, str):
		abreviations = [abreviations]
	currentInputTable = brailleInput.handler.table.fileName
	out = []
	for abreviation in abreviations:
		if abreviation.endswith("⠀"):
			strict = True
			abreviation = abreviation[:-1]
		if not strict:
			out += [
				entry
				for entry in advancedInputDictHandler.getEntries()
				if entry.abreviation.startswith(abreviation)
				and entry.table in [currentInputTable, '*']
			]
		else:
			out += [
				entry
				for entry in advancedInputDictHandler.getEntries()
				if entry.abreviation == abreviation
				and entry.table in [currentInputTable, '*']
			]
	return out


def translateTable(tableFilename, return_index=False):
	if tableFilename == '*':
		return 0 if return_index else _("Any (all tables)")
	for i, table in enumerate(brailleTables.listTables(), 1):
		if not table.input:
			continue
		if table.fileName == tableFilename:
			return i if return_index else table.displayName
	return tableFilename


class AdvancedInputModeDlg(gui.settingsDialogs.SettingsDialog):

	# Translators: title of a dialog.
	title = _("Advanced input mode dictionary")

	def makeSettings(self, settingsSizer):
		self.backupDict = deepcopy(advancedInputDictHandler)
		self.curDict = advancedInputDictHandler
		self.curDict.sort()
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: The label for the combo box of dictionary entries in
		# advanced input mode dictionary dialog.
		entriesLabelText = _("Dictionary &entries")
		self.dictList = sHelper.addLabeledControl(
			entriesLabelText,
			wx.ListCtrl,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
			size=(550, 350),
		)
		# Translators: The label for a column in dictionary entries list used
		# to identify comments for the entry.
		self.dictList.InsertColumn(0, _("Replacement"), width=150)
		self.dictList.InsertColumn(1, _("Input"), width=150)
		self.dictList.InsertColumn(2, _("Input table"), width=150)
		self.onSetEntries()
		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in advanced input mode
			# dictionariy dialog to add new entries.
			label=_("&Add"),
		).Bind(wx.EVT_BUTTON, self.onAddClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in advanced input mode
			# dictionariy dialog to edit existing entries.
			label=_("&Edit"),
		).Bind(wx.EVT_BUTTON, self.onEditClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in advanced input mode
			# dictionariy dialog to remove existing entries.
			label=_("Re&move"),
		).Bind(wx.EVT_BUTTON, self.onRemoveClick)

		sHelper.addItem(bHelper)
		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in advanced input mode
			# dictionariy dialog to save entries.
			label=_("&Save"),
		).Bind(wx.EVT_BUTTON, self.onSaveClick)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in advanced input mode
			# dictionariy dialog to open dictionary file in an editor.
			label=_("&Open the dictionary file in an editor"),
		).Bind(wx.EVT_BUTTON, self.onOpenFileClick)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in advanced input mode
			# dictionariy dialog to reload dictionary.
			label=_("&Reload the dictionary"),
		).Bind(wx.EVT_BUTTON, self.onReloadDictClick)
		sHelper.addItem(bHelper)

	def onSetEntries(self):
		self.dictList.DeleteAllItems()
		for entry in self.curDict.getEntries():
			self.dictList.Append(
				(entry.replacement,
				 entry.abreviation,
				 translateTable(
					 entry.table)))
		self.dictList.SetFocus()

	def _isValid(self, entryIndex=NO_DUPLICATE):
		duplicateIndex = self.curDict.checkDuplicate(self.entry, entryIndex)
		if duplicateIndex != NO_DUPLICATE:
			if self.entry.replacement == self.curDict.entries[duplicateIndex].replacement:
				msg = _("Don't get tired, this entry already exists!")
				gui.messageBox(msg, addonName, wx.OK | wx.ICON_INFORMATION)
				return True
			msg = _('The abreviation "{abreviation}" is already used for "{replacement}". Do you want to update the existing entry?').format(
				abreviation=self.entry.abreviation, replacement=self.curDict.entries[duplicateIndex].replacement)
			if gui.messageBox(msg, addonName, wx.YES_NO |
							  wx.ICON_INFORMATION) == wx.NO:
				return False
		return True

	def _postValidation(self, editIndex=NO_DUPLICATE):
		newIndex = editIndex
		if editIndex != NO_DUPLICATE:
			self.curDict.editEntry(editIndex, self.entry)
		else:
			newIndex = self.curDict.addEntry(self.entry)
		self.onSetEntries()
		self.dictList.Focus(newIndex)
		self.dictList.Select(newIndex)
		self.dictList.SetFocus()

	def onAddClick(self, event):
		entryDialog = DictionaryEntryDlg(self, title=_("Add Dictionary Entry"))
		while entryDialog.ShowModal() == wx.ID_OK:
			self.entry = entryDialog.dictEntry
			if not self._isValid():
				continue
			self._postValidation()
			entryDialog.Destroy()
			break

	def onEditClick(self, event):
		if self.dictList.GetSelectedItemCount() != 1:
			return ui.message(_("Please select an entry first"))
		editIndex = self.dictList.GetFirstSelected()
		entry = self.curDict.getEntries()[editIndex]
		entryDialog = DictionaryEntryDlg(self)
		entryDialog.abreviationTextCtrl.SetValue(entry.abreviation)
		entryDialog.replacementTextCtrl.SetValue(entry.replacement)
		entryDialog.table.SetSelection(translateTable(entry.table, True))
		while entryDialog.ShowModal() == wx.ID_OK:
			self.entry = entryDialog.dictEntry
			if not self._isValid(editIndex):
				continue
			self._postValidation(editIndex)
			entryDialog.Destroy()
			break

	def onRemoveClick(self, event):
		deleteIndex = self.dictList.GetFirstSelected()
		while deleteIndex >= 0:
			self.dictList.DeleteItem(deleteIndex)
			self.curDict.removeEntry(deleteIndex)
			deleteIndex = self.dictList.GetNextSelected(deleteIndex)
		self.dictList.SetFocus()

	def onSaveClick(self, evt):
		saveDict(self.curDict)
		self.backupDict = deepcopy(self.curDict)
		self.dictList.SetFocus()

	def onOpenFileClick(self, event):
		if not os.path.exists(PATH_DICT):
			return ui.message(_("File doesn't exist yet"))
		try:
			os.startfile(PATH_DICT)
		except OSError:
			os.popen('notepad "%s"' % dictPath)

	def onReloadDictClick(self, event):
		self.curDict.terminate()
		initialize()
		self.curDict = advancedInputDictHandler
		self.onSetEntries()

	def postInit(self):
		self.dictList.SetFocus()

	def onOk(self, evt):
		saveDict(self.curDict)
		super().onOk(evt)

	def onCancel(self, evt):
		global advancedInputDictHandler
		advancedInputDictHandler = self.backupDict
		super().onCancel(evt)


class DictionaryEntryDlg(wx.Dialog):

	# Translators: This is the label for the edit dictionary entry dialog.
	def __init__(self, parent=None, title=_("Edit Dictionary Entry")):
		super().__init__(parent, title=title)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: This is a label for an edit field in add dictionary
		# entry dialog.
		abreviationLabelText = _("&Abreviation:")
		self.abreviationTextCtrl = sHelper.addLabeledControl(
			abreviationLabelText, wx.TextCtrl
		)
		# Translators: This is a label for an edit field in add dictionary
		# entry dialog.
		replacementLabelText = _("&Replace by:")
		self.replacementTextCtrl = sHelper.addLabeledControl(
			replacementLabelText, wx.TextCtrl
		)

		label = _("Input table:")
		choices = [translateTable('*')]
		choices.extend([table.displayName for table in brailleTables.listTables() if table.input])
		self.table = sHelper.addLabeledControl(label, wx.Choice, choices=choices)
		self.table.SetSelection(0)

		sHelper.addDialogDismissButtons(
			self.CreateButtonSizer(wx.OK | wx.CANCEL))

		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.abreviationTextCtrl.SetFocus()
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)

	def onOk(self, evt):
		abreviation = self.abreviationTextCtrl.GetValue()
		replacement = self.replacementTextCtrl.GetValue()
		msg = None
		if not abreviation:
			msg = _('The abreviation field is empty, please enter something.')
			self.abreviationTextCtrl.SetFocus()
		if not replacement:
			msg = _('The remplacement field is empty, please enter something.')
			self.replacementTextCtrl.SetFocus()
		if msg:
			return gui.messageBox(msg, addonName, wx.OK | wx.ICON_ERROR)
		abreviation = getTextInBraille(abreviation)
		table = '*'
		idx = self.table.GetSelection()
		if idx > 0:
			table = [table.fileName for table in brailleTables.listTables() if table.input][idx-1]
		newEntry = AdvancedInputDictEntry(abreviation, replacement, table)
		self.dictEntry = newEntry
		evt.Skip()


class SettingsDlg(gui.settingsDialogs.SettingsPanel):

	# Translators: title of a dialog.
	title = _("Advanced input mode")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: label of a dialog.
		self.stopAdvancedInputModeAfterOneChar = sHelper.addItem(wx.CheckBox(
			self, label=_("E&xit the advanced input mode after typing one pattern")))
		self.stopAdvancedInputModeAfterOneChar.SetValue(
			config.conf["brailleExtender"]["advancedInputMode"]["stopAfterOneChar"])
		self.escapeSignUnicodeValue = sHelper.addLabeledControl(
			_("&Escape character for Unicode values input"),
			wx.TextCtrl,
			value=config.conf["brailleExtender"]["advancedInputMode"]
			["escapeSignUnicodeValue"],)
		

	def onSave(self):
		config.conf["brailleExtender"]["advancedInputMode"]["stopAfterOneChar"] = self.stopAdvancedInputModeAfterOneChar.IsChecked()
		s = self.escapeSignUnicodeValue.Value
		if s:
			config.conf["brailleExtender"]["advancedInputMode"][
				"escapeSignUnicodeValue"] = getTextInBraille(s[0])
