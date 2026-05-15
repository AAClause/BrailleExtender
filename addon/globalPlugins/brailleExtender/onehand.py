# coding: utf-8
# onehand.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.
import addonHandler
import gui
import wx

addonHandler.initTranslation()
import config
import speech
from .huc import unicodeBrailleToDescription, cellDescriptionsToUnicodeBraille

ONE_SIDE = "side"
BOTH_SIDES = "sides"
DOT_BY_DOT = "dot"

INPUT_METHODS = {
	ONE_SIDE: _("Fill a cell in two stages using one side only"),
	BOTH_SIDES: _("Fill a cell in two stages using both sides"),
	DOT_BY_DOT: _("Fill a cell dots by dots"),
}

endChar = True


def process(self, dots):
	global endChar
	addSpace = False
	method = config.conf["brailleExtender"]["oneHandedMode"]["inputMethod"]
	pos = self.untranslatedStart + self.untranslatedCursorPos
	continue_ = True
	endWord = False
	if method == BOTH_SIDES:
		endChar = not endChar
		if dots == 0:
			endChar = endWord = True
			addSpace = True
	elif method == ONE_SIDE:
		endChar = not endChar
		if endChar:
			equiv = "045645688"
		else:
			equiv = "012312377"
			if dots == 0:
				addSpace = True
		if dots:
			translatedBufferBrailleDots = 0
			if self.bufferBraille:
				translatedBufferBraille = chr(self.bufferBraille[-1] | 0x2800)
				translatedBufferBrailleDots = unicodeBrailleToDescription(translatedBufferBraille)
			translatedDots = chr(dots | 0x2800)
			translatedDotsBrailleDots = unicodeBrailleToDescription(translatedDots)
			newDots = ""
			for dot in translatedDotsBrailleDots:
				dot = int(dot)
				if dots >= 0 and dot < 9:
					newDots += equiv[dot]
			newDots = "".join(sorted(set(newDots)))
			if not newDots:
				newDots = "0"
			dots = ord(cellDescriptionsToUnicodeBraille(newDots)) - 0x2800
	elif method == DOT_BY_DOT:
		endChar = dots == 0
		translatedBufferBrailleDots = "0"
		if self.bufferBraille:
			translatedBufferBraille = chr(self.bufferBraille[-1] | 0x2800)
			translatedBufferBrailleDots = unicodeBrailleToDescription(translatedBufferBraille)
		translatedDots = chr(dots | 0x2800)
		translatedDotsBrailleDots = unicodeBrailleToDescription(translatedDots)
		for dot in translatedDotsBrailleDots:
			if dot not in translatedBufferBrailleDots:
				translatedBufferBrailleDots += dot
			else:
				translatedBufferBrailleDots = translatedBufferBrailleDots.replace(dot, "")
		if not translatedBufferBrailleDots:
			translatedBufferBrailleDots = "0"
		newDots = "".join(sorted(set(translatedBufferBrailleDots)))
		dots = ord(cellDescriptionsToUnicodeBraille(newDots)) - 0x2800
	else:
		speech.speakMessage(_("Unsupported input method"))
		self.flushBuffer()
		return False, False
	if endChar:
		if not self.bufferBraille:
			self.bufferBraille.insert(pos, 0)
		if method == DOT_BY_DOT:
			self.bufferBraille[-1] = dots
		else:
			self.bufferBraille[-1] |= dots
		if not endWord:
			endWord = self.bufferBraille[-1] == 0
		if method == DOT_BY_DOT:
			self.bufferBraille.append(0)
		self.untranslatedCursorPos += 1
		if addSpace:
			self.bufferBraille.append(0)
			self.untranslatedCursorPos += 1
	else:
		continue_ = False
		if self.bufferBraille and method == DOT_BY_DOT:
			self.bufferBraille[-1] = dots
		else:
			self.bufferBraille.insert(pos, dots)
		self._reportUntranslated(pos)
	return continue_, endWord


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("One-handed mode")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.featureEnabled = sHelper.addItem(wx.CheckBox(self, label=_("Enable &one-handed mode")))
		self.featureEnabled.SetValue(config.conf["brailleExtender"]["oneHandedMode"]["enabled"])
		self.featureEnabled.Bind(wx.EVT_CHECKBOX, self.onFeatureEnabled)
		choices = list(INPUT_METHODS.values())
		itemToSelect = list(INPUT_METHODS.keys()).index(
			config.conf["brailleExtender"]["oneHandedMode"]["inputMethod"]
		)
		self.inputMethod = sHelper.addLabeledControl(_("Input &method"), wx.Choice, choices=choices)
		self.inputMethod.SetSelection(itemToSelect)
		self.onFeatureEnabled(None)

	def onFeatureEnabled(self, evt):
		if self.featureEnabled.IsChecked():
			self.inputMethod.Enable()
		else:
			self.inputMethod.Disable()

	def onSave(self):
		config.conf["brailleExtender"]["oneHandedMode"]["enabled"] = self.featureEnabled.IsChecked()
		config.conf["brailleExtender"]["oneHandedMode"]["inputMethod"] = list(INPUT_METHODS.keys())[
			self.inputMethod.GetSelection()
		]
