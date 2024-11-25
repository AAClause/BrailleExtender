# tablegroups.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush Clause, released under GPL.

import codecs
import json
import os
import gui
import wx

import addonHandler
import config
from itertools import permutations
from brailleTables import listTables, TABLES_DIR
from logHandler import log
from . import addoncfg
from .common import baseDir, configDir
from .tablehelper import (
	getPreferredTables, getPreferredTablesIndexes,
	get_display_names, get_tables, get_tables_file_name_by_id, get_file_names_by_display_names, get_table_by_file_name
)

addonHandler.initTranslation()

POSITION_CURRENT = "c"
POSITION_PREVIOUS = "p"
POSITION_NEXT = "n"
POSITIONS = [POSITION_CURRENT, POSITION_PREVIOUS, POSITION_NEXT]

USAGE_INPUT = 0
USAGE_OUTPUT = 1
USAGE_BOTH = 2
USAGES = (USAGE_INPUT, USAGE_OUTPUT, USAGE_BOTH)

USAGE_LABELS = {
	USAGE_INPUT: _("input only"),
	USAGE_OUTPUT: _("output only"),
	USAGE_BOTH: _("input and output")
}

class TableGroups:

	_groups = []

	def __init__(self, groups=[]):
		self._groups = []
		if groups:
			for group in groups: self.add_group(group)

	def __len__(self):
		return len(self._groups)

	def __getitem__(self, item):
		return self._groups[item]

	def __contains__(self, value):
		for i, group in enumerate(self._groups):
			if self.is_similar(value, group): return True
		return False

	def index(self, value):
		for i, group in enumerate(self._groups):
			if self.is_similar(value, group): return i
		raise IndexError ("Group is not in list group")

	def add_group(self, groupTable):
		if not isinstance(groupTable, TableGroup):
			raise TypeError("groupTable: wrong type")
		self._groups.append(groupTable)

	def is_similar(self, group1, group2):
		if group1.usageIn != group2.usageIn:
			return False
		if len(group1.members) != len(group2.members):
			return False
		if group1.members != group2.members:
			return False
		return True

	def get_json(self):
		data = [
			{
				"name": group.name,
				"members": [m.fileName for m in group.members],
				"usageIn": group.usageIn,
			}
			for group in self._groups
		]
		return data

	def load_json(self, data):
		for group in data:
			self.add_group(
				TableGroups(
					entry["name"],
					entry["members"],
					entry["usageIn"]
				)
			)

	def get_groups(self):
		groups = self._groups
		i = [group for group in groups if group.usageIn in [USAGE_INPUT, USAGE_BOTH]]
		o = [group for group in groups if group.usageIn in [USAGE_OUTPUT, USAGE_BOTH]]
		return i, o


class TableGroup:

	name = None
	members: list = []
	usageIn = None

	def __init__(self,
		name: str,
		members: list,
		usageIn
	):
		if not isinstance(name, str):
			raise TypeError("name: wrong type")
		if not isinstance(members, list):
			raise TypeError("members: wrong type")
		if not isinstance(members, list):
			raise TypeError("wrong type")
		members = [member for member in members if member]
		if len(members) < 1:
			raise ValueError("Missing member")
		self.name = name
		self.usageIn = usageIn
		self.members = []
		for member in members:
			table = get_table_by_file_name(member)
			if table:
				self.members.append(table)
			else:
				raise ValueError(f"invalid table ({member})")

	def __str__(self):
		name = self.name
		members = self.members
		usageIn = self.usageIn
		return f'{{name="{name}", members={members}, usageIn={usageIn}}}'

	def get_tables(self):
		return [
			os.path.join(TABLES_DIR, member.fileName)
			for member in self.members
		]



def translateUsageIn(s):
	labels = USAGE_LABELS
	return labels[s] if s in labels.keys() else _("None")


def getPathGroups():
	return f"{configDir}/table-groups.json"


