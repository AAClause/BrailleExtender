# coding: utf-8
# tabledictionaries.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.

import os.path
import re
import unicodedata
from collections import namedtuple

import addonHandler
import braille
import config
import gui
import louis
import wx
from logHandler import log

from . import tablegroups

addonHandler.initTranslation()

from .common import configDir
from . import huc

dictTables = []
TableDictEntry = namedtuple(
	"TableDictEntry", ("opcode", "textPattern", "braillePattern", "direction", "comment"))
OPCODE_SIGN = "sign"
OPCODE_MATH = "math"
OPCODE_REPLACE = "replace"
OPCODE_LABELS = {
	# Translators: This is a label for an Entry Type radio button in add dictionary entry dialog.
	OPCODE_SIGN: _("Sign"),
	# Translators: This is a label for an Entry Type radio button in add dictionary entry dialog.
	OPCODE_MATH: _("Math"),
	# Translators: This is a label for an Entry Type radio button in add dictionary entry dialog.
	OPCODE_REPLACE: _("Replace"),
}
OPCODE_LABELS_ORDERING = (OPCODE_SIGN, OPCODE_MATH, OPCODE_REPLACE)

DIRECTION_BOTH = "both"
DIRECTION_BACKWARD = "nofor"
DIRECTION_FORWARD = "noback"
DIRECTION_LABELS = {
	DIRECTION_BOTH: _("Both (input and output)"),
	DIRECTION_BACKWARD: _("Backward (input only)"),
	DIRECTION_FORWARD: _("Forward (output only)")
}
DIRECTION_LABELS_ORDERING = (
	DIRECTION_BOTH, DIRECTION_FORWARD, DIRECTION_BACKWARD)

inputTables = []
outputTables = []
invalidTables = set()


def checkTable(path):
	global invalidTables
	tablesString = b",".join(
		[x.encode("mbcs") if isinstance(x, str) else bytes(x) for x in [path]])
	if not louis.liblouis.lou_checkTable(tablesString):
		log.error("Can't compile: tables %s" % path)
		invalidTables.add(path)
		return False
	return True


def getValidPathsDict(usageIn):
	types = ["tmp", "table", "default"]
	paths = [getPathDict(type_, usageIn) for type_ in types]
	def valid(path): return os.path.exists(
		path) and os.path.isfile(path) and checkTable(path)
	return [path for path in paths if valid(path)]


def getPathDict(type_, usageIn="io"):
	groupEnabled = tablegroups.groupEnabled()
	g = tablegroups.getGroup(usageIn=usageIn)
	table = os.path.join(configDir, "brailleDicts", config.conf["braille"]["inputTable"]
						 ) if usageIn == tablegroups.USAGE_INPUT else config.conf["braille"]["translationTable"]
	if type_ == "table":
		if groupEnabled and g and g.members:
			if len(g.members) == 1:
				path = os.path.join(configDir, "brailleDicts", g.members[0])
			else:
				path = ''
		else:
			path = os.path.join(configDir, "brailleDicts", table)
	elif type_ == "tmp":
		path = os.path.join(configDir, "brailleDicts", "tmp")
	else:
		if groupEnabled and g and g.members:
			if len(g.members) == 1:
				path = os.path.join(configDir, "brailleDicts", "default")
			else:
				path = ''
		else:
			path = os.path.join(configDir, "brailleDicts", "default")
	return f"{path}.cti"


def getDictionary(type_):
	path = getPathDict(type_)
	if not os.path.exists(path):
		return False, []
	out = []
	with open(path, "rb") as f:
		for line in f:
			line = line.decode("UTF-8")
			line = line.replace(" ", "	").replace(
				"		", "	").replace("		", "	").strip().split("	", 4)
			if line[0].lower().strip() not in [DIRECTION_BACKWARD, DIRECTION_FORWARD]:
				line.insert(0, DIRECTION_BOTH)
			if len(line) < 4:
				if line[1] == "replace" and len(line) == 3:
					line.append("")
				else:
					continue
			if len(line) == 4:
				line.append("")
			out.append(TableDictEntry(
				line[1], line[2], line[3], line[0], ' '.join(line[4:]).replace("	", " ")))
	return True, out


