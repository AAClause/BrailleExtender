# coding: utf-8
# excelSettings.py
# Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush Clause, released under GPL.

import addonHandler
import config
import gui
import wx

from appModules.brailleExtenderExcel import FormulaScope, SCOPE_LABELS, ScopeFormulaDisplay

addonHandler.initTranslation()

conf = config.conf["brailleExtender"]["excel"]

# Translators: when to show formulas in row/column scope (Braille Extender Excel settings).
_SCOPE_FORMULA_LABELS = {
	ScopeFormulaDisplay.ACTIVE_CELL: _("Active cell only"),
	ScopeFormulaDisplay.ALL: _("All cells in range"),
	ScopeFormulaDisplay.NONE: _("Values only (hide formulas)"),
}


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of the Excel category in Braille Extender settings.
	title = _("Excel")
	panelDescription = _("Options for reporting Microsoft Excel cell formulas in braille.")

	def makeSettings(self, settingsSizer: wx.Sizer) -> None:
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		sHelper.addItem(wx.StaticText(self, label=self.panelDescription))

		self.cellFormula = sHelper.addItem(wx.CheckBox(self, label=_("Report cell &formulas in braille")))
		self.cellFormula.SetValue(conf["cellFormula"])
		self.cellFormula.Bind(wx.EVT_CHECKBOX, self._onChanged)

		self.cellFormulaScope = sHelper.addLabeledControl(
			_("Formula &scope:"),
			wx.Choice,
			choices=[SCOPE_LABELS[scope] for scope in FormulaScope],
		)
		try:
			self.cellFormulaScope.SetSelection(
				list(FormulaScope).index(FormulaScope(conf["cellFormulaScope"]))
			)
		except ValueError:
			self.cellFormulaScope.SetSelection(0)
		self.cellFormulaScope.Bind(wx.EVT_CHOICE, self._onChanged)

		self.scopeFormulaDisplay = sHelper.addLabeledControl(
			_("Show &formulas in row/column scope:"),
			wx.Choice,
			choices=[_SCOPE_FORMULA_LABELS[mode] for mode in ScopeFormulaDisplay],
		)
		try:
			self.scopeFormulaDisplay.SetSelection(
				list(ScopeFormulaDisplay).index(ScopeFormulaDisplay(conf["scopeFormulaDisplay"]))
			)
		except ValueError:
			self.scopeFormulaDisplay.SetSelection(0)
		self.scopeFormulaDisplay.Bind(wx.EVT_CHOICE, self._onChanged)

		self.cellFormulaNeighbors = sHelper.addLabeledControl(
			_("Number of cells before and after (row/column scope):"),
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=50,
			initial=int(conf["cellFormulaNeighbors"]),
		)
		self.cellFormulaSeparator = sHelper.addLabeledControl(
			_("Cell &separator (row/column scope):"),
			wx.TextCtrl,
		)
		self.cellFormulaSeparator.SetValue(conf["cellFormulaSeparator"])
		self._onChanged()

	def _rowOrColumnScope(self) -> bool:
		if not self.cellFormula.IsChecked():
			return False
		selection = self.cellFormulaScope.GetSelection()
		return 0 <= selection < len(FormulaScope) and list(FormulaScope)[selection].isRowOrColumn

	def _onChanged(self, evt: wx.CommandEvent | None = None) -> None:
		enabled = self.cellFormula.IsChecked()
		self.cellFormulaScope.Enable(enabled)
		rowCol = self._rowOrColumnScope()
		self.scopeFormulaDisplay.Enable(enabled and rowCol)
		self.cellFormulaNeighbors.Enable(rowCol)
		self.cellFormulaSeparator.Enable(rowCol)

	def onSave(self) -> None:
		from appModules.brailleExtenderExcel import schedule_excel_braille_refresh

		conf["cellFormula"] = self.cellFormula.IsChecked()
		conf["cellFormulaScope"] = list(FormulaScope)[self.cellFormulaScope.GetSelection()].value
		conf["scopeFormulaDisplay"] = list(ScopeFormulaDisplay)[self.scopeFormulaDisplay.GetSelection()].value
		conf["cellFormulaNeighbors"] = int(self.cellFormulaNeighbors.GetValue())
		conf["cellFormulaSeparator"] = self.cellFormulaSeparator.GetValue()
		schedule_excel_braille_refresh()
