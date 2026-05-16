# coding: utf-8
# addonhelp.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2025 André-Abush CLAUSE and contributors, released under GPL.

from __future__ import annotations

import os
import re
from collections import OrderedDict
from typing import Any

import addonHandler
import braille
import config
import cursorManager
import globalCommands
import globalVars
import languageHandler
import queueHandler
import ui
from logHandler import log

addonHandler.initTranslation()
from . import addoncfg
from . import utils
from .common import addonName, addonSummary, addonVersion, punctuationSeparator


def open_user_guide() -> None:
	"""Open the bundled user guide (NVDA manifest ``docFileName``, usually ``readme.html``)."""
	if globalVars.appArgs.secure:
		ui.message(_("User guide is not available in secure mode."))
		return
	addon = addonHandler.getCodeAddon()
	if addon is None:
		ui.message(_("Could not locate the Braille Extender add-on bundle."))
		return
	doc_name = addon.manifest.get("docFileName", "readme.html")
	lang_full = languageHandler.getLanguage()
	candidates: list[str] = []
	for cand in (lang_full, lang_full.split("_")[0] if "_" in lang_full else lang_full, "en"):
		if cand not in candidates:
			candidates.append(cand)
	doc_path: str | None = None
	for cand in candidates:
		p = os.path.join(addon.path, "doc", cand, doc_name)
		if os.path.isfile(p):
			doc_path = p
			break
	if not doc_path:
		ui.message(
			_(
				"User guide not found ({doc}). Install a built copy of the add-on or see README.md in the source tree."
			).format(doc=doc_name)
		)
		return

	def _open() -> None:
		try:
			os.startfile(doc_path)  # noqa: S606
		except Exception:
			log.debugWarning("Failed to open user guide", exc_info=True)
			ui.message(_("Could not open the user guide."))

	queueHandler.queueFunction(queueHandler.eventQueue, _open)


def show_gesture_reference(instance_gp: Any) -> None:
	"""Show a browseable HTML summary of profile and keyboard bindings."""
	GestureReferenceSummary(instance_gp).show()


