# coding: utf-8
# virtualDocumentSettings.py
# Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush CLAUSE, released under GPL.

import addonHandler
import config
import gui
import wx

addonHandler.initTranslation()

conf = config.conf["brailleExtender"]["virtualDocument"]


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of the Virtual documents category in Braille Extender settings.
	title = _("Virtual documents")
	panelDescription = _(
		"Choose how tables in browse mode (web pages and other virtual documents) appear on the braille display."
	)

	def makeSettings(self, settingsSizer: wx.Sizer) -> None:
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		sHelper.addItem(wx.StaticText(self, label=self.panelDescription))

		# Translators: Checkbox in Braille Extender virtual document settings.
		self.tableRowBraille = sHelper.addItem(
			wx.CheckBox(self, label=_("Display full table &row on one braille line"))
		)
		self.tableRowBraille.SetValue(conf["tableRowBraille"])
		self.tableRowBraille.Bind(wx.EVT_CHECKBOX, self._onTableRowBrailleChanged)

		# Translators: Label for the text shown between table cells on one braille row line.
		self.cellSeparator = sHelper.addLabeledControl(
			_("&Separator between cells:"),
			wx.TextCtrl,
		)
		self.cellSeparator.SetValue(conf["cellSeparator"])
		# Translators: Label for the text shown at the start of a table row braille line.
		self.lineStart = sHelper.addLabeledControl(
			_("Start of &row line:"),
			wx.TextCtrl,
		)
		self.lineStart.SetValue(conf["lineStart"])
		# Translators: Label for the text shown at the end of a table row braille line.
		self.lineEnd = sHelper.addLabeledControl(
			_("End of row &line:"),
			wx.TextCtrl,
		)
		self.lineEnd.SetValue(conf["lineEnd"])
		self._onTableRowBrailleChanged()

	def _onTableRowBrailleChanged(self, evt: wx.CommandEvent | None = None) -> None:
		enabled = self.tableRowBraille.IsChecked()
		self.cellSeparator.Enable(enabled)
		self.lineStart.Enable(enabled)
		self.lineEnd.Enable(enabled)

	def onSave(self) -> None:
		from .virtualBufferTableBraille import schedule_virtual_document_braille_refresh

		conf["tableRowBraille"] = self.tableRowBraille.IsChecked()
		conf["cellSeparator"] = self.cellSeparator.GetValue()
		conf["lineStart"] = self.lineStart.GetValue()
		conf["lineEnd"] = self.lineEnd.GetValue()
		schedule_virtual_document_braille_refresh()