def initializeGroups():
	global _groups
	_groups = TableGroups()
	fp = getPathGroups()
	if os.path.exists(fp):
		json_ = json.load(codecs.open(fp, "r", "UTF-8"))
		_groups.load_json(json_)


def saveGroups(entries=None):
	data = tableGroups.get_json()
	with codecs.open(getPathGroups(), "w", "UTF-8") as outfile:
		json.dump(entries, outfile, ensure_ascii=False, indent=2)


def getAllGroups(usageIn):
	usageInIndex = USAGES.index(usageIn)
	groups = []
	groups.extend(tablesToGroups(getPreferredTables()[usageInIndex], usageIn=usageIn))
	groups.extend(_groups.get_groups()[usageInIndex])
	return groups


def getGroup(
	usageIn,
	position=POSITION_CURRENT,
	choices=None
):
	global _currentGroup
	if choices and not isinstance(choices, TableGroups):
		raise TypeError("choices: wrong type")
	if position not in POSITIONS:
		raise ValueError("Invalid position")
	if usageIn not in USAGES:
		raise ValueError("Invalid usage")
	usageInIndex = USAGES.index(usageIn)
	currentGroup = _currentGroup[usageInIndex]
	if not choices:
		choices = getAllGroups(usageIn=usageIn)
		if not choices:
			return None
	if not currentGroup:
		currentGroup = choices[0]
	if currentGroup not in choices:
		choices_str = "\n  - ".join([str(c) for c in choices])
		log.error(f"Unable to find the current group in group list\n- currentGroup={currentGroup}\n- choices={choices_str}")
		raise RuntimeError()
	curPos = choices.index(currentGroup)
	newPos = curPos
	if position == POSITION_PREVIOUS:
		newPos = curPos - 1
	elif position == POSITION_NEXT:
		newPos = curPos + 1
	newChoice = choices[newPos % len(choices)]
	if not isinstance(newChoice, TableGroup):
		log.error(choices)
		log.error(newChoice)
		raise TypeError("newChoice: wrong type")
	return newChoice


def setTableOrGroup(
	usageIn,
	e,
	choices=None
):
	global _currentGroup
	if not isinstance(e, TableGroup):
		raise TypeError("e: wrong type")
	if not usageIn in USAGES:
		raise ValueError("invalid usageIn")
	usageInIndex = USAGES.index(usageIn)
	if not choices:
		choices = getAllGroups(usageIn)
	"""if not e in choices:
		log.error(f"e={e}, choices={[str(e) for e in choices]}")
		return False"""
	_currentGroup[usageInIndex] = e
	return True


def tablesToGroups(tables, usageIn):
	if not tables: return []
	if not isinstance(tables, list):
		raise ValueError("tables wrong type")
	groups = []
	for table in tables:
		groups.append(TableGroup(", ".join(get_file_names_by_display_names([table])),
			[table],
			usageIn
		))
	return groups


def groupEnabled():
	return bool(_groups)


_groups = None
_currentGroup = [None, None]
conf = config.conf["brailleExtender"]["tables"]