class GestureReferenceSummary:
	"""Browseable gesture and profile listing for the current display."""

	def __init__(self, instance_gp: Any) -> None:
		self.instance_gp = instance_gp

	def show(self) -> None:
		if not self.instance_gp:
			return
		gestures = self.instance_gp.getGestures()
		doc = "".join(
			[
				f"<h1>{addonSummary} {addonVersion} — ",
				_("Gestures and profiles"),
				"</h1>",
				"<p>",
				_(
					"This window lists bindings that depend on your braille display profile and the add-on’s keyboard assignments. "
					"Concepts, settings, and credits are in the user guide—open User guide from the NVDA menu under Braille Extender."
				),
				"</p>",
				'<h2 id="be-doc-profile-gestures">',
				_("Profile gestures"),
				"</h2>",
			]
		)
		if addoncfg.gesturesFileExists:
			braille_display_driver_name = addoncfg.curBD.capitalize()
			profile_name = config.conf["brailleExtender"]["profile_%s" % addoncfg.curBD]
			doc += "".join(
				[
					"<p>",
					_("Driver loaded") + f"{punctuationSeparator}: {braille_display_driver_name}<br />",
					_("Profile") + f"{punctuationSeparator}: {profile_name}",
					"</p>",
				]
			)
			m_kb: OrderedDict[str, Any] = OrderedDict()
			m_nv: OrderedDict[str, Any] = OrderedDict()
			m_w: OrderedDict[str, Any] = OrderedDict()
			for g in addoncfg.iniGestures["globalCommands.GlobalCommands"].keys():
				if "kb:" in g:
					if "+" in g:
						m_w[g] = addoncfg.iniGestures["globalCommands.GlobalCommands"][g]
					else:
						m_kb[g] = addoncfg.iniGestures["globalCommands.GlobalCommands"][g]
				else:
					m_nv[g] = addoncfg.iniGestures["globalCommands.GlobalCommands"][g]
			doc += ("<h3>" + _("Simple keys") + " (%d)</h3>") % len(m_kb)
			doc += self.translate_lst(m_kb)
			doc += ("<h3>" + _("Usual shortcuts") + " (%d)</h3>") % len(m_w)
			doc += self.translate_lst(m_w)
			doc += ("<h3>" + _("Standard NVDA commands") + " (%d)</h3>") % len(m_nv)
			doc += self.translate_lst(m_nv)
			doc += "<h3>{} ({})</h3>".format(_("Modifier keys"), len(addoncfg.iniProfile["modifierKeys"]))
			doc += self.translate_lst(addoncfg.iniProfile["modifierKeys"])
			doc += "<h3>" + _("Quick navigation keys") + "</h3>"
			doc += self.translate_lst(addoncfg.iniGestures["cursorManager.CursorManager"])
			doc += "<h3>" + _("Rotor feature") + "</h3>"
			doc += self.translate_lst(
				{
					k: addoncfg.iniProfile["miscs"][k]
					for k in addoncfg.iniProfile["miscs"]
					if "rotor" in k.lower()
				}
			) + self.translate_lst(addoncfg.iniProfile["rotor"])
			doc += ("<h3>" + _("Gadget commands") + " (%d)</h3>") % (len(addoncfg.iniProfile["miscs"]) - 2)
			doc += self.translate_lst(
				OrderedDict(
					[
						(k, addoncfg.iniProfile["miscs"][k])
						for k in addoncfg.iniProfile["miscs"]
						if k not in ["nextRotor", "priorRotor"]
					]
				)
			)
			doc += "<h3>{} ({})</h3>".format(
				_("Shortcuts defined outside add-on"),
				len(braille.handler.display.gestureMap._map),
			)
			doc += "<ul>"
			for g in braille.handler.display.gestureMap._map:
				doc += ("<li>{}{}: {}{};</li>").format(
					utils.format_gesture_identifiers(g),
					punctuationSeparator,
					utils.uncapitalize(
						re.sub(
							"^([A-Z])",
							lambda m: m.group(1).lower(),
							self.get_doc_script(braille.handler.display.gestureMap._map[g]),
						)
					),
					punctuationSeparator,
				)
			doc = re.sub(r"[  ]?;(</li>)$", r".\1", doc)
			doc += "</ul>"

			if not self.instance_gp.noKeyboarLayout() and "keyboardLayouts" in addoncfg.iniProfile:
				lb = self.instance_gp.getKeyboardLayouts()
				doc += "<h3>{}</h3>".format(_("Keyboard configurations provided"))
				doc += (
					"<p>"
					+ _("The following keyboard layouts are available for this display")
					+ f"{punctuationSeparator}</p><ol>"
				)
				doc += "".join(f"<li>{layout_name}.</li>" for layout_name in lb)
				doc += "</ol>"
		else:
			doc += (
				"<h3>"
				+ _("Warning:")
				+ "</h3><p>"
				+ _("BrailleExtender has no gesture map yet for your braille display.")
				+ "<br />"
				+ _(
					'However, you can still assign your own gestures in the "Input Gestures" dialog (under Preferences menu).'
				)
				+ "</p>"
			)
		doc += (
			'<h2 id="be-doc-system-keyboard-gestures">'
			+ _("Add-on gestures on the system keyboard")
			+ " (%s)</h2>"
		) % (len(gestures) - 4)
		doc += "<ul>"
		for g in [k for k in gestures if k.lower().startswith("kb:")]:
			if g.lower() not in [
				"kb:volumeup",
				"kb:volumedown",
				"kb:volumemute",
			] and gestures[g] not in ["logFieldsAtCursor"]:
				doc += ("<li>{}{}: {}{};</li>").format(
					utils.getKeysTranslation(g),
					punctuationSeparator,
					re.sub(
						"^([A-Z])",
						lambda m: m.group(1).lower(),
						self.get_doc_script(gestures[g]),
					),
					punctuationSeparator,
				)
		doc = re.sub(r"[  ]?;(</li>)$", r".\1", doc)
		doc += "</ul>"
		ui.browseableMessage(doc, _("%s: gestures") % addonName, True)

	def get_doc_script(self, n: str) -> str:
		"""Return localized description for a script/gesture name."""
		if n == "defaultQuickLaunches":
			n = "quickLaunch"
		doc = None
		if isinstance(n, list):
			n = str(n[-1][-1])
		if n.startswith("kb:"):
			return _("Emulates pressing %s on the system keyboard") % utils.getKeysTranslation(n)
		places = [globalCommands.commands, self.instance_gp, cursorManager.CursorManager]
		for place in places:
			func = getattr(place, ("script_%s" % n), None)
			if func:
				doc = func.__doc__
				break
		return doc if doc is not None else _("description currently unavailable for this shortcut")

	def translate_lst(self, lst: dict[str, Any]) -> str:
		doc = "<ul>"
		for g in lst:
			if "kb:" in g and "capsLock" not in g and "insert" not in g:
				if isinstance(lst[g], list):
					doc += "<li>{0}{2}: {1}{2};</li>".format(
						utils.getKeysTranslation(g),
						utils.format_gesture_identifiers(lst[g]),
						punctuationSeparator,
					)
				else:
					doc += "<li>{0}{2}: {1}{2};</li>".format(
						utils.getKeysTranslation(g),
						utils.format_gesture_identifiers(lst[g]),
						punctuationSeparator,
					)
			elif "kb:" in g:
				gt = _("caps lock") if "capsLock" in g else g
				doc += "<li>{0}{2}: {1}{2};</li>".format(
					gt.replace("kb:", ""),
					utils.format_gesture_identifiers(lst[g]),
					punctuationSeparator,
				)
			else:
				if isinstance(lst[g], list):
					doc += "<li>{}{}: {}{};</li>".format(
						utils.format_gesture_identifiers(lst[g]),
						punctuationSeparator,
						re.sub(
							"^([A-Z])",
							lambda m: m.group(1).lower(),
							utils.uncapitalize(self.get_doc_script(g)),
						),
						punctuationSeparator,
					)
				else:
					doc += "<li>{}{}: {}{};</li>".format(
						utils.format_gesture_identifiers(lst[g]),
						punctuationSeparator,
						re.sub(
							"^([A-Z])",
							lambda m: m.group(1).lower(),
							utils.uncapitalize(self.get_doc_script(g)),
						),
						punctuationSeparator,
					)
		doc = re.sub(r"[  ]?;(</li>)$", r".\1", doc)
		doc += "</ul>"
		return doc
