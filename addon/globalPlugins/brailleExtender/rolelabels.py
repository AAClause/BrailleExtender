# coding: utf-8
# rolelabels.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2021 André-Abush CLAUSE, released under GPL.

import json
import os
import gui
import wx

import addonHandler
import braille
import config
import controlTypes
import languageHandler

from .common import configDir

addonHandler.initTranslation()

CUR_LANG = languageHandler.getLanguage().split("_")[0]
PATH_JSON = os.path.join(configDir, f"roleLabels-{CUR_LANG}.json")


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("Role labels")

	roleLabels = {}

	def makeSettings(self, settingsSizer):
		self.roleLabels = roleLabels.copy()
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		self.toggleRoleLabels = sHelper.addItem(wx.CheckBox(self, label=_("Use custom braille &role labels")))
		self.toggleRoleLabels.SetValue(config.conf["brailleExtender"]["features"]["roleLabels"])
		self.toggleRoleLabels.Bind(wx.EVT_CHECKBOX, self.onToggleRoleLabels)
		self.categories = sHelper.addLabeledControl(
			_("Role cate&gory:"),
			wx.Choice,
			choices=[_("General"), _("Landmarks"), _("Positive states"), _("Negative states")],
		)
		self.categories.Bind(wx.EVT_CHOICE, self.onCategories)
		self.categories.SetSelection(0)

		choices = []
		if hasattr(controlTypes, "roleLabels"):
			choices = [controlTypes.roleLabels[int(k)] for k in braille.roleLabels.keys()]

		self.labels = sHelper.addLabeledControl(_("&Role:"), wx.Choice, choices=choices)
		self.labels.Bind(wx.EVT_CHOICE, self.onLabels)

		self.label = sHelper.addLabeledControl(_("Braille &label"), wx.TextCtrl)
		self.label.Bind(wx.EVT_TEXT, self.onLabel)

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.resetLabelBtn = bHelper.addButton(
			self, wx.ID_ANY, _("&Reset this role label"), wx.DefaultPosition
		)
		self.resetLabelBtn.Bind(wx.EVT_BUTTON, self.onResetLabelBtn)
		self.resetAllLabelsBtn = bHelper.addButton(
			self, wx.ID_ANY, _("Reset a&ll role labels"), wx.DefaultPosition
		)
		self.resetAllLabelsBtn.Bind(wx.EVT_BUTTON, self.onResetAllLabelsBtn)
		sHelper.addItem(bHelper)
		self.onToggleRoleLabels(None)
		self.onCategories(None)

	def onToggleRoleLabels(self, evt):
		controls = [
			self.categories,
			self.labels,
			self.label,
			self.resetLabelBtn,
			self.resetAllLabelsBtn,
		]
		for e in controls:
			if self.toggleRoleLabels.IsChecked():
				e.Enable()
			else:
				e.Disable()

	def onCategories(self, event):
		labels = []
		idCategory = self.categories.GetSelection()
		oldRoleLabels = hasattr(controlTypes, "roleLabels")
		if idCategory == 0:
			if oldRoleLabels:
				labels = [controlTypes.roleLabels[int(k)] for k in braille.roleLabels.keys()]
			else:
				labels = [role.displayString for role in braille.roleLabels.keys()]
		elif idCategory == 1:
			labels = list(braille.landmarkLabels.keys())
		elif idCategory == 2:
			if oldRoleLabels:
				labels = [controlTypes.stateLabels[k] for k in braille.positiveStateLabels.keys()]
			else:
				labels = [role.displayString for role in braille.positiveStateLabels.keys()]
		elif idCategory == 3:
			if oldRoleLabels:
				labels = [controlTypes.stateLabels[k] for k in braille.negativeStateLabels.keys()]
			else:
				labels = [role.displayString for role in braille.negativeStateLabels.keys()]
		for iLabel, label in enumerate(labels):
			idLabel = getIDFromIndexes(idCategory, iLabel)
			actualLabel = getLabelFromID(idCategory, idLabel)
			originalLabel = self.getOriginalLabel(idCategory, idLabel, actualLabel)
			labels[iLabel] += _(": %s") % actualLabel
			if actualLabel != originalLabel:
				labels[iLabel] += " (%s)" % originalLabel
		self.labels.SetItems(labels)
		if idCategory > -1 and idCategory < 4:
			self.labels.SetSelection(0)
		self.onLabels(None)

	def onLabels(self, event):
		idCategory = self.categories.GetSelection()
		idLabel = getIDFromIndexes(idCategory, self.labels.GetSelection())
		key = f"{idCategory}:{idLabel}"
		if key in self.roleLabels.keys():
			self.label.SetValue(self.roleLabels[key])
		else:
			self.label.SetValue(self.getOriginalLabel(idCategory, idLabel))

	def onLabel(self, evt):
		idCategory = self.categories.GetSelection()
		iLabel = self.labels.GetSelection()
		idLabel = getIDFromIndexes(idCategory, iLabel)
		key = "%d:%s" % (idCategory, idLabel)
		label = self.label.GetValue()
		if idCategory >= 0 and iLabel >= 0:
			if self.getOriginalLabel(idCategory, idLabel, chr(4)) == label:
				if key in self.roleLabels.keys():
					self.roleLabels.pop(key)
			else:
				self.roleLabels[key] = label
			actualLabel = getLabelFromID(idCategory, idLabel)
			originalLabel = self.getOriginalLabel(idCategory, idLabel, actualLabel)
			if label != originalLabel:
				self.resetLabelBtn.Enable()
			else:
				self.resetLabelBtn.Disable()

	def onResetLabelBtn(self, event):
		idCategory = self.categories.GetSelection()
		iLabel = self.labels.GetSelection()
		idLabel = getIDFromIndexes(idCategory, iLabel)
		actualLabel = getLabelFromID(idCategory, idLabel)
		originalLabel = self.getOriginalLabel(idCategory, idLabel, actualLabel)
		self.label.SetValue(originalLabel)
		self.onLabel(None)
		self.label.SetFocus()

	def onResetAllLabelsBtn(self, event):
		nbCustomizedLabels = len(self.roleLabels)
		if not nbCustomizedLabels:
			msg = _("You have no customized role labels.")
			res = gui.messageBox(msg, _("Reset role labels"), wx.OK | wx.ICON_INFORMATION)
			return
		msg = (
			_("You have %d customized role labels defined. Do you want to reset all labels?")
			% nbCustomizedLabels
		)
		flags = wx.YES | wx.NO | wx.ICON_INFORMATION
		res = gui.messageBox(msg, _("Reset role labels"), flags)
		if res == wx.YES:
			self.roleLabels = {}
			self.onCategories(None)

	def getOriginalLabel(self, idCategory, idLabel, defaultValue=""):
		key = f"{idCategory}:{idLabel}"
		if key in backupRoleLabels.keys():
			return backupRoleLabels[key][1]
		return getLabelFromID(idCategory, idLabel)

	def postInit(self):
		self.toggleRoleLabels.SetFocus()

	def onSave(self):
		global roleLabels
		config.conf["brailleExtender"]["features"]["roleLabels"] = self.toggleRoleLabels.IsChecked()
		saveRoleLabels(self.roleLabels)
		discardRoleLabels()
		if config.conf["brailleExtender"]["features"]["roleLabels"]:
			loadRoleLabels()


