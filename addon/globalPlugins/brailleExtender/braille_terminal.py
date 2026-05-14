# coding: utf-8
# braille_terminal.py — BrailleExtender: console / terminal review tethering
# Copyright 2016-2022 André-Abush CLAUSE, released under GPL.

"""Force NVDA's internal braille tether and region type for terminals.

NVDA uses ``BrailleHandler._tether`` (not only ``getTether()``) when building regions on
``handleGainFocus``. Overriding ``getTether()`` alone made the review cursor shape appear while
``TextInfoRegion`` still followed the caret, so display line keys did nothing until the review
cursor moved from the keyboard.
"""

from __future__ import annotations

import itertools
from typing import Any, Callable

import api
import braille
import config
import textInfos
from logHandler import log

from .utils import get_control_type


def _object_below_lock_screen(obj: Any) -> bool:
	try:
		from utils.security import objectBelowLockScreenAndWindowsIsLocked

		return bool(objectBelowLockScreenAndWindowsIsLocked(obj))
	except ImportError:
		return False
	except Exception:
		log.debugWarning("BrailleExtender: could not evaluate lock screen state", exc_info=True)
		return True


def _braille_speech_output_blocks_gain_focus(handler: Any) -> bool:
	try:
		from config.configFlags import BrailleMode

		return config.conf["braille"]["mode"] == BrailleMode.SPEECH_OUTPUT.value
	except Exception:
		return False


def _resolve_tree_interceptor_text_buffer(obj: Any) -> Any:
	if (
		getattr(obj, "treeInterceptor", None)
		and not obj.treeInterceptor.passThrough
		and obj.treeInterceptor.isReady
	):
		return obj.treeInterceptor
	return obj


def is_terminal_braille_focus_object(obj: Any) -> bool:
	"""True for ROLE_TERMINAL and for Windows Terminal's UIA document buffer."""
	if not obj:
		return False
	try:
		role = obj.role
	except Exception:
		return False
	try:
		if role == get_control_type("ROLE_TERMINAL"):
			return True
	except Exception:
		pass
	try:
		if role == get_control_type("ROLE_DOCUMENT"):
			try:
				app_name = (obj.appModule.appName or "").lower()
			except Exception:
				app_name = ""
			if "windowsterminal" in app_name or app_name in {"wt", "windows terminal"}:
				return True
	except Exception:
		pass
	return False


def _sync_review_position_to_object_caret(obj: Any) -> None:
	try:
		info = obj.makeTextInfo(textInfos.POSITION_CARET)
	except Exception:
		try:
			info = obj.makeTextInfo(textInfos.POSITION_FIRST)
		except Exception:
			log.debugWarning(
				"BrailleExtender: cannot obtain TextInfo to sync review in terminal",
				exc_info=True,
			)
			return
	try:
		info.collapse()
		api.setReviewPosition(info)
	except Exception:
		log.debugWarning("BrailleExtender: setReviewPosition for terminal failed", exc_info=True)


def _restore_tether_after_terminal(handler: Any) -> None:
	configured = config.conf["braille"]["tetherTo"]
	handler._tether = (
		handler.TETHER_FOCUS if configured == handler.TETHER_AUTO else configured
	)
	handler.mainBuffer.clear()


def make_patched_handle_gain_focus(_originals: dict[str, Any]) -> Callable[..., None]:
	"""Return a ``BrailleHandler.handleGainFocus`` replacement."""

	def handleGainFocus_brailleExtender(self, obj: Any, shouldAutoTether: bool = True) -> None:
		orig = _originals["BrailleHandler.handleGainFocus"]
		if not self.enabled:
			return
		if _braille_speech_output_blocks_gain_focus(self):
			return
		if _object_below_lock_screen(obj):
			orig(self, obj, shouldAutoTether=shouldAutoTether)
			return

		if getattr(self, "_be_terminal_review_override", False):
			resolved = _resolve_tree_interceptor_text_buffer(obj)
			if not is_terminal_braille_focus_object(resolved):
				self._be_terminal_review_override = False
				_restore_tether_after_terminal(self)

		if shouldAutoTether:
			self.setTether(self.TETHER_FOCUS, auto=True)

		ti_obj = _resolve_tree_interceptor_text_buffer(obj)
		if config.conf["brailleExtender"]["reviewModeTerminal"] and is_terminal_braille_focus_object(ti_obj):
			if self._tether != self.TETHER_REVIEW:
				self._tether = self.TETHER_REVIEW
				self.mainBuffer.clear()
			_sync_review_position_to_object_caret(ti_obj)
			self._doNewObject(
				itertools.chain(
					braille.getFocusContextRegions(ti_obj, oldFocusRegions=self.mainBuffer.regions),
					braille.getFocusRegions(ti_obj, review=True),
				)
			)
			self._be_terminal_review_override = True
			return

		if self._tether != self.TETHER_FOCUS:
			return

		self._doNewObject(
			itertools.chain(
				braille.getFocusContextRegions(ti_obj, oldFocusRegions=self.mainBuffer.regions),
				braille.getFocusRegions(ti_obj),
			)
		)

	return handleGainFocus_brailleExtender
