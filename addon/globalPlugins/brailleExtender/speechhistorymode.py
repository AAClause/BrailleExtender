# coding: utf-8
# speechhistorymode.py
# Part of BrailleExtender addon for NVDA
# Copyright 2021-2023 Emil Hesmyr, André-Abush Clause, released under GPL.
import braille
import config
import speech
import api
import ui
import gui
import wx
import addonHandler
import globalCommands
from logHandler import log

addonHandler.initTranslation()
TETHER_SPEECH = "speech"

class SettingsDlg(gui.settingsDialogs.SettingsPanel):

	# Translators: title of a dialog.
	title = _("Speech History Mode")

	def makeSettings(self, settingsSizer):

		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: label of a dialog.
		label = _("&Number of last announcements to retain:")
		self.limit = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000000,
			initial=config.conf["brailleExtender"]["speechHistoryMode"]["limit"]
		)

		# Translators: label of a dialog.
		label = _("&Prefix entries with their position in the history")
		self.numberEntries = sHelper.addItem(wx.CheckBox(self, label=label))
		self.numberEntries.SetValue(config.conf["brailleExtender"]["speechHistoryMode"]["numberEntries"])

		# Translators: label of a dialog.
		label = _("&Read entries while browsing history")
		self.speakEntries = sHelper.addItem(wx.CheckBox(self, label=label))
		self.speakEntries.SetValue(config.conf["brailleExtender"]["speechHistoryMode"]["speakEntries"])

	def onSave(self):
		config.conf["brailleExtender"]["speechHistoryMode"]["limit"] = self.limit.Value
		config.conf["brailleExtender"]["speechHistoryMode"]["numberEntries"] = self.numberEntries.IsChecked()
		config.conf["brailleExtender"]["speechHistoryMode"]["speakEntries"] = self.speakEntries.IsChecked()


orig_speak = speech.speech.speak


def showSpeech(index, allowReadEntry=False):
	try:
		if braille.handler.getTether() == TETHER_SPEECH:
			text = speechList[index]
			if config.conf["brailleExtender"]["speechHistoryMode"]["numberEntries"]:
				size_limit = len(str(config.conf["brailleExtender"]["speechHistoryMode"]["limit"]))
				text = f"#%.{size_limit}d:{text}" % (index+1)
			region = braille.TextRegion(text)
			region.update()
			region.obj = None
			braille.handler._doNewObject([region])
			if allowReadEntry and config.conf["brailleExtender"]["speechHistoryMode"]["speakEntries"]:
				speech.cancelSpeech()
				speak([speechList[index]], saveString=False)
	except BaseException:
		pass


speechList = []
index = 0

def speak(
	speechSequence,
	saveString=True,
	allowReadEntry=False,
	*args,
	**kwargs
):
	orig_speak(speechSequence, *args, **kwargs)
	if not saveString: return
	string = ""
	for i in speechSequence:
		if isinstance(i, str):
			string += i
			if not speechSequence.index(i) == len(speechSequence) - 1:
				string += " "
	global speechList, index
	speechList.append(string)
	speechList = speechList[-config.conf["brailleExtender"]["speechHistoryMode"]["limit"]:]
	index = len(speechList) - 1
	showSpeech(index, allowReadEntry=allowReadEntry)

speech.speech.speak = speak
if hasattr(speech, "speak"):
	speech.speak = speak


def scrollBack(self):
	windowRawText = braille.handler.mainBuffer.windowRawText
	windowEndPos = braille.handler.buffer.windowEndPos
	orig_ScrollBack(self)
	if braille.handler.buffer == braille.handler.mainBuffer and braille.handler.getTether(
	) == TETHER_SPEECH and braille.handler.buffer.windowRawText == windowRawText and braille.handler.buffer.windowEndPos == windowEndPos:
		global index
		if index > 0:
			index -= 1
		showSpeech(index, allowReadEntry=True)


def scrollForward(self):
	windowRawText = braille.handler.mainBuffer.windowRawText
	windowEndPos = braille.handler.buffer.windowEndPos
	orig_ScrollForward(self)
	if braille.handler.buffer == braille.handler.mainBuffer and braille.handler.getTether(
	) == TETHER_SPEECH and braille.handler.buffer.windowRawText == windowRawText and braille.handler.buffer.windowEndPos == windowEndPos:
		global index
		if not index >= len(speechList) - 1:
			index += 1
			showSpeech(index, allowReadEntry=True)


def newBrailleMessage(self, *args, **kwargs):
	if braille.handler.getTether() != TETHER_SPEECH:
		orig_BrailleMessage(self, *args, **kwargs)


def showSpeechFromRoutingIndex(routingNumber):
	global index
	if not routingNumber:
		api.copyToClip(speechList[index])
		speak([_("Announcement copied to clipboard")], saveString=False)
	elif routingNumber == braille.handler.displaySize - 1:
		ui.browseableMessage(speechList[index])
	else:
		direction = routingNumber + 1 > braille.handler.displaySize / 2
		if direction:
			index = index - (braille.handler.displaySize - routingNumber) + 1
		else:
			index += routingNumber
		if index < 0:
			index = 0
		if index >= len(speechList):
			index = len(speechList) - 1
	showSpeech(index, allowReadEntry=True)


orig_ScrollBack = braille.BrailleBuffer.scrollBack
braille.BrailleBuffer.scrollBack = scrollBack
orig_BrailleMessage = braille.BrailleHandler.message
braille.BrailleHandler.message = newBrailleMessage
orig_ScrollForward = braille.BrailleBuffer.scrollForward
braille.BrailleBuffer.scrollForward = scrollForward