backupRoleLabels = {}
roleLabels = {}


def getIDFromIndexes(idCategory, idLabel):
	oldRoleLabels = hasattr(controlTypes, "roleLabels")
	if not isinstance(idCategory, int):
		raise TypeError(f"Wrong type for idCategory ({idCategory})")
	if not isinstance(idLabel, int):
		raise TypeError(f"Wrong type for idLabel ({idLabel})")
	idRole = -1
	if idCategory == 0:
		idRole = list(braille.roleLabels.keys())[idLabel]
	elif idCategory == 1:
		idRole = list(braille.landmarkLabels.keys())[idLabel]
	elif idCategory == 2:
		idRole = list(braille.positiveStateLabels.keys())[idLabel]
	elif idCategory == 3:
		idRole = list(braille.negativeStateLabels.keys())[idLabel]
	else:
		raise ValueError(f"Wrong value for category ({idCategory})")
	if not oldRoleLabels and isinstance(idRole, (controlTypes.Role, controlTypes.State)):
		idRole = idRole.value
	return idRole


def getLabelFromID(idCategory, idLabel):
	if idCategory == 0:
		return braille.roleLabels[int(idLabel)]
	if idCategory == 1:
		return braille.landmarkLabels[idLabel]
	if idCategory == 2:
		return braille.positiveStateLabels[int(idLabel)]
	if idCategory == 3:
		return braille.negativeStateLabels[int(idLabel)]
	raise ValueError("Invalid value: %d" % idCategory)


def setLabelFromID(idCategory, idLabel, newLabel):
	if idCategory == 0:
		braille.roleLabels[int(idLabel)] = newLabel
	elif idCategory == 1:
		braille.landmarkLabels[idLabel] = newLabel
	elif idCategory == 2:
		braille.positiveStateLabels[int(idLabel)] = newLabel
	elif idCategory == 3:
		braille.negativeStateLabels[int(idLabel)] = newLabel
	else:
		raise ValueError(f"Unknown category {idCategory}")


def loadRoleLabels(roleLabels_=None):
	global backupRoleLabels, roleLabels
	roleLabels.clear()
	if roleLabels_:
		roleLabels.update(roleLabels_)
	elif (
		"roleLabels" in config.conf["brailleExtender"] and config.conf["brailleExtender"]["roleLabels"].copy()
	):
		roleLabels.update(config.conf["brailleExtender"]["roleLabels"].copy())
		saveRoleLabels(roleLabels)
		config.conf["brailleExtender"]["roleLabels"] = {}
	elif os.path.exists(PATH_JSON):
		f = open(PATH_JSON, "r", encoding="UTF-8")
		try:
			roleLabels.update(json.load(f))
		except json.decoder.JSONDecodeError:
			pass
		f.close()
	for k, v in roleLabels.items():
		idCategory, idRole = k.split(":")
		idCategory = int(idCategory)
		backupRoleLabels[k] = (v, getLabelFromID(idCategory, idRole))
		setLabelFromID(idCategory, idRole, v)


def saveRoleLabels(roleLabels_):
	f = open(PATH_JSON, "w")
	json.dump(roleLabels_, f, ensure_ascii=False, indent=2)
	f.close()


def discardRoleLabels():
	global backupRoleLabels, roleLabels
	for k, v in backupRoleLabels.items():
		idCategory, idRole = k.split(":")
		idCategory = int(idCategory)
		setLabelFromID(idCategory, idRole, v[1])
	backupRoleLabels = {}
	roleLabels = {}