def saveDict(type_, dict_):
	path = getPathDict(type_)
	f = open(path, "wb")
	for entry in dict_:
		direction = entry.direction if entry.direction != "both" else ''
		line = ("%s	%s	%s	%s	%s" % (direction, entry.opcode, entry.textPattern,
									entry.braillePattern, entry.comment)).strip()+"\n"
		f.write(line.encode("UTF-8"))
	f.write(b'\n')
	f.close()
	return True


def setDictTables():
	global inputTables, outTable
	inputTables = getValidPathsDict(tablegroups.USAGE_INPUT)
	outputTables = getValidPathsDict(tablegroups.USAGE_OUTPUT)
	invalidTables.clear()


def notifyInvalidTables():
	if invalidTables:
		dicts = {
			getPathDict("default"): "default",
			getPathDict("table"): "table",
			getPathDict("tmp"): "tmp"
		}
		msg = _("One or more errors are present in dictionary tables: %s. As a result, these dictionaries were not loaded.") % ", ".join(
			[dicts[path] for path in invalidTables if path in dicts])
		wx.CallAfter(gui.messageBox, msg, _(
			"Braille Extender"), wx.OK | wx.ICON_ERROR)


def removeTmpDict():
	path = getPathDict("tmp")
	if os.path.exists(path):
		os.remove(path)


