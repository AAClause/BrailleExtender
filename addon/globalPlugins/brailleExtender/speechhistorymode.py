# coding: utf-8
# speechhistorymode.py
# Part of BrailleExtender addon for NVDA
# Copyright 2021-2023 Emil Hesmyr, André-Abush Clause, released under GPL.

from __future__ import annotations

from typing import Any, Callable

import addonHandler
import api
import braille
import config
import gui
import speech
import ui
import wx
from logHandler import log

addonHandler.initTranslation()

TETHER_SPEECH = "speech"

_orig_speak: Callable[..., Any] | None = None
_orig_scroll_back: Callable[..., Any] | None = None
_orig_scroll_forward: Callable[..., Any] | None = None
_orig_braille_message: Callable[..., Any] | None = None
_installed = False


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("Speech History Mode")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		label = _("&Number of last announcements to retain:")
		self.limit = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=0,
			max=1000000,
			initial=config.conf["brailleExtender"]["speechHistoryMode"]["limit"],
		)
		label = _("&Prefix entries with their position in the history")
		self.numberEntries = sHelper.addItem(wx.CheckBox(self, label=label))
		self.numberEntries.SetValue(config.conf["brailleExtender"]["speechHistoryMode"]["numberEntries"])
		label = _("&Read entries while browsing history")
		self.speakEntries = sHelper.addItem(wx.CheckBox(self, label=label))
		self.speakEntries.SetValue(config.conf["brailleExtender"]["speechHistoryMode"]["speakEntries"])

	def onSave(self):
		config.conf["brailleExtender"]["speechHistoryMode"]["limit"] = self.limit.Value
		config.conf["brailleExtender"]["speechHistoryMode"]["numberEntries"] = self.numberEntries.IsChecked()
		config.conf["brailleExtender"]["speechHistoryMode"]["speakEntries"] = self.speakEntries.IsChecked()


speechList: list[str] = []
speechListIndex = 0


def showSpeech(index: int, allowReadEntry: bool = False) -> None:
	try:
		if braille.handler.getTether() == TETHER_SPEECH:
			text = speechList[index]
			if config.conf["brailleExtender"]["speechHistoryMode"]["numberEntries"]:
				size_limit = len(str(config.conf["brailleExtender"]["speechHistoryMode"]["limit"]))
				text = f"#%.{size_limit}d:{text}" % (index + 1)
			region = braille.TextRegion(text)
			region.update()
			region.obj = None
			braille.handler._doNewObject([region])
			if allowReadEntry and config.conf["brailleExtender"]["speechHistoryMode"]["speakEntries"]:
				speech.cancelSpeech()
				speak_wrapped([speechList[index]], saveString=False)
	except Exception:
		log.debugWarning("Speech history: showSpeech failed", exc_info=True)


def speak_wrapped(
	speechSequence: Any,
	saveString: bool = True,
	allowReadEntry: bool = False,
	*args: Any,
	**kwargs: Any,
) -> None:
	assert _orig_speak is not None
	_orig_speak(speechSequence, *args, **kwargs)
	if not saveString:
		return
	parts: list[str] = []
	for item in speechSequence:
		if isinstance(item, str):
			parts.append(item)
	joined = " ".join(parts)
	global speechList, speechListIndex
	speechList.append(joined)
	limit = config.conf["brailleExtender"]["speechHistoryMode"]["limit"]
	speechList = speechList[-limit:]
	speechListIndex = len(speechList) - 1
	showSpeech(speechListIndex, allowReadEntry=allowReadEntry)


def scrollBack(self: Any) -> None:
	assert _orig_scroll_back is not None
	window_raw_text = braille.handler.mainBuffer.windowRawText
	window_end_pos = braille.handler.buffer.windowEndPos
	_orig_scroll_back(self)
	if (
		braille.handler.buffer is braille.handler.mainBuffer
		and braille.handler.getTether() == TETHER_SPEECH
		and braille.handler.buffer.windowRawText == window_raw_text
		and braille.handler.buffer.windowEndPos == window_end_pos
	):
		global speechListIndex
		if speechListIndex > 0:
			speechListIndex -= 1
		showSpeech(speechListIndex, allowReadEntry=True)