class SettingsDlg(gui.settingsDialogs.SettingsPanel):

	# Translators: title of a dialog.
	title = _("Braille tables")

	def makeSettings(self, settingsSizer):
		listPreferredTablesIndexes = getPreferredTablesIndexes()
		log.info(listPreferredTablesIndexes)
		currentTableLabel = _("Use the current input table")
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		bHelper1 = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)

		tables = [
			f"{table.displayName}, {table.fileName}" for table in listTables() if table.input]
		label = _("Preferred &input tables")
		self.inputTables = sHelper.addLabeledControl(
			label, gui.nvdaControls.CustomCheckListBox, choices=tables)
		self.inputTables.CheckedItems = listPreferredTablesIndexes[0]
		self.inputTables.Select(0)

		tables = [
			f"{table.displayName}, {table.fileName}" for table in listTables() if table.output]
		label = _("Preferred &output tables")
		self.outputTables = sHelper.addLabeledControl(
			label, gui.nvdaControls.CustomCheckListBox, choices=tables)
		self.outputTables.CheckedItems = listPreferredTablesIndexes[1]
		self.outputTables.Select(0)

		label = _("Input braille table to use for keyboard shortcuts")
		try:
			selectedItem = 0 if conf["shortcuts"] == '?' else listTablesFileName(get_tables(input=True, contracted=False)
			).index(conf["shortcuts"]) + 1
		except ValueError:
			selectedItem = 0
		self.inputTableShortcuts = sHelper.addLabeledControl(label, wx.Choice, choices=[
			currentTableLabel] + get_display_names(
				get_tables(contracted=False, input=True)
			))
		self.inputTableShortcuts.SetSelection(selectedItem)

		self.tablesGroupBtn = bHelper1.addButton(
			self, wx.NewId(), "%s..." % _("Table &groups"), wx.DefaultPosition)
		self.tablesGroupBtn.Bind(wx.EVT_BUTTON, self.onTableGroupsBtn)

		self.customBrailleTablesBtn = bHelper1.addButton(self, wx.NewId(), "%s..." % _(
			"Alternative and &custom braille tables"), wx.DefaultPosition)
		self.customBrailleTablesBtn.Bind(
			wx.EVT_BUTTON, self.onCustomBrailleTablesBtn)

		# Translators: label of a dialog.
		self.tabSpace = sHelper.addItem(wx.CheckBox(
			self, label=_("Display &tab signs as spaces")))
		self.tabSpace.SetValue(conf["tabSpace"])
		self.tabSpace.Bind(wx.EVT_CHECKBOX, self.onTabSpace)

		# Translators: label of a dialog.
		label =  _("Number of &space for a tab sign")+" "+_("for the currrent braille display")
		self.tabSize = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl, min=1, max=42, initial=int(conf["tabSize_%s" % addoncfg.curBD])
		)
		sHelper.addItem(bHelper1)
		self.onTabSpace()

	def onTabSpace(self, evt=None):
		if self.tabSpace.IsChecked():
			self.tabSize.Enable()
		else:
			self.tabSize.Disable()

	def onTableGroupsBtn(self, evt):
		tableGroupsDlg = TableGroupsDlg(self, multiInstanceAllowed=True)
		tableGroupsDlg.ShowModal()

	def onCustomBrailleTablesBtn(self, evt):
		customBrailleTablesDlg = CustomBrailleTablesDlg(
			self, multiInstanceAllowed=True)
		customBrailleTablesDlg.ShowModal()

	def postInit(self): self.tables.SetFocus()

	def isValid(self):
		if self.tabSize.Value > 42:
			gui.messageBox(
				_("Tab size is invalid"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self
			)
			self.tabSize.SetFocus()
			return False
		return super().isValid()

	def onSave(self):
		inputTables = '|'.join(get_tables_file_name_by_id(
			self.inputTables.CheckedItems,
			get_tables(input=True)
		))
		outputTables = '|'.join(
			get_tables_file_name_by_id(
				self.outputTables.CheckedItems,
				get_tables(output=True)
			)
		)
		tablesShortcuts = get_tables_file_name_by_id(
			[self.inputTableShortcuts.GetSelection()-1],
			get_tables(contracted=False, input=True)
		)[0] if self.inputTableShortcuts.GetSelection() > 0 else '?'
		conf["preferredInput"] = inputTables
		conf["preferredOutput"] = outputTables
		conf["shortcuts"] = tablesShortcuts
		conf["tabSpace"] = self.tabSpace.IsChecked()
		conf[f"tabSize_{addoncfg.curBD}"] = self.tabSize.Value

	def postSave(self):
		pass #initializePreferredTables()


class TableGroupsDlg(gui.settingsDialogs.SettingsDialog):

	# Translators: title of a dialog.
	title = _("Table groups")

	def makeSettings(self, settingsSizer):
		self.tmpGroups = getGroups()
		self.tmpGroups.sort(key=lambda e: e.name)
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		groupsLabelText = _("List of table groups")
		self.groupsList = sHelper.addLabeledControl(
			groupsLabelText, wx.ListCtrl, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(550, 350))
		self.groupsList.InsertColumn(0, _("Name"), width=150)
		self.groupsList.InsertColumn(1, _("Members"), width=150)
		self.groupsList.InsertColumn(2, _("Usable in"), width=150)
		self.onSetEntries()

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table groups dialog to add new entries.
			label=_("&Add")
		).Bind(wx.EVT_BUTTON, self.onAddClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table groups dialog to edit existing entries.
			label=_("&Edit")
		).Bind(wx.EVT_BUTTON, self.onEditClick)

		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table groups dialog to remove existing entries.
			label=_("Re&move")
		).Bind(wx.EVT_BUTTON, self.onRemoveClick)

		sHelper.addItem(bHelper)
		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table groups dialog to open table groups file in an editor.
			label=_("&Open the table groups file in an editor")
		).Bind(wx.EVT_BUTTON, self.onOpenFileClick)
		bHelper.addButton(
			parent=self,
			# Translators: The label for a button in table groups dialog to reload table groups.
			label=_("&Reload table groups")
		).Bind(wx.EVT_BUTTON, self.onReloadClick)
		sHelper.addItem(bHelper)

	def postInit(self):
		self.groupsList.SetFocus()

	def onSetEntries(self, evt=None):
		self.groupsList.DeleteAllItems()
		for group in self.tmpGroups:
			self.groupsList.Append((
				group.name,
				", ".join(FileName2displayName(group.members)),
				translateUsageIn(group.usageIn)
			))

	def onAddClick(self, event):
		entryDialog = GroupEntryDlg(self, title=_("Add group entry"))
		if entryDialog.ShowModal() == wx.ID_OK:
			entry = entryDialog.groupEntry
			self.tmpGroups.append(entry)
			self.groupsList.Append(
				(entry.name, ", ".join(FileName2displayName(entry.members)),
				 translateUsageIn(entry.usageIn))
			)
			index = self.groupsList.GetFirstSelected()
			while index >= 0:
				self.groupsList.Select(index, on=0)
				index = self.groupsList.GetNextSelected(index)
			addedIndex = self.groupsList.GetItemCount() - 1
			self.groupsList.Select(addedIndex)
			self.groupsList.Focus(addedIndex)
			self.groupsList.SetFocus()
		entryDialog.Destroy()

	def onEditClick(self, event):
		if self.groupsList.GetSelectedItemCount() != 1:
			return
		editIndex = self.groupsList.GetFirstSelected()
		entryDialog = GroupEntryDlg(self)
		entryDialog.name.SetValue(self.tmpGroups[editIndex].name)
		entryDialog.members.CheckedItems = listTablesIndexes(
			self.tmpGroups[editIndex].members, get_tables(contracted=False, input=True))
		entryDialog.refreshOrders()
		selectedItem = 0
		try:
			selectedItem = list(entryDialog.orderPermutations.keys()).index(tuple(
				listTablesIndexes(self.tmpGroups[editIndex].members, get_tables(contracted=False))))
			entryDialog.order.SetSelection(selectedItem)
		except ValueError:
			pass
		entryDialog.usageIn.CheckedItems = translateUsageInIndexes(
			self.tmpGroups[editIndex].usageIn)
		if entryDialog.ShowModal() == wx.ID_OK:
			entry = entryDialog.groupEntry
			self.tmpGroups[editIndex] = entry
			self.groupsList.SetItem(editIndex, 0, entry.name)
			self.groupsList.SetItem(editIndex, 1, ", ".join(
				FileName2displayName(entry.members)))
			self.groupsList.SetItem(
				editIndex, 2, translateUsageIn(entry.usageIn))
			self.groupsList.SetFocus()
			entryDialog.Destroy()

	def onRemoveClick(self, event):
		index = self.groupsList.GetFirstSelected()
		while index >= 0:
			self.groupsList.DeleteItem(index)
			del self.tmpGroups[index]
			index = self.groupsList.GetNextSelected(index)
		self.onSetEntries()
		self.groupsList.SetFocus()

	def onOpenFileClick(self, evt):
		path = getPathGroups()
		if not os.path.exists(path):
			return
		try:
			os.startfile(path)
		except OSError:
			os.popen(f"notepad \"{path}\"")

	def onReloadClick(self, evt):
		self.tmpGroups = getGroups()
		self.onSetEntries()

	def onOk(self, evt):
		saveGroups(self.tmpGroups)
		setDict(self.tmpGroups)
		super().onOk(evt)