class DictionaryDlg(gui.settingsDialogs.SettingsDialog):

	def __init__(self, parent, title, type_):
		self.title = title
		self.type_ = type_
		self.tmpDict = getDictionary(type_)[1]
		super().__init__(parent, hasApplyButton=True)

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: The label for the combo box of dictionary entries in table dictionary dialog.
		entriesLabelText = _("Dictionary &entries")
		self.dictList = sHelper.addLabeledControl(
			entriesLabelText, wx.ListCtrl, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(550, 350))
		# Translators: The label for a column in dictionary entries list used to identify comments for the entry.
		self.dictList.InsertColumn(0, _("Comment"), width=150)
		# Translators: The label for a column in dictionary entries list used to identify original character.
		self.dictList.InsertColumn(1, _("Pattern"), width=150)
		# Translators: The label for a column in dictionary entries list and in a list of symbols from symbol pronunciation dialog used to identify replacement for a pattern or a symbol
		self.dictList.InsertColumn(2, _("Representation"), width=150)
		# Translators: The label for a column in dictionary entries list used to identify whether the entry is a sign, math, replace
		self.dictList.InsertColumn(4, _("Opcode"), width=50)
		# Translators: The label for a column in dictionary entries list used to identify whether the entry is a sign, math, replace
		self.dictList.InsertColumn(5, _("Direction"), width=50)
		self.onSetEntries()
		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table dictionaries dialog to add new entries.
			label=_("&Add")
		).Bind(wx.EVT_BUTTON, self.onAddClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table dictionaries dialog to edit existing entries.
			label=_("&Edit")
		).Bind(wx.EVT_BUTTON, self.onEditClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table dictionaries dialog to remove existing entries.
			label=_("Re&move")
		).Bind(wx.EVT_BUTTON, self.onRemoveClick)

		sHelper.addItem(bHelper)
		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table dictionaries dialog to open dictionary file in an editor.
			label=_("&Open the current dictionary file in an editor")
		).Bind(wx.EVT_BUTTON, self.onOpenFileClick)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table dictionaries dialog to reload dictionary.
			label=_("&Reload the dictionary")
		).Bind(wx.EVT_BUTTON, self.onReloadDictClick)
		sHelper.addItem(bHelper)

	def postInit(self):
		self.dictList.SetFocus()

	def onSetEntries(self, evt=None):
		self.dictList.DeleteAllItems()
		for entry in self.tmpDict:
			direction = DIRECTION_LABELS[entry[3]] if len(
				entry) >= 4 and entry[3] in DIRECTION_LABELS else "both"
			self.dictList.Append((
				entry.comment,
				self.getReprTextPattern(entry.textPattern),
				self.getReprBraillePattern(entry.braillePattern),
				entry.opcode,
				direction
			))
		self.dictList.SetFocus()

	def onOpenFileClick(self, evt):
		dictPath = getPathDict(self.type_)
		if not os.path.exists(dictPath):
			return
		try:
			os.startfile(dictPath)
		except OSError:
			os.popen("notepad \"%s\"" % dictPath)

	def onReloadDictClick(self, evt):
		self.tmpDict = getDictionary(self.type_)[1]
		self.onSetEntries()

	@staticmethod
	def getReprTextPattern(textPattern, equiv=True):
		if re.match(r"^\\x[0-9a-f]+$", textPattern, re.IGNORECASE):
			textPattern = textPattern.lower()
			textPattern = chr(
				int(''.join([c for c in textPattern if c in "abcdef1234567890"]), 16))
		if equiv and len(textPattern) == 1:
			return "%s (%s, %s)" % (textPattern, hex(ord(textPattern)).replace("0x", r"\x"), unicodedata.name(textPattern).lower())
		textPattern = textPattern.replace(r"\s", " ").replace(
			r"\t", "	").replace(r"\ ", r"\s").replace(r"\	", r"\t")
		return textPattern

	@staticmethod
	def getReprBraillePattern(braillePattern, equiv=True):
		if equiv and re.match(r"^[0-8\-]+$", braillePattern):
			return "%s (%s)" % (huc.cellDescriptionsToUnicodeBraille(braillePattern), braillePattern)
		braillePattern = braillePattern.replace(r"\s", " ").replace(r"\t", "	")
		return braillePattern

	def onAddClick(self, evt):
		entryDialog = DictionaryEntryDlg(self, title=_("Add Dictionary Entry"))
		if entryDialog.ShowModal() == wx.ID_OK:
			entry = entryDialog.dictEntry
			self.tmpDict.append(entry)
			direction = DIRECTION_LABELS[entry[3]] if len(
				entry) >= 4 and entry[3] in DIRECTION_LABELS else "both"
			comment = entry[4] if len(entry) == 5 else ''
			self.dictList.Append((
				comment,
				self.getReprTextPattern(entry.textPattern),
				self.getReprBraillePattern(entry.braillePattern),
				entry.opcode,
				direction
			))
			index = self.dictList.GetFirstSelected()
			while index >= 0:
				self.dictList.Select(index, on=0)
				index = self.dictList.GetNextSelected(index)
			addedIndex = self.dictList.GetItemCount()-1
			self.dictList.Select(addedIndex)
			self.dictList.Focus(addedIndex)
			self.dictList.SetFocus()
		entryDialog.Destroy()

	def onEditClick(self, evt):
		if self.dictList.GetSelectedItemCount() != 1:
			return
		editIndex = self.dictList.GetFirstSelected()
		entryDialog = DictionaryEntryDlg(self)
		entryDialog.textPatternTextCtrl.SetValue(
			self.getReprTextPattern(self.tmpDict[editIndex].textPattern, False))
		entryDialog.braillePatternTextCtrl.SetValue(
			self.getReprBraillePattern(self.tmpDict[editIndex].braillePattern, False))
		entryDialog.commentTextCtrl.SetValue(self.tmpDict[editIndex].comment)
		entryDialog.setOpcode(self.tmpDict[editIndex].opcode)
		entryDialog.setDirection(self.tmpDict[editIndex].direction)
		if entryDialog.ShowModal() == wx.ID_OK:
			self.tmpDict[editIndex] = entryDialog.dictEntry
			entry = entryDialog.dictEntry
			direction = DIRECTION_LABELS[entry.direction] if len(
				entry) >= 4 and entry.direction in DIRECTION_LABELS else "both"
			self.dictList.SetItem(editIndex, 0, entry.comment)
			self.dictList.SetItem(
				editIndex, 1, self.getReprTextPattern(entry.textPattern))
			self.dictList.SetItem(
				editIndex, 2, self.getReprBraillePattern(entry.braillePattern))
			self.dictList.SetItem(editIndex, 3, entry.opcode)
			self.dictList.SetItem(editIndex, 4, direction)
			self.dictList.SetFocus()
		entryDialog.Destroy()

	def onRemoveClick(self, evt):
		index = self.dictList.GetFirstSelected()
		while index >= 0:
			self.dictList.DeleteItem(index)
			del self.tmpDict[index]
			index = self.dictList.GetNextSelected(index)
		self.dictList.SetFocus()

	def onApply(self, evt):
		res = saveDict(self.type_, self.tmpDict)
		setDictTables()
		braille.handler.setDisplayByName(braille.handler.display.name)
		if res:
			super().onApply(evt)
		else:
			notImplemented("Error during writing file, more info in log.")
		notifyInvalidTables()
		self.dictList.SetFocus()

	def onOk(self, evt):
		res = saveDict(self.type_, self.tmpDict)
		setDictTables()
		braille.handler.setDisplayByName(braille.handler.display.name)
		notifyInvalidTables()
		if res:
			super().onOk(evt)
		else:
			notImplemented("Error during writing file, more info in log.")
		notifyInvalidTables()


