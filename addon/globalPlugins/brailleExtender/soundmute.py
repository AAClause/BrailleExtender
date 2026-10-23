# soundmute.py - Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush CLAUSE, released under GPL.
"""Keep NVDA completely silent while speech is off (optional).

When ``muteSoundsWithSpeech`` is enabled and NVDA's speech mode is "off", every wave file
(error sound, browse/focus mode sounds, add-on sounds...) and every beep (progress bars,
mouse coordinates...) is cancelled through NVDA's ``nvwave.decide_playWaveFile`` and
``tones.decide_beep`` extension points (available on all supported NVDA versions).

The deciders look at the current speech mode on each call, so NVDA becomes audible again as
soon as speech is turned back on, whatever command was used to change the speech mode.
"""

from __future__ import annotations

import config
import nvwave
import tones

from . import utils

_registered = False


def is_enabled() -> bool:
	return bool(config.conf["brailleExtender"]["muteSoundsWithSpeech"])


def is_muted() -> bool:
	"""True when NVDA sounds are currently being suppressed."""
	return is_enabled() and utils.is_speechMode_off()


def _allowSound(**kwargs) -> bool:
	return not is_muted()


def install() -> None:
	global _registered
	if _registered:
		return
	nvwave.decide_playWaveFile.register(_allowSound)
	tones.decide_beep.register(_allowSound)
	_registered = True


def uninstall() -> None:
	global _registered
	if not _registered:
		return
	nvwave.decide_playWaveFile.unregister(_allowSound)
	tones.decide_beep.unregister(_allowSound)
	_registered = False