class GroupEntryDlg(wx.Dialog):

	orderPermutations = {}

	def __init__(self, parent=None, title=_("Edit Dictionary Entry")):
		super().__init__(parent, title=title)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.name = sHelper.addLabeledControl(_("Group &name:"), wx.TextCtrl)
		label = _("Group &members")
		self.members = sHelper.addLabeledControl(
			label, gui.nvdaControls.CustomCheckListBox, choices=get_display_names(
				get_tables(contracted=False)
			))
		self.members.SetSelection(0)
		self.members.Bind(wx.EVT_CHECKLISTBOX, lambda s: self.refreshOrders())
		label = _("Table &order:")
		self.order = sHelper.addLabeledControl(
			label, wx.Choice, choices=[])
		self.refreshOrders()
		label = _("&Usable in:")
		choices = list(USAGE_LABELS.values())
		self.usageIn = sHelper.addItem(wx.RadioBox(self,
			label=label, choices=choices))
		self.usageIn.SetSelection(1)
		sHelper.addDialogDismissButtons(
			self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.name.SetFocus()

	def refreshOrders(self, evt=None):
		tables = get_tables(contracted=False)
		self.orderPermutations = {e: FileName2displayName(get_tables_file_name_by_id(e, tables)) for e in permutations(self.members.CheckedItems) if e}
		self.order.SetItems([", ".join(e)
							 for e in self.orderPermutations.values()])
		self.order.SetSelection(0)

	def onOk(self, evt):
		name = self.name.Value
		if not self.orderPermutations:
			return
		members = get_tables_file_name_by_id(list(self.orderPermutations.keys())[
			self.order.GetSelection()], get_tables(contracted=False))
		matches = USAGE_LABELS.keys()
		usageIn = ''.join([matches[e] for e in self.usageIn.CheckedItems])
		if not name:
			gui.messageBox(
				_("Please specify a group name"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self
			)
			return self.name.SetFocus()
		if len(members) < 2:
			gui.messageBox(
				_("Please select at least 2 tables"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self
			)
			return self.members.SetFocus()
		self.groupEntry = TableGroups(name, members, usageIn)
		evt.Skip()


class CustomBrailleTablesDlg(gui.settingsDialogs.SettingsDialog):

	# Translators: title of a dialog.
	title = _("Custom braille tables")
	providedTablesPath = "%s/res/json" % baseDir
	userTablesPath = "%s/json" % configDir

	def makeSettings(self, settingsSizer):
		self.providedTables = self.getBrailleTablesFromJSON(
			self.providedTablesPath)
		self.userTables = self.getBrailleTablesFromJSON(self.userTablesPath)
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		bHelper1 = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.inTable = sHelper.addItem(wx.CheckBox(
			self, label=_("Use a custom table as input table")))
		self.outTable = sHelper.addItem(wx.CheckBox(
			self, label=_("Use a custom table as output table")))
		self.addBrailleTablesBtn = bHelper1.addButton(
			self, wx.NewId(), "%s..." % _("&Add a braille table"), wx.DefaultPosition)
		self.addBrailleTablesBtn.Bind(
			wx.EVT_BUTTON, self.onAddBrailleTablesBtn)
		sHelper.addItem(bHelper1)

	@staticmethod
	def getBrailleTablesFromJSON(path):
		if not os.path.exists(path):
			path = "%s/%s" % (baseDir, path)
			if not os.path.exists(path):
				return {}
		f = open(path)
		return json.load(f)

	def onAddBrailleTablesBtn(self, evt):
		addBrailleTablesDlg = AddBrailleTablesDlg(
			self, multiInstanceAllowed=True)
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
		self.name = sHelper.addLabeledControl(_("Display name"), wx.TextCtrl)
		self.description = sHelper.addLabeledControl(
			_("Description"), wx.TextCtrl, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER, size=(360, 90), pos=(-1, -1))
		self.path = sHelper.addLabeledControl(_("Path"), wx.TextCtrl)
		self.browseBtn = bHelper1.addButton(
			self, wx.NewId(), "%s..." % _("&Browse"), wx.DefaultPosition)
		self.browseBtn.Bind(wx.EVT_BUTTON, self.onBrowseBtn)
		sHelper.addItem(bHelper1)
		self.isContracted = sHelper.addItem(wx.CheckBox(
			self, label=_("Contracted (grade 2) braille table")))
		# Translators: label of a dialog.
		self.inputOrOutput = sHelper.addLabeledControl(_("Available for"), wx.Choice, choices=[
			_("Input and output"), _("Input only"), _("Output only")])
		self.inputOrOutput.SetSelection(0)

	def postInit(self): self.name.SetFocus()

	def onBrowseBtn(self, event):
		dlg = wx.FileDialog(None, _("Choose a table file"), "%PROGRAMFILES%", "", "%s (*.ctb, *.cti, *.utb, *.uti)|*.ctb;*.cti;*.utb;*.uti" %
							_("Liblouis table files"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return self.path.SetFocus()
		self.path.SetValue(dlg.GetDirectory() + '\\' + dlg.GetFileName())
		dlg.Destroy()
		self.path.SetFocus()

	def onOk(self, event):
		path = self.path.GetValue().strip().encode("UTF-8")
		displayName = self.name.GetValue().strip()
		if not displayName:
			gui.messageBox(_("Please specify a display name."), _(
				"Invalid display name"), wx.OK | wx.ICON_ERROR)
			self.name.SetFocus()
			return
		if not os.path.exists(path.decode("UTF-8").encode("mbcs")):
			gui.messageBox(_("The specified path is not valid (%s).") % path.decode(
				"UTF-8"), _("Invalid path"), wx.OK | wx.ICON_ERROR)
			self.path.SetFocus()
			return
		switch_possibleValues = ["both", "input", "output"]
		v = "%s|%s|%s|%s" % (
			switch_possibleValues[self.inputOrOutput.GetSelection()],
			self.isContracted.IsChecked(), path.decode("UTF-8"), displayName
		)
		k = hashlib.md5(path).hexdigest()[:15]
		conf["brailleTables"][k] = v
		super().onOk(evt)

	@staticmethod
	def getAvailableBrailleTables():
		out = []
		brailleTablesDir = addoncfg.TABLES_DIR
		ls = glob.glob(brailleTablesDir+'\\*.ctb')+glob.glob(brailleTablesDir +
															 '\\*.cti')+glob.glob(brailleTablesDir+'\\*.utb')
		for i, e in enumerate(ls):
			e = str(e.split('\\')[-1])
			if e in addoncfg.tablesFN or e.lower() in addoncfg.tablesFN:
				del ls[i]
			else:
				out.append(e.lower())
		out = sorted(out)
		return out