class DictionaryEntryDlg(wx.Dialog):
	# Translators: This is the label for the edit dictionary entry dialog.
	def __init__(self, parent=None, title=_("Edit Dictionary Entry"), textPattern='', specifyDict=False):
		super().__init__(parent, title=title)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		if specifyDict:
			# Translators: This is a label for an edit field in add dictionary entry dialog.
			dictText = _("Dictionary")
			outTable = tablegroups.fileName2displayName(
				config.conf["braille"]["translationTable"])
			dictChoices = [_("Global"), _(
				"Table ({})").format(outTable), _("Temporary")]
			self.dictRadioBox = sHelper.addItem(wx.RadioBox(
				self, label=dictText, choices=dictChoices))
			self.dictRadioBox.SetSelection(1)
			bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
			bHelper.addButton(
				parent=self,
				label=_("See &entries")
			).Bind(wx.EVT_BUTTON, self.onSeeEntriesClick)
			sHelper.addItem(bHelper)

		# Translators: This is a label for an edit field in add dictionary entry dialog.
		patternLabelText = _("&Text pattern/sign")
		self.textPatternTextCtrl = sHelper.addLabeledControl(
			patternLabelText, wx.TextCtrl)
		if textPattern:
			self.textPatternTextCtrl.SetValue(textPattern)

		# Translators: This is a label for an edit field in add dictionary entry dialog and in punctuation/symbol pronunciation dialog.
		braillePatternLabelText = _("&Braille representation")
		self.braillePatternTextCtrl = sHelper.addLabeledControl(
			braillePatternLabelText, wx.TextCtrl)

		# Translators: This is a label for an edit field in add dictionary entry dialog.
		commentLabelText = _("&Comment")
		self.commentTextCtrl = sHelper.addLabeledControl(
			commentLabelText, wx.TextCtrl)

		# Translators: This is a label for a set of radio buttons in add dictionary entry dialog.
		opcodeText = _("&Opcode")
		opcodeChoices = [OPCODE_LABELS[i] for i in OPCODE_LABELS_ORDERING]
		self.opcodeRadioBox = sHelper.addItem(wx.RadioBox(
			self, label=opcodeText, choices=opcodeChoices))

		# Translators: This is a label for a set of radio buttons in add dictionary entry dialog.
		directionText = _("&Direction")
		directionChoices = [DIRECTION_LABELS[i]
							for i in DIRECTION_LABELS_ORDERING]
		self.directionRadioBox = sHelper.addItem(wx.RadioBox(
			self, label=directionText, choices=directionChoices))

		sHelper.addDialogDismissButtons(
			self.CreateButtonSizer(wx.OK | wx.CANCEL))

		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.setOpcode(OPCODE_SIGN)
		toFocus = self.dictRadioBox if specifyDict else self.textPatternTextCtrl
		toFocus.SetFocus()
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)

	def onSeeEntriesClick(self, evt):
		outTable = tablegroups.fileName2displayName(
			config.conf["braille"]["translationTable"])
		label = [_("Global dictionary"), _("Table dictionary ({})").format(
			outTable), _("Temporary dictionary")][self.dictRadioBox.GetSelection()]
		type_ = self.getType_()
		self.Destroy()
		gui.mainFrame._popupSettingsDialog(DictionaryDlg, label, type_)

	def getOpcode(self):
		opcodeRadioValue = self.opcodeRadioBox.GetSelection()
		if opcodeRadioValue == wx.NOT_FOUND:
			return OPCODE_SIGN
		return OPCODE_LABELS_ORDERING[opcodeRadioValue]

	def getDirection(self):
		directionRadioValue = self.directionRadioBox.GetSelection()
		if directionRadioValue == wx.NOT_FOUND:
			return DIRECTION_BOTH
		return DIRECTION_LABELS_ORDERING[directionRadioValue]

	def getType_(self):
		dicts = ["default", "table", "tmp"]
		return dicts[self.dictRadioBox.GetSelection()]

	def onOk(self, evt):
		braillePattern = self.braillePatternTextCtrl.GetValue()
		textPattern = self.textPatternTextCtrl.GetValue()
		opcode = self.getOpcode()
		if not textPattern:
			msg = _("Text pattern/sign field is empty.")
			gui.messageBox(msg, _("Braille Extender"), wx.OK | wx.ICON_ERROR)
			return self.textPatternTextCtrl.SetFocus()
		if opcode != OPCODE_REPLACE:
			egBRLRepr = "12345678, 5-123456, 0-138."
			egTextPattern = r"α, ∪, \x2019."
			if len(textPattern) > 1 and not re.match(r"^\\x[0-9a-f]+$", textPattern):
				msg = _(
					"Invalid value for 'text pattern/sign' field. You must specify a character with this opcode. E.g.: %s") % egTextPattern
				gui.messageBox(msg, _("Braille Extender"),
							   wx.OK | wx.ICON_ERROR)
				return self.textPatternTextCtrl.SetFocus()
			if not braillePattern:
				msg = _(
					"'Braille representation' field is empty. You must specify something with this opcode. E.g.: %s") % egBRLRepr
				gui.messageBox(msg, _("Braille Extender"),
							   wx.OK | wx.ICON_ERROR)
				return self.braillePatternTextCtrl.SetFocus()
			if not re.match(r"^[0-8\-]+$", braillePattern):
				msg = _(
					"Invalid value for 'braille representation' field. You must enter dot patterns with this opcode. E.g.: %s") % egBRLRepr
				gui.messageBox(msg, _("Braille Extender"),
							   wx.OK | wx.ICON_ERROR)
				return self.braillePatternTextCtrl.SetFocus()
		else:
			textPattern = textPattern.lower().replace("\\", r"\\")
		textPattern = textPattern.replace("	", r"\t").replace(" ", r"\s")
		braillePattern = braillePattern.replace(
			"\\", r"\\").replace("	", r"\t").replace(" ", r"\s")
		newEntry = TableDictEntry(opcode, textPattern, braillePattern, self.getDirection(
		), self.commentTextCtrl.GetValue())
		save = True if hasattr(self, "dictRadioBox") else False
		if save:
			type_ = self.getType_()
			dict_ = getDictionary(type_)[1]
			dict_.append(newEntry)
			saveDict(type_, dict_)
			self.Destroy()
			setDictTables()
			braille.handler.setDisplayByName(braille.handler.display.name)
			notifyInvalidTables()
		else:
			self.dictEntry = newEntry
		evt.Skip()

	def setOpcode(self, opcode):
		self.opcodeRadioBox.SetSelection(OPCODE_LABELS_ORDERING.index(opcode))

	def setDirection(self, direction):
		self.directionRadioBox.SetSelection(
			DIRECTION_LABELS_ORDERING.index(direction))
