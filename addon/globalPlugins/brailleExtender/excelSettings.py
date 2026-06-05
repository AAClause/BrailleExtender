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

# Translators: formula display when Braille view is row or column range (Braille Extender Excel settings).
_SCOPE_FORMULA_LABELS = {
	ScopeFormulaDisplay.ACTIVE_CELL: _("Focused cell only"),
	ScopeFormulaDisplay.ALL: _("Every cell on the line"),
	ScopeFormulaDisplay.NONE: _("Values only (no formulas)"),
}


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of the Excel category in Braille Extender settings.
	title = _("Excel")
	panelDescription = _("Choose how Microsoft Excel cells and formulas appear on the braille display.")

	def makeSettings(self, settingsSizer: wx.Sizer) -> None:
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		sHelper.addItem(wx.StaticText(self, label=self.panelDescription))

		self.cellFormula = sHelper.addItem(wx.CheckBox(self, label=_("Report cell &formulas in braille")))
		self.cellFormula.SetValue(conf["cellFormula"])
		self.cellFormula.Bind(wx.EVT_CHECKBOX, self._onChanged)

		self.cellFormulaScope = sHelper.addLabeledControl(
			_("Braille &view:"),
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
			_("Formulas on row or column &line:"),
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
			_("Cells on each side of focus (&row/column line):"),
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=50,
			initial=int(conf["cellFormulaNeighbors"]),
		)
		self.cellFormulaSeparator = sHelper.addLabeledControl(
			_("&Separator between cells on the line:"),
			wx.TextCtrl,
		)
		self.cellFormulaSeparator.SetValue(conf["cellFormulaSeparator"])

		# Translators: Label for the custom text shown at the start of an Excel row-range braille line.
		self.rowAxisPrefix = sHelper.addLabeledControl(_("&Row line prefix:"), wx.TextCtrl)
		self.rowAxisPrefix.SetValue(conf["rowAxisPrefix"])
		# Translators: Label for the custom text shown at the start of an Excel column-range braille line.
		self.columnAxisPrefix = sHelper.addLabeledControl(_("&Column line prefix:"), wx.TextCtrl)
		self.columnAxisPrefix.SetValue(conf["columnAxisPrefix"])
		# Translators: Hint under the row/column line prefix fields in Braille Extender Excel settings.
		sHelper.addItem(
			wx.StaticText(
				self,
				label=_(
					"Leave empty to use the translated default. "
					"Do not type a space at the end; one space is added automatically before the cell address."
				),
			)
		)
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
		self.rowAxisPrefix.Enable(rowCol)
		self.columnAxisPrefix.Enable(rowCol)

	def onSave(self) -> None:
		from appModules.brailleExtenderExcel import schedule_excel_braille_refresh

		conf["cellFormula"] = self.cellFormula.IsChecked()
		conf["cellFormulaScope"] = list(FormulaScope)[self.cellFormulaScope.GetSelection()].value
		conf["scopeFormulaDisplay"] = list(ScopeFormulaDisplay)[self.scopeFormulaDisplay.GetSelection()].value
		conf["cellFormulaNeighbors"] = int(self.cellFormulaNeighbors.GetValue())
		conf["cellFormulaSeparator"] = self.cellFormulaSeparator.GetValue()
		conf["rowAxisPrefix"] = self.rowAxisPrefix.GetValue().strip()
		conf["columnAxisPrefix"] = self.columnAxisPrefix.GetValue().strip()
		schedule_excel_braille_refresh()