def scrollForward(self: Any) -> None:
	assert _orig_scroll_forward is not None
	window_raw_text = braille.handler.mainBuffer.windowRawText
	window_end_pos = braille.handler.buffer.windowEndPos
	_orig_scroll_forward(self)
	if (
		braille.handler.buffer is braille.handler.mainBuffer
		and braille.handler.getTether() == TETHER_SPEECH
		and braille.handler.buffer.windowRawText == window_raw_text
		and braille.handler.buffer.windowEndPos == window_end_pos
	):
		global speechListIndex
		if speechListIndex < len(speechList) - 1:
			speechListIndex += 1
			showSpeech(speechListIndex, allowReadEntry=True)


def new_braille_message(self: Any, *args: Any, **kwargs: Any) -> None:
	assert _orig_braille_message is not None
	if braille.handler.getTether() != TETHER_SPEECH:
		_orig_braille_message(self, *args, **kwargs)


def showSpeechFromRoutingIndex(routing_number: int) -> None:
	global speechListIndex
	if not routing_number:
		api.copyToClip(speechList[speechListIndex])
		speak_wrapped([_("Announcement copied to clipboard")], saveString=False)
	elif routing_number == braille.handler.displaySize - 1:
		ui.browseableMessage(speechList[speechListIndex])
	else:
		direction = routing_number + 1 > braille.handler.displaySize / 2
		if direction:
			speechListIndex = speechListIndex - (braille.handler.displaySize - routing_number) + 1
		else:
			speechListIndex += routing_number
		speechListIndex = max(0, min(speechListIndex, len(speechList) - 1))
	showSpeech(speechListIndex, allowReadEntry=True)


def install() -> None:
	"""Apply speech history monkey-patches (idempotent)."""
	global _installed, _orig_speak, _orig_scroll_back, _orig_scroll_forward, _orig_braille_message
	if _installed:
		return
	_orig_speak = speech.speech.speak
	_orig_scroll_back = braille.BrailleBuffer.scrollBack
	_orig_scroll_forward = braille.BrailleBuffer.scrollForward
	_orig_braille_message = braille.BrailleHandler.message
	speech.speech.speak = speak_wrapped
	if hasattr(speech, "speak"):
		speech.speak = speak_wrapped
	braille.BrailleBuffer.scrollBack = scrollBack
	braille.BrailleBuffer.scrollForward = scrollForward
	braille.BrailleHandler.message = new_braille_message
	_installed = True
	log.debug("BrailleExtender: speech history mode patches installed")


def uninstall() -> None:
	"""Restore speech and braille hooks from install(). Safe if not installed."""
	global _installed, _orig_speak, _orig_scroll_back, _orig_scroll_forward, _orig_braille_message
	if not _installed:
		return
	try:
		if _orig_speak is not None:
			speech.speech.speak = _orig_speak
			if hasattr(speech, "speak"):
				speech.speak = _orig_speak
		if _orig_scroll_back is not None:
			braille.BrailleBuffer.scrollBack = _orig_scroll_back
		if _orig_scroll_forward is not None:
			braille.BrailleBuffer.scrollForward = _orig_scroll_forward
		if _orig_braille_message is not None:
			braille.BrailleHandler.message = _orig_braille_message
	except Exception:
		log.warning("BrailleExtender: error restoring speech history patches", exc_info=True)
	_orig_speak = _orig_scroll_back = _orig_scroll_forward = _orig_braille_message = None
	_installed = False
	log.debug("BrailleExtender: speech history mode patches uninstalled")


def is_installed() -> bool:
	return _installed
