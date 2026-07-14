# coding: utf-8
# autoscroll.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.

import addonHandler
import braille
import config
import configobj
import gui
import tones
import threading
import time
import ui
import wx

from logHandler import log
from .common import (
	MIN_AUTO_SCROLL_DELAY,
	DEFAULT_AUTO_SCROLL_DELAY,
	MAX_AUTO_SCROLL_DELAY,
	MIN_STEP_DELAY_CHANGE,
	MAX_STEP_DELAY_CHANGE,
)

addonHandler.initTranslation()

conf = config.conf["brailleExtender"]["autoScroll"]


def is_be_auto_scroll_active(handler=None) -> bool:
	"""True when Braille Extender's autoscroll thread is running on ``handler``."""
	handler = handler or braille.handler
	return handler is not None and getattr(handler, "_auto_scroll", None) is not None


def stop_nvda_core_autoscroll(handler=None) -> None:
	"""Disable NVDA's built-in braille auto-scroll (NVDA 2026.2+), if available."""
	handler = handler or braille.handler
	if handler is None:
		return
	auto_scroll = getattr(handler, "autoScroll", None)
	if not callable(auto_scroll):
		return
	try:
		auto_scroll(enable=False)
	except Exception:
		log.debugWarning("could not disable NVDA core auto scroll", exc_info=True)


class AutoScroll(threading.Thread):
	_continue = True

	def _next_delay(self):
		if conf["adjustToContent"]:
			return get_dynamic_auto_scroll_delay()
		return get_auto_scroll_delay()

	def run(self):
		while self._continue:
			if braille.handler.buffer is not braille.handler.mainBuffer:
				time.sleep(0.2)
				continue
			next_delay = self._next_delay() / 1000
			if next_delay < 0:
				next_delay = 0
			time.sleep(next_delay)
			if self._continue:
				try:
					stop_nvda_core_autoscroll()
					braille.handler.scrollForward()
				except wx._core.wxAssertionError as err:
					log.error(err)
				# HACK: windowStartPos and windowEndPos take a some time to
				# refresh
				time.sleep(0.1)

	def stop(self):
		self._continue = False


def get_dynamic_auto_scroll_delay(buffer=None):
	if not buffer:
		buffer = braille.handler.buffer
	size_window = buffer.windowEndPos - buffer.windowStartPos
	display_size = braille.handler.displaySize
	if display_size and size_window:
		delay = get_auto_scroll_delay()
		dynamic_delay = int(size_window / display_size * delay)
		return dynamic_delay
	return get_auto_scroll_delay()


def get_auto_scroll_delay() -> int:
	key = f"delay_{braille.handler.display.name}"
	if key in conf:
		try:
			return int(conf[key])
		except (TypeError, ValueError):
			pass
	return DEFAULT_AUTO_SCROLL_DELAY


def set_auto_scroll_delay(delay):
	key = f"delay_{braille.handler.display.name}"
	try:
		conf[key] = delay
		return True
	except configobj.validate.VdtValueTooSmallError:
		return False


def increase_auto_scroll_delay(self):
	cur_delay = get_auto_scroll_delay()
	if cur_delay:
		new_delay = cur_delay + conf["stepDelayChange"]
	set_auto_scroll_delay(new_delay)


def decrease_auto_scroll_delay(self):
	cur_delay = get_auto_scroll_delay()
	if cur_delay:
		new_delay = cur_delay - conf["stepDelayChange"]
	set_auto_scroll_delay(new_delay)


def report_auto_scroll_delay(self):
	cur_delay = get_auto_scroll_delay()
	ui.message(_("{delay} ms").format(delay=cur_delay))


def toggle_auto_scroll(self):
	if self._auto_scroll:
		self._auto_scroll.stop()
		self._auto_scroll = None
		stop_nvda_core_autoscroll(self)
		tones.beep(100, 100)
	else:
		stop_nvda_core_autoscroll(self)
		self._auto_scroll = self.AutoScroll()
		self._auto_scroll.start()
		tones.beep(300, 100)


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = _("Auto scroll")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: label of a dialog.
		label = _("Autoscroll &delay for the active braille display (ms):")
		self.autoScrollDelay = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=MIN_AUTO_SCROLL_DELAY,
			max=MAX_AUTO_SCROLL_DELAY,
			initial=int(get_auto_scroll_delay()),
		)
		# Translators: label of a dialog.
		label = _("&Step for delay change (ms):")
		self.stepDelayChange = sHelper.addLabeledControl(
			label,
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=MIN_STEP_DELAY_CHANGE,
			max=MAX_STEP_DELAY_CHANGE,
			initial=int(conf["stepDelayChange"]),
		)
		# Translators: label of a dialog.
		label = _("&Adjust the delay to content")
		self.adjustToContent = sHelper.addItem(wx.CheckBox(self, label=label))
		self.adjustToContent.SetValue(conf["adjustToContent"])
		# Translators: label of a dialog.
		label = _("Always ignore &blank line")
		self.ignoreBlankLine = sHelper.addItem(wx.CheckBox(self, label=label))
		self.ignoreBlankLine.SetValue(conf["ignoreBlankLine"])

	def onSave(self):
		set_auto_scroll_delay(self.autoScrollDelay.Value)
		conf["stepDelayChange"] = self.stepDelayChange.Value
		conf["adjustToContent"] = self.adjustToContent.IsChecked()
		conf["ignoreBlankLine"] = self.ignoreBlankLine.IsChecked()
