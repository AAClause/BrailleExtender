# coding: utf-8
# BrailleExtender Addon for NVDA
# This file is covered by the GNU General Public License.
# See the file LICENSE for more details.
# Copyright (C) 2016-2023 André-Abush Clause <dev@andreabc.net>

import os
import subprocess
import time
from collections import OrderedDict

import addonHandler
import api
import braille
import brailleInput
import config
import globalCommands
import globalPluginHandler
import globalVars
import gui
import inputCore
import keyLabels
import keyboardHandler
import scriptHandler
from scriptHandler import script
import speech
import tones
import ui
import virtualBuffers
import vision
import wx
from logHandler import log

from . import addoncfg

config.conf.spec["brailleExtender"] = addoncfg.getConfspec()
from . import patches
from . import rotor
from . import advancedinput
from . import huc
from . import documentformatting
from . import objectpresentation
from . import rolelabels
from . import settings
from . import tabledictionaries
from . import undefinedchars
from . import updatecheck
from . import utils
from .common import (
	addonName,
	addonURL,
	addonVersion,
	punctuationSeparator,
	RC_NORMAL,
	RC_EMULATE_ARROWS_BEEP,
	RC_EMULATE_ARROWS_SILENT,
)

addonHandler.initTranslation()

instanceGP = None


def _modifier_keys_script_description(key_combo: str) -> str:
	"""Translatable description for braille modifier emulation scripts."""
	return _("Emulate on the system keyboard: %s") % " + ".join(
		utils.getKeysTranslation(part) or part for part in key_combo.split("+")
	)


def _brailleMessagePersistent(msg):
	"""Display a message in the main braille buffer so it stays visible (no timeout)."""
	region = braille.TextRegion(msg)
	region.obj = None
	region.update()
	braille.handler.mainBuffer.clear()
	braille.handler.mainBuffer.regions.append(region)
	braille.handler.mainBuffer.update()
	braille.handler.update()


def _restoreMainBuffer():
	"""Clear the persistent time display and restore the main braille buffer with focus/review content."""
	braille.handler.buffer = braille.handler.mainBuffer
	braille.handler.mainBuffer.clear()
	braille.handler.initialDisplay()


def _popupSettingsDialog(*args, **kwargs):
	return getattr(gui.mainFrame, "popupSettingsDialog", gui.mainFrame._popupSettingsDialog)(*args, **kwargs)


# Step size for move-in-text / text-selection rotor modes (character, word, line, …)
rotorRange = 0
HLP_browseModeInfo = ". %s" % _("If pressed twice, presents the information in browse mode")

# Freedom Scientific wiz wheel lines: do not remap (NVDA core scroll gestures).
_REVERSE_SCROLL_EXCLUDED_BRAILLE_IDS = frozenset(
	(
		"br(freedomscientific):leftwizwheelup",
		"br(freedomscientific):leftwizwheeldown",
	)
)

# Default *keyboard* shortcuts from ``@script(gesture="kb:...")`` on GlobalPlugin below.
# Braille-line bindings for the same scripts (and many others) live under
# ``Profiles/<driver>/default/profile.ini`` in ``[miscs]`` and ``[rotor]``.
#
# script_toggleBRFMode              kb:nvda+alt+f
# script_translateInBRU             kb:nvda+alt+u
# script_charsToCellDescriptions    kb:nvda+alt+i
# script_cellDescriptionsToChars    kb:nvda+alt+o
# script_advancedInput              kb:nvda+windows+i
# script_undefinedCharsDesc         kb:nvda+windows+u
# script_switchInputBrailleTable    kb:shift+NVDA+i
# script_switchOutputBrailleTable   kb:shift+NVDA+u
# script_currentBrailleTable        kb:shift+NVDA+p
# script_reload_brailledisplay1     kb:nvda+j
# script_reload_brailledisplay2     kb:nvda+shift+j
# script_addDictionaryEntry         kb:nvda+alt+y
#
# No default ``gesture=`` (assign in NVDA Input Gestures or use a display profile):
# - script_volumePlus / script_volumeMinus / script_toggleVolume (avoid grabbing volume keys)
# - script_logFieldsAtCursor (developer-only)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = addonName
	brailleKeyboardLocked = False
	lastShortcutPerformed = None
	hideDots78 = False
	BRFMode = False
	advancedInput = False
	modifiersLocked = False
	hourDatePlayed = False
	hourDateTimer = None
	modifiers = set()
	_pGestures = OrderedDict()
	rotorGES = {}
	noKC = None
	if not addoncfg.noUnicodeTable:
		backupInputTable = brailleInput.handler.table
	backupMessageTimeout = None

	def __init__(self):
		startTime = time.time()
		super(globalPluginHandler.GlobalPlugin, self).__init__()
		patches.instanceGP = self
		patches.apply_patches()
		braille.TextInfoRegion._addTextWithFields = documentformatting.decorator(
			braille.TextInfoRegion._addTextWithFields, "addTextWithFields"
		)
		braille.TextInfoRegion.update = documentformatting.decorator(braille.TextInfoRegion.update, "update")
		braille.TextInfoRegion._getTypeformFromFormatField = documentformatting.decorator(
			braille.TextInfoRegion._getTypeformFromFormatField, "_getTypeformFromFormatField"
		)
		settings.instanceGP = self
		addoncfg.loadConf()
		if not addoncfg.noUnicodeTable:
			self.reloadBrailleTables(apply_handlers=True)
		rotor.reload_from_config()
		addoncfg.initGestures()
		addoncfg.loadGestures()
		self.gesturesInit()
		checkingForced = False
		if config.conf["brailleExtender"]["lastNVDAVersion"] != updatecheck.versionInfo.version:
			config.conf["brailleExtender"]["lastNVDAVersion"] = updatecheck.versionInfo.version
			checkingForced = True
		delayChecking = (
			86400 if config.conf["brailleExtender"]["updateChannel"] != addoncfg.CHANNEL_stable else 604800
		)
		if (
			not globalVars.appArgs.secure
			and config.conf["brailleExtender"]["autoCheckUpdate"]
			and (
				checkingForced
				or (time.time() - config.conf["brailleExtender"]["lastCheckUpdate"]) > delayChecking
			)
		):
			updatecheck.checkUpdates(True)
			config.conf["brailleExtender"]["lastCheckUpdate"] = time.time()
		self.backup__brailleTableDict = config.conf["braille"]["translationTable"]
		if config.conf["brailleExtender"]["reverseScrollBtns"]:
			self.reverseScrollBtns()
		self.createMenu()
		advancedinput.initialize()
		if config.conf["brailleExtender"]["features"]["roleLabels"]:
			rolelabels.loadRoleLabels()
		objectpresentation.loadOrderProperties()
		documentformatting.load_tags()
		log.info(f"{addonName} {addonVersion} loaded ({round(time.time() - startTime, 2)}s)")

	def event_gainFocus(self, obj, nextHandler):
		isVirtualBuff = obj is not None and isinstance(obj.treeInterceptor, virtualBuffers.VirtualBuffer)
		rotor.apply_focus_context(isVirtualBuff, self)

		if "tabSize_%s" % addoncfg.curBD not in config.conf["brailleExtender"].copy().keys():
			self.onReload(None, 1)
		if self.hourDatePlayed:
			self.script_hourDate(None)
		if self.autoTestPlayed:
			self.script_autoTest(None)
		if braille.handler is not None and addoncfg.curBD != braille.handler.display.name:
			addoncfg.curBD = braille.handler.display.name
			self.onReload(None, 1)

		if self.backup__brailleTableDict != config.conf["braille"]["translationTable"]:
			self.reloadBrailleTables()
		nextHandler()

	def event_foreground(self, obj, nextHandler):
		if patches.is_patch_applied("braille_handler") and patches.get_auto_scroll():
			braille.handler.toggle_auto_scroll()
		nextHandler()

	_oldObj = None
	_oldVal = None

	def event_valueChange(self, obj, nextHandler):
		if not config.conf["brailleExtender"]["objectPresentation"]["progressBarUpdate"]:
			return nextHandler()
		List = objectpresentation.validProgressBar(obj)
		if not List or False in List:
			return nextHandler()
		try:
			if self._oldObj == obj and self._oldVal == obj.value:
				return nextHandler()
			value = obj.value
			self._oldObj = obj
			self._oldVal = value
			if config.conf["brailleExtender"]["objectPresentation"]["progressBarUpdate"] == 1:  # show value
				braille.handler.message(value)
			else:
				string = (
					objectpresentation.generateProgressBarString(value, braille.handler.displaySize) or value
				)
				braille.handler.message(string)
		except BaseException as e:
			log.error(e)
		nextHandler()

	def event_nameChange(self, obj, nextHandler):
		if config.conf["brailleExtender"]["advanced"]["refreshForegroundObjNameChange"]:
			fg = api.getForegroundObject()
			visibleRegions = list(braille.handler.mainBuffer.visibleRegions)
			if (
				len(visibleRegions) > 1
				and visibleRegions[0].obj is not api.getFocusObject()
				and visibleRegions[0].obj is not fg
			):
				visibleRegions[0].obj = fg
			braille.handler.handleUpdate(fg)
			vision.handler.handleUpdate(fg, property="name")
		nextHandler()

	def createMenu(self):
		self.submenu = wx.Menu()
		item = self.submenu.Append(
			wx.ID_ANY,
			_("&User guide"),
			_("Opens the add-on user guide (readme.html) in your default viewer."),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda event: self.script_getHelp(None), item)
		item = self.submenu.Append(
			wx.ID_ANY,
			_("&Gestures for this display…"),
			_("Shows a browseable summary of braille profile bindings and add-on keyboard shortcuts."),
		)
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU, lambda event: self.script_showGestureReference(None), item
		)
		item = self.submenu.Append(wx.ID_ANY, _("&Settings..."), _("Opens the addons' settings."))
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU, lambda event: wx.CallAfter(_popupSettingsDialog, settings.AddonSettingsDialog), item
		)
		dictionariesMenu = wx.Menu()
		self.submenu.AppendSubMenu(
			dictionariesMenu, _("Table &dictionaries"), _("'Braille dictionaries' menu")
		)
		item = dictionariesMenu.Append(
			wx.ID_ANY,
			_("&Global dictionary"),
			_("A dialog where you can set global dictionary by adding dictionary entries to the list."),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onDefaultDictionary, item)
		item = dictionariesMenu.Append(
			wx.ID_ANY,
			_("&Table dictionary"),
			_(
				"A dialog where you can set table-specific dictionary by adding dictionary entries to the list."
			),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onTableDictionary, item)
		item = dictionariesMenu.Append(
			wx.ID_ANY,
			_("Te&mporary dictionary"),
			_("A dialog where you can set temporary dictionary by adding dictionary entries to the list."),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onTemporaryDictionary, item)

		item = self.submenu.Append(
			wx.ID_ANY,
			_("&Custom braille tables..."),
			_("Add, remove, and edit your own Liblouis braille tables (NVDA 2024.3+)."),
		)
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda event: wx.CallAfter(_popupSettingsDialog, settings.CustomBrailleTablesDlg),
			item,
		)

		item = self.submenu.Append(
			wx.ID_ANY, _("Advanced &input mode dictionary..."), _("Advanced input mode configuration")
		)
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU, lambda event: _popupSettingsDialog(advancedinput.AdvancedInputModeDlg), item
		)
		item = self.submenu.Append(
			wx.ID_ANY, "%s..." % _("&Quick launches"), _("Quick launches configuration")
		)
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU, lambda event: wx.CallAfter(_popupSettingsDialog, settings.QuickLaunchesDlg), item
		)
		item = self.submenu.Append(
			wx.ID_ANY, _("Braille input table &overview"), _("Overview of the current input braille table")
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda event: self.script_getTableOverview(None), item)
		item = self.submenu.Append(wx.ID_ANY, _("&Reload add-on"), _("Reload this add-on."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onReload, item)
		item = self.submenu.Append(
			wx.ID_ANY, _("Check for &update..."), _("Checks if Braille Extender update is available")
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onUpdate, item)
		item = self.submenu.Append(wx.ID_ANY, _("&Website"), _("Open addon's website."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onWebsite, item)
		item = self.submenu.Append(
			wx.ID_ANY,
			_("Get the latest template &translation file (.pot)"),
			_("Opens the URL to download the latest Portable Object Template file of the add-on"),
		)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_pot_file, item)
		self.submenu_item = gui.mainFrame.sysTrayIcon.menu.Insert(
			2, wx.ID_ANY, "%s (%s)" % (_("&Braille Extender"), addonVersion), self.submenu
		)

	def reloadBrailleTables(self, *, apply_handlers: bool = False):
		from . import braille_tables

		braille_tables.reload_liblouis_chain(apply_handlers=apply_handlers)
		self.backup__brailleTableDict = config.conf["braille"]["translationTable"]
		tabledictionaries.notify_invalid_dictionary_tables()
		if config.conf["brailleExtender"]["tabSpace"]:
			liblouisDef = r"always \t " + ("0-" * addoncfg.getTabSize()).strip("-")
			patches.louis.compileString(utils.getCurrentBrailleTables(), bytes(liblouisDef, "ASCII"))
		undefinedchars.setUndefinedChar()
		utils.refresh_braille_for_current_focus()

	@staticmethod
	def onDefaultDictionary(evt):
		_popupSettingsDialog(tabledictionaries.DictionaryDlg, _("Global dictionary"), "default")

	@staticmethod
	def onTableDictionary(evt):
		outTable = addoncfg.tablesTR[addoncfg.tablesFN.index(utils.getTranslationTable())]
		_popupSettingsDialog(
			tabledictionaries.DictionaryDlg, _("Table dictionary ({})").format(outTable), "table"
		)

	@staticmethod
	def onTemporaryDictionary(evt):
		_popupSettingsDialog(tabledictionaries.DictionaryDlg, _("Temporary dictionary"), "tmp")

	def getGestureWithBrailleIdentifier(self, gesture=""):
		return ("br(%s):" % addoncfg.curBD if ":" not in gesture else "") + gesture

	def gesturesInit(self):
		# rotor gestures
		if "rotor" in addoncfg.iniProfile.keys():
			for k in addoncfg.iniProfile["rotor"]:
				if isinstance(addoncfg.iniProfile["rotor"][k], list):
					for gesture_id in addoncfg.iniProfile["rotor"][k]:
						self.rotorGES[self.getGestureWithBrailleIdentifier(gesture_id)] = k
				else:
					self.rotorGES[self.getGestureWithBrailleIdentifier(addoncfg.iniProfile["rotor"][k])] = k
			log.debug(self.rotorGES)
		else:
			log.debug("No rotor gestures for this profile")

		# keyboard layout gestures
		gK = OrderedDict()
		try:
			cK = (
				addoncfg.iniProfile["keyboardLayouts"][
					config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD]
				]
				if config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD]
				and config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD]
				in addoncfg.iniProfile["keyboardLayouts"]
				is not None
				else addoncfg.iniProfile["keyboardLayouts"].keys()[0]
			)
			for k in cK:
				if k in ["enter", "backspace"]:
					if isinstance(cK[k], list):
						for gesture_id in cK[k]:
							gK[
								inputCore.normalizeGestureIdentifier(
									self.getGestureWithBrailleIdentifier(gesture_id)
								)
							] = "kb:%s" % k
					else:
						gK["kb:%s" % k] = inputCore.normalizeGestureIdentifier(
							self.getGestureWithBrailleIdentifier(cK[k])
						)
				elif k in ["braille_dots", "braille_enter", "braille_translate"]:
					if isinstance(cK[k], list):
						for i in range(len(cK[k])):
							if ":" not in cK[k][i]:
								cK[k][i] = inputCore.normalizeGestureIdentifier(
									self.getGestureWithBrailleIdentifier(cK[k][i])
								)
					else:
						if ":" not in cK[k]:
							cK[k] = self.getGestureWithBrailleIdentifier(cK[k])
					gK[k] = cK[k]
			inputCore.manager.localeGestureMap.update({"globalCommands.GlobalCommands": gK})
			self.noKC = False
			log.debug(
				"Keyboard conf found, loading layout `%s`"
				% config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD]
			)
		except BaseException:
			log.debug("No keyboard conf found")
			self.noKC = True
		if addoncfg.gesturesFileExists:
			self._pGestures = OrderedDict()
			for k, v in addoncfg.iniProfile["modifierKeys"].items() + [
				k for k in addoncfg.iniProfile["miscs"].items() if k[0] != "defaultQuickLaunches"
			]:
				if isinstance(v, list):
					for i, gesture in enumerate(v):
						self._pGestures[
							inputCore.normalizeGestureIdentifier(
								self.getGestureWithBrailleIdentifier(gesture)
							)
						] = k
				else:
					self._pGestures[
						inputCore.normalizeGestureIdentifier(self.getGestureWithBrailleIdentifier(v))
					] = k
		self.bindGestures(self._pGestures)
		self.loadQuickLaunchesGes()

	def loadQuickLaunchesGes(self):
		self.bindGestures(
			{
				k: "quickLaunch"
				for k in config.conf["brailleExtender"]["quickLaunches"].copy().keys()
				if "(%s" % addoncfg.curBD in k
			}
		)

	def bindRotorGES(self):
		for k in self.rotorGES:
			try:
				self.removeGestureBinding(k)
			except BaseException:
				pass
		rid = rotor.current_rotor_id()
		if rid == rotor.RotorId.default:
			return
		if rotor.should_bind_full_rotor_gestures(rid):
			self.bindGestures(self.rotorGES)
		else:
			for k in self.rotorGES:
				if self.rotorGES[k] not in ["selectElt", "nextSetRotor", "priorSetRotor"]:
					self.bindGestures({k: self.rotorGES[k]})

	@script(description=_("Select the previous rotor category (links, headings, review, and so on)"))
	def script_priorRotor(self, gesture):
		msg = rotor.advance_rotor(-1)
		self.bindRotorGES()
		return ui.message(msg)

	@script(description=_("Select the next rotor category"))
	def script_nextRotor(self, gesture):
		msg = rotor.advance_rotor(1)
		self.bindRotorGES()
		return ui.message(msg)

	@staticmethod
	def getCurrentSelectionRange(pretty=True, back=False):
		if pretty:
			labels = [_("Character"), _("Word"), _("Line"), _("Paragraph"), _("Page"), _("Document")]
			return labels[rotorRange]
		keys = [
			("leftarrow", "rightarrow"),
			("control+leftarrow", "control+rightarrow"),
			("uparrow", "downarrow"),
			("control+uparrow", "control+downarrow"),
			("pageup", "pagedown"),
			("control+home", "control+end"),
		]
		if rotor.current_rotor_id() == rotor.RotorId.textSelection:
			return "shift+%s" % (keys[rotorRange][0] if back else keys[rotorRange][1])
		return keys[rotorRange][0] if back else keys[rotorRange][1]

	def switchSelectionRange(self, previous=False):
		global rotorRange
		if previous:
			rotorRange = rotorRange - 1 if rotorRange > 0 else 5
		else:
			rotorRange = rotorRange + 1 if rotorRange < 5 else 0
		ui.message(self.getCurrentSelectionRange())

	@staticmethod
	def moveTo(direction, gesture=None):
		obj = api.getFocusObject()
		if obj is None:
			return ui.message(_("Not available here"))
		ti = rotor.resolve_document_tree_interceptor(obj)
		if ti is None:
			return ui.message(_("Not available here"))
		func = getattr(
			ti,
			rotor.browse_mode_script_attr(direction, rotor.current_rotor_id()),
			None,
		)
		if func:
			return func(gesture)
		return ui.message(_("Not available here"))

	@script(
		description=_(
			"Rotor: move forward (next character, link, review line, and so on, depending on the rotor)"
		)
	)
	def script_nextEltRotor(self, gesture):
		rid = rotor.current_rotor_id()
		if rid == rotor.RotorId.default:
			return self.sendComb("rightarrow", gesture)
		if rid in (rotor.RotorId.moveInText, rotor.RotorId.textSelection):
			return self.sendComb(self.getCurrentSelectionRange(False), gesture)
		if rid == rotor.RotorId.object:
			self.sendComb("nvda+shift+rightarrow", gesture)
		elif rid == rotor.RotorId.review:
			scriptHandler.executeScript(globalCommands.commands.script_braille_scrollForward, gesture)
		elif rid == rotor.RotorId.moveInTable:
			self.sendComb("control+alt+rightarrow", gesture)
		elif rid == rotor.RotorId.Error:
			return self.moveTo("next", gesture)
		elif rid == rotor.RotorId.prefInputTable:
			return self._cyclePreferredInputTable(1)
		elif rid == rotor.RotorId.prefOutputTable:
			return self._cyclePreferredOutputTable(1)
		else:
			return self.moveTo("next", gesture)

	@script(description=_("Rotor: move backward (previous character, link, review line, and so on)"))
	def script_priorEltRotor(self, gesture):
		rid = rotor.current_rotor_id()
		if rid == rotor.RotorId.default:
			return self.sendComb("leftarrow", gesture)
		if rid in (rotor.RotorId.moveInText, rotor.RotorId.textSelection):
			return self.sendComb(self.getCurrentSelectionRange(False, True), gesture)
		if rid == rotor.RotorId.object:
			return self.sendComb("nvda+shift+leftarrow", gesture)
		if rid == rotor.RotorId.review:
			return scriptHandler.executeScript(globalCommands.commands.script_braille_scrollBack, gesture)
		if rid == rotor.RotorId.moveInTable:
			return self.sendComb("control+alt+leftarrow", gesture)
		if rid == rotor.RotorId.Error:
			return self.moveTo("previous", gesture)
		if rid == rotor.RotorId.prefInputTable:
			return self._cyclePreferredInputTable(-1)
		if rid == rotor.RotorId.prefOutputTable:
			return self._cyclePreferredOutputTable(-1)
		return self.moveTo("previous", gesture)

	@script(
		description=_(
			"Rotor: next step (next line, next object group, larger selection unit, depending on the rotor)"
		)
	)
	def script_nextSetRotor(self, gesture):
		rid = rotor.current_rotor_id()
		if rid in (rotor.RotorId.moveInText, rotor.RotorId.textSelection):
			return self.switchSelectionRange()
		if rid == rotor.RotorId.object:
			self.sendComb("nvda+shift+downarrow", gesture)
		elif rid == rotor.RotorId.review:
			scriptHandler.executeScript(globalCommands.commands.script_braille_nextLine, gesture)
		elif rid == rotor.RotorId.moveInTable:
			self.sendComb("control+alt+downarrow", gesture)
		else:
			return self.sendComb("downarrow", gesture)

	@script(description=_("Rotor: previous step (previous line, object group, or selection unit)"))
	def script_priorSetRotor(self, gesture):
		rid = rotor.current_rotor_id()
		if rid in (rotor.RotorId.moveInText, rotor.RotorId.textSelection):
			self.switchSelectionRange(True)
		elif rid == rotor.RotorId.object:
			self.sendComb("nvda+shift+uparrow", gesture)
		elif rid == rotor.RotorId.review:
			scriptHandler.executeScript(globalCommands.commands.script_braille_previousLine, gesture)
		elif rid == rotor.RotorId.moveInTable:
			self.sendComb("control+alt+uparrow", gesture)
		else:
			self.sendComb("uparrow", gesture)

	@script(description=_("Rotor: activate the item (press Enter or the rotor’s default action)"))
	def script_selectElt(self, gesture):
		if rotor.current_rotor_id() == rotor.RotorId.object:
			self.sendComb("NVDA+enter", gesture)
		self.sendComb("enter", gesture)

	@script(description=_("Lock or unlock the braille keyboard so dots are not translated as you type"))
	def script_toggleLockBrailleKeyboard(self, gesture):
		self.brailleKeyboardLocked = not self.brailleKeyboardLocked
		if self.brailleKeyboardLocked:
			ui.message(_("Braille keyboard locked"))
		else:
			ui.message(_("Braille keyboard unlocked"))

	@script(description=_("Turn Braille Extender one-handed braille input on or off"))
	def script_toggleOneHandMode(self, gesture):
		config.conf["brailleExtender"]["oneHandedMode"]["enabled"] = not config.conf["brailleExtender"][
			"oneHandedMode"
		]["enabled"]
		if config.conf["brailleExtender"]["oneHandedMode"]["enabled"]:
			ui.message(_("One-handed mode enabled"))
		else:
			ui.message(_("One handed mode disabled"))

	@script(description=_("Hide or show dots 7 and 8 in contracted braille output"))
	def script_toggleDots78(self, gesture):
		self.hideDots78 = not self.hideDots78
		if self.hideDots78:
			speech.speakMessage(_("Dots 7 and 8 disabled"))
		else:
			speech.speakMessage(_("Dots 7 and 8 enabled"))
		utils.refresh_braille_for_current_focus()

	@script(
		description=_("Switch BRF output mode (braille file / literary layout handling)"),
		gesture="kb:nvda+alt+f",
	)
	def script_toggleBRFMode(self, gesture):
		self.BRFMode = not self.BRFMode
		utils.refresh_braille_for_current_focus()
		if self.BRFMode:
			speech.speakMessage(_("BRF mode enabled"))
		else:
			speech.speakMessage(_("BRF mode disabled"))

	@script(description=_("Lock or unlock modifier keys when entering text from the braille keyboard"))
	def script_toggleLockModifiers(self, gesture):
		self.modifiersLocked = not self.modifiersLocked
		if self.modifiersLocked:
			ui.message(_("Modifier keys locked"))
		else:
			ui.message(_("Modifier keys unlocked"))

	@script(
		description=_(
			"Turn reporting of font attributes in braille (bold, italic, underline, and so on) on or off"
		)
	)
	def script_toggleTextAttributes(self, gesture):
		key = "fontAttributes"
		documentformatting.toggle_report(key)
		documentformatting.report_formatting(key)
		utils.refresh_braille_for_current_focus()

	@script(description=_("Turn alignment indicators in braille (left, center, right, justified) on or off"))
	def script_toggleReportAlignments(self, gesture):
		key = "alignment"
		documentformatting.toggle_report(key)
		documentformatting.report_formatting(key)
		utils.refresh_braille_for_current_focus()

	@script(description=_("Show only plain text in braille (strip most structure and attribute marks)"))
	def script_toggle_plain_text(self, gesture):
		cur = config.conf["brailleExtender"]["documentFormatting"]["plainText"]
		config.conf["brailleExtender"]["documentFormatting"]["plainText"] = not cur
		cur = config.conf["brailleExtender"]["documentFormatting"]["plainText"]
		if cur:
			ui.message(_("Plain text mode enabled"))
		else:
			ui.message(_("Plain text mode disabled"))
		utils.refresh_braille_for_current_focus()

	@script(
		description=_(
			"Cycle how NVDA speaks the current line when you scroll braille (off, focus, review, or both)"
		)
	)
	def script_toggleSpeechScrollFocusMode(self, gesture):
		choices = addoncfg.focusOrReviewChoices
		curChoice = config.conf["brailleExtender"]["speakScroll"]
		curChoiceID = list(choices.keys()).index(curChoice)
		newChoiceID = (curChoiceID + 1) % len(choices)
		newChoice = list(choices.keys())[newChoiceID]
		config.conf["brailleExtender"]["speakScroll"] = newChoice
		ui.message(list(choices.values())[newChoiceID].capitalize())

	@script(description=_("Turn NVDA speech on or off (same as the built-in speech toggle)"))
	def script_toggleSpeech(self, gesture):
		if utils.is_speechMode_talk():
			utils.set_speech_off()
			ui.message(_("Speech off"))
		else:
			utils.set_speech_talk()
			ui.message(_("Speech on"))

	@script(
		description=_(
			"Read extra details for the review cursor (name, description, value; for example a link URL)"
		)
		+ HLP_browseModeInfo,
	)
	def script_reportExtraInfos(self, gesture):
		obj = api.getNavigatorObject()
		msg = []
		if obj.name:
			msg.append(obj.name)
		if obj.description:
			msg.append(obj.description)
		if obj.value:
			msg.append(obj.value)
		if len(msg) == 0:
			return ui.message(_("No extra info for this element"))
		if scriptHandler.getLastScriptRepeatCount() == 0:
			ui.message((punctuationSeparator + ": ").join(msg))
		else:
			ui.browseableMessage(("\n").join(msg))

	@script(description=_("Open a browseable list of dot patterns for the current Liblouis input table"))
	def script_getTableOverview(self, gesture):
		inTable = brailleInput.handler.table.displayName
		ouTable = addoncfg.tablesTR[addoncfg.tablesFN.index(utils.getTranslationTable())]
		t = (_(" Input table") + ": %s\n" + _("Output table") + ": %s\n\n") % (
			inTable + " (%s)" % (brailleInput.handler.table.fileName),
			ouTable + " (%s)" % (utils.getTranslationTable()),
		)
		t += utils.getTableOverview()
		ui.browseableMessage(
			"<pre>%s</pre>" % t, _("Table overview (%s)") % brailleInput.handler.table.displayName, True
		)

	@script(
		description=_("Translate the selection to Unicode braille and show it in a browseable window"),
		gesture="kb:nvda+alt+u",
	)
	def script_translateInBRU(self, gesture):
		tm = time.time()
		t = utils.getTextInBraille("", utils.getCurrentBrailleTables())
		if not t.strip():
			return ui.message(_("No text selection"))
		ui.browseableMessage(
			"<pre>%s</pre>" % t, _("Unicode Braille conversion") + (" (%.2f s)" % (time.time() - tm)), True
		)

	@script(
		description=_(
			"Translate the selection to dot numbers (cell descriptions) and show them in a browseable window"
		),
		gesture="kb:nvda+alt+i",
	)
	def script_charsToCellDescriptions(self, gesture):
		tm = time.time()
		t = utils.getTextInBraille("", utils.getCurrentBrailleTables())
		t = huc.unicodeBrailleToDescription(t)
		if not t.strip():
			return ui.message(_("No text selection"))
		ui.browseableMessage(
			t, _("Braille Unicode to cell descriptions") + (" (%.2f s)" % (time.time() - tm))
		)

	@script(
		description=_("Convert selected dot-number text (for example 125-24-0) to Unicode braille cells"),
		gesture="kb:nvda+alt+o",
	)
	def script_cellDescriptionsToChars(self, gesture):
		tm = time.time()
		t = utils.getTextSelection()
		if not t.strip():
			return ui.message(_("No text selection"))
		t = huc.cellDescriptionsToUnicodeBraille(t)
		ui.browseableMessage(
			t, _("Cell descriptions to braille Unicode") + (" (%.2f s)" % (time.time() - tm))
		)

	@script(
		description=_(
			"Turn advanced braille input mode on or off (HUC or numeric character codes and abbreviation expansions)"
		),
		gesture="kb:nvda+windows+i",
	)
	def script_advancedInput(self, gesture):
		self.advancedInput = not self.advancedInput
		if self.advancedInput:
			tones.beep(700, 30)
		else:
			tones.beep(300, 30)

	@script(
		description=_("Turn punctuation or symbol names in braille for undefined characters on or off"),
		gesture="kb:nvda+windows+u",
	)
	def script_undefinedCharsDesc(self, gesture):
		config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"] = not config.conf["brailleExtender"][
			"undefinedCharsRepr"
		]["desc"]
		if config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"]:
			speech.speakMessage(_("Punctuation or symbol names for undefined characters in braille on"))
		else:
			speech.speakMessage(_("Punctuation or symbol names for undefined characters in braille off"))
		utils.refresh_braille_for_current_focus()

	@script(
		description=_(
			"Report how far the caret has moved through the text under the braille cursor (percentage and character count)"
		)
	)
	def script_position(self, gesture=None):
		curpos, total = utils.getTextPosition()
		if total:
			percentage = round((curpos / total * 100), 2)
			ui.message(f"{percentage}% ({curpos}/{total})")
		else:
			ui.message(_("No text"))

	@script(
		description=_(
			"Show the current time and date on the braille display, updating every second. "
			"Press again to return to normal braille."
		),
	)
	def script_hourDate(self, gesture=None):
		if patches.get_auto_scroll():
			return
		if self.hourDatePlayed:
			self.hourDateTimer.Stop()
			self.clearMessageFlash()
			if addoncfg.noMessageTimeout:
				config.conf["braille"]["noMessageTimeout"] = self.backupMessageTimeout
			_restoreMainBuffer()
		else:
			if addoncfg.noMessageTimeout:
				self.backupMessageTimeout = config.conf["braille"]["noMessageTimeout"]
				config.conf["braille"]["noMessageTimeout"] = True
			self.showHourDate()
			self.hourDateTimer = wx.PyTimer(self.showHourDate)
			time.sleep(1.02 - round(time.time() - int(time.time()), 3))
			self.showHourDate()
			self.hourDateTimer.Start(1000)
		self.hourDatePlayed = not self.hourDatePlayed
		return

	@staticmethod
	def showHourDate():
		currentHourDate = time.strftime("%X %x (%a, %W/53, %b)", time.localtime())
		return _brailleMessagePersistent(currentHourDate)

	@script(description=_("Turn Braille Extender automatic braille scrolling on or off"))
	def script_autoScroll(self, gesture):
		if patches.is_patch_applied("braille_handler"):
			braille.handler.toggle_auto_scroll()
		else:
			ui.message(_("Autoscroll feature unavailable (patch not applied)"))

	@script(description=_("Press the system volume up key and report the new level in braille or speech"))
	def script_volumePlus(self, gesture):
		keyboardHandler.KeyboardInputGesture.fromName("volumeup").send()
		utils.report_volume_level()

	@script(description=_("Press the system volume down key and report the new level in braille or speech"))
	def script_volumeMinus(self, gesture):
		keyboardHandler.KeyboardInputGesture.fromName("volumedown").send()
		utils.report_volume_level()

	@script(description=_("Press the system mute key and report the new mute or volume state"))
	def script_toggleVolume(self, gesture):
		keyboardHandler.KeyboardInputGesture.fromName("volumemute").send()
		utils.report_volume_level()

	@staticmethod
	def clearMessageFlash():
		if config.conf["braille"]["messageTimeout"] != 0:
			if braille.handler.buffer is braille.handler.messageBuffer:
				braille.handler._dismissMessage()

	@script(description=_("Open the Braille Extender user guide (readme.html)"))
	def script_getHelp(self, g):
		from . import addonhelp

		addonhelp.open_user_guide()

	@script(
		description=_("Show a browseable summary of braille profile gestures and add-on keyboard shortcuts")
	)
	def script_showGestureReference(self, g):
		from . import addonhelp

		addonhelp.show_gesture_reference(self)

	def noKeyboarLayout(self):
		return self.noKC

	def getKeyboardLayouts(self):
		if not self.noKC and "keyboardLayouts" in addoncfg.iniProfile:
			for layout in addoncfg.iniProfile["keyboardLayouts"]:
				t = []
				for lk in addoncfg.iniProfile["keyboardLayouts"][layout]:
					if lk in ["braille_dots", "braille_enter", "braille_translate"]:
						scriptName = "script_%s" % lk
						func = getattr(globalCommands.GlobalCommands, scriptName, None)
						if isinstance(addoncfg.iniProfile["keyboardLayouts"][layout][lk], list):
							t.append(
								utils.format_gesture_identifiers(
									addoncfg.iniProfile["keyboardLayouts"][layout][lk]
								)
								+ punctuationSeparator
								+ ": "
								+ func.__doc__
							)
						else:
							t.append(
								utils.format_gesture_identifiers(
									addoncfg.iniProfile["keyboardLayouts"][layout][lk]
								)
								+ punctuationSeparator
								+ ": "
								+ func.__doc__
							)
					else:
						if isinstance(addoncfg.iniProfile["keyboardLayouts"][layout][lk], list):
							t.append(
								utils.format_gesture_identifiers(
									addoncfg.iniProfile["keyboardLayouts"][layout][lk]
								)
								+ punctuationSeparator
								+ ": "
								+ utils.getKeysTranslation(lk)
							)
						else:
							t.append(
								utils.format_gesture_identifiers(
									addoncfg.iniProfile["keyboardLayouts"][layout][lk]
								)
								+ punctuationSeparator
								+ ": "
								+ utils.getKeysTranslation(lk)
							)
				yield ((punctuationSeparator + "; ").join(t))

	def getGestures(self):
		gesture_map_attr = "_%s__gestures" % self.__class__.__name__
		class_gestures = getattr(self.__class__, gesture_map_attr, None)
		if class_gestures is not None:
			return class_gestures.copy()
		return OrderedDict()

	@script(
		description=_(
			"Run a quick-launch item (application, file, or URL) configured in Braille Extender settings"
		)
	)
	def script_quickLaunch(self, gesture):
		g = gesture.normalizedIdentifiers[0]
		quickLaunches = config.conf["brailleExtender"]["quickLaunches"].copy()
		if g not in quickLaunches.keys():
			ui.message("Target for %s not defined." % gesture.id)
			return
		try:
			return subprocess.Popen(quickLaunches[g])
		except BaseException:
			try:
				os.startfile(quickLaunches[g])
			except BaseException:
				ui.message(_("No such file or directory"))
			return

	@script(description=_("Check whether a newer version of Braille Extender is available"))
	def script_checkUpdate(self, gesture):
		if not globalVars.appArgs.secure:
			updatecheck.checkUpdates()
		return

	@script(description=_("Increase the delay before the braille display auto-scrolls to the next chunk"))
	def script_increaseDelayAutoScroll(self, gesture):
		if not patches.is_patch_applied("braille_handler"):
			ui.message(_("Autoscroll feature unavailable (patch not applied)"))
			return
		braille.handler.increase_auto_scroll_delay()
		if not patches.get_auto_scroll():
			braille.handler.report_auto_scroll_delay()

	@script(description=_("Decrease the delay before the braille display auto-scrolls to the next chunk"))
	def script_decreaseDelayAutoScroll(self, gesture):
		if not patches.is_patch_applied("braille_handler"):
			ui.message(_("Autoscroll feature unavailable (patch not applied)"))
			return
		braille.handler.decrease_auto_scroll_delay()
		if not patches.get_auto_scroll():
			braille.handler.report_auto_scroll_delay()

	@script(
		description=_(
			"Switch to the next Liblouis input table from your Braille Extender list (including automatic selection)"
		),
		gesture="kb:shift+NVDA+i",
	)
	def script_switchInputBrailleTable(self, gesture):
		return self._cyclePreferredInputTable(1)

	def _cyclePreferredInputTable(self, delta: int):
		if addoncfg.noUnicodeTable:
			return ui.message(_("NVDA 2017.3 or later is required to use this feature"))
		addoncfg.loadPreferredTables()
		if len(addoncfg.inputTables) < 2:
			return ui.message(
				_("You must choose at least two tables for this feature. Please fill in the settings")
			)
		activeInput = utils.getActiveInputTableForSwitch()
		try:
			tid = addoncfg.inputTables.index(activeInput)
		except ValueError:
			tid = -1
		nID = (tid + delta) % len(addoncfg.inputTables)
		nextTable = addoncfg.inputTables[nID]
		utils.apply_braille_input_table(nextTable)
		self.reloadBrailleTables()
		ui.message(_("Input: %s") % utils.get_braille_table_display_name(nextTable, is_input=True))

	@script(
		description=_(
			"Switch to the next Liblouis output table from your Braille Extender list (including automatic selection)"
		),
		gesture="kb:shift+NVDA+u",
	)
	def script_switchOutputBrailleTable(self, gesture):
		return self._cyclePreferredOutputTable(1)

	def _cyclePreferredOutputTable(self, delta: int):
		if addoncfg.noUnicodeTable:
			return ui.message(_("NVDA 2017.3 or later is required to use this feature"))
		addoncfg.loadPreferredTables()
		if len(addoncfg.outputTables) < 2:
			return ui.message(
				_("You must choose at least two tables for this feature. Please fill in the settings")
			)
		activeOutput = utils.getActiveOutputTableForSwitch()
		try:
			tid = addoncfg.outputTables.index(activeOutput)
		except ValueError:
			tid = -1
		nID = (tid + delta) % len(addoncfg.outputTables)
		nextTable = addoncfg.outputTables[nID]
		utils.apply_braille_output_table(nextTable)
		self.reloadBrailleTables()
		ui.message(_("Output: %s") % utils.get_braille_table_display_name(nextTable, is_input=False))

	@script(
		description=_("Announce the active Liblouis input and output table names in speech and braille"),
		gesture="kb:shift+NVDA+p",
	)
	def script_currentBrailleTable(self, gesture):
		inTable = utils.get_braille_table_display_name(utils.getActiveInputTableForSwitch(), is_input=True)
		ouTable = utils.get_braille_table_display_name(utils.getActiveOutputTableForSwitch(), is_input=False)
		if ouTable == inTable:
			braille.handler.message(_("I⣿O:{I}").format(I=inTable, O=ouTable))
			speech.speakMessage(_("Input and output: {I}.").format(I=inTable, O=ouTable))
		else:
			braille.handler.message(_("I:{I} ⣿ O: {O}").format(I=inTable, O=ouTable))
			speech.speakMessage(_("Input: {I}; Output: {O}").format(I=inTable, O=ouTable))
		return

	@script(
		description=_(
			"Show character information for the review cursor: Unicode name, speech symbol, braille cells, and numeric bases"
		)
	)
	def script_brlDescChar(self, gesture):
		utils.currentCharDesc()

	@script(
		description=_("Show the speech symbol string for the current selection in braille")
		+ HLP_browseModeInfo,
	)
	def script_getSpeechOutput(self, gesture):
		out = utils.getSpeechSymbols()
		if scriptHandler.getLastScriptRepeatCount() == 0:
			braille.handler.message(out)
		else:
			ui.browseableMessage(out)

	@script(description=_("Repeat the last keyboard shortcut you issued from the braille display"))
	def script_repeatLastShortcut(self, gesture):
		if not self.lastShortcutPerformed:
			ui.message(_("No shortcut performed from a braille display"))
			return
		sht = self.lastShortcutPerformed
		inputCore.manager.emulateGesture(keyboardHandler.KeyboardInputGesture.fromName(sht))

	def onReload(self, evt=None, sil=False, sv=False):
		self.clearGestureBindings()
		class_gestures = getattr(self.__class__, "_%s__gestures" % self.__class__.__name__, None)
		if class_gestures is not None:
			self.bindGestures(class_gestures)
		self._pGestures = OrderedDict()
		addoncfg.quickLaunches = OrderedDict()
		config.conf.spec["brailleExtender"] = addoncfg.getConfspec()
		addoncfg.loadConf()
		rotor.reload_from_config()
		addoncfg.initGestures()
		addoncfg.loadGestures()
		self.gesturesInit()
		if config.conf["brailleExtender"]["reverseScrollBtns"]:
			self.reverseScrollBtns()
		if not sil:
			ui.message(_("Braille Extender reloaded"))
		return

	@staticmethod
	def onUpdate(evt):
		return updatecheck.checkUpdates()

	@staticmethod
	def onWebsite(evt):
		return os.startfile(addonURL)

	@staticmethod
	def on_pot_file(evt):
		return os.startfile(f"{addonURL}/pot")

	@script(
		description=_("Reload Braille Extender settings, gesture maps, and patches without restarting NVDA")
	)
	def script_reloadAddon(self, gesture):
		self.onReload()

	@script(
		description=_(
			"Reload the primary braille display chosen in Braille Extender or NVDA (when that slot follows NVDA's active display)"
		),
		gesture="kb:nvda+j",
	)
	def script_reload_brailledisplay1(self, gesture):
		self.reload_configured_braille_display(1)

	@script(
		description=_("Reload the second favorite braille display chosen in Braille Extender settings"),
		gesture="kb:nvda+shift+j",
	)
	def script_reload_brailledisplay2(self, gesture):
		self.reload_configured_braille_display(2)

	def reload_configured_braille_display(self, slot: int) -> None:
		"""Reload primary (1) or secondary (2) display from Braille Extender / NVDA settings."""
		display_setting_key = "brailleDisplay2" if slot == 2 else "brailleDisplay1"
		if config.conf["brailleExtender"][display_setting_key] == "last":
			if config.conf["braille"]["display"] == "noBraille":
				return ui.message(_("No braille display specified. No reload to do"))
			utils.reload_braille_display(config.conf["braille"]["display"])
			addoncfg.curBD = braille.handler.display.name
			utils.refresh_braille_for_current_focus()
		else:
			utils.reload_braille_display(config.conf["brailleExtender"][display_setting_key])
			addoncfg.curBD = config.conf["brailleExtender"][display_setting_key]
			utils.refresh_braille_for_current_focus()
		return self.onReload(None, True)

	def clearModifiers(self, forced=False):
		if self.modifiersLocked and not forced:
			return
		brailleInput.handler.currentModifiers.clear()

	def sendComb(self, sht, gesture=None):
		inputCore.manager.emulateGesture(keyboardHandler.KeyboardInputGesture.fromName(sht))

	def getActualModifiers(self, short=True):
		modifiers = brailleInput.handler.currentModifiers
		if len(modifiers) == 0:
			return self.script_cancelShortcut(None)
		s = ""
		t = {"windows": _("WIN"), "control": _("CTRL"), "shift": _("SHIFT"), "alt": _("ALT"), "nvda": "NVDA"}
		for k in modifiers:
			s += t[k] + "+" if short else k + "+"
		if not short:
			return s
		if config.conf["brailleExtender"]["modifierKeysFeedback"] in [
			addoncfg.CHOICE_braille,
			addoncfg.CHOICE_speechAndBraille,
		]:
			braille.handler.message("%s..." % s)
		if config.conf["brailleExtender"]["modifierKeysFeedback"] in [
			addoncfg.CHOICE_speech,
			addoncfg.CHOICE_speechAndBraille,
		]:
			speech.speakMessage(keyLabels.getKeyCombinationLabel("+".join([m for m in self.modifiers])))

	def toggleModifier(self, modifier, beep=True):
		if modifier.lower() not in ["alt", "control", "nvda", "shift", "windows"]:
			return
		modifiers = brailleInput.handler.currentModifiers
		if modifier not in modifiers:
			modifiers.add(modifier)
			if beep and config.conf["brailleExtender"]["beepsModifiers"]:
				tones.beep(275, 50)
		else:
			modifiers.discard(modifier)
			if beep and config.conf["brailleExtender"]["beepsModifiers"]:
				tones.beep(100, 100 if len(modifiers) > 0 else 200)
		if len(modifiers) == 0:
			self.clearModifiers(True)

	@script(description=_modifier_keys_script_description("control"), bypassInputHelp=True)
	def script_ctrl(self, gesture=None, sil=True):
		self.toggleModifier("control", sil)
		if sil:
			self.getActualModifiers()
		return

	@script(description=_modifier_keys_script_description("NVDA"), bypassInputHelp=True)
	def script_nvda(self, gesture=None):
		self.toggleModifier("nvda")
		self.getActualModifiers()
		return

	@script(description=_modifier_keys_script_description("ALT"), bypassInputHelp=True)
	def script_alt(self, gesture=None, sil=True):
		self.toggleModifier("alt", sil)
		if sil:
			self.getActualModifiers()
		return

	@script(description=_modifier_keys_script_description("windows"))
	def script_win(self, gesture=None, sil=True):
		self.toggleModifier("windows", sil)
		if sil:
			self.getActualModifiers()
		return

	@script(description=_modifier_keys_script_description("SHIFT"))
	def script_shift(self, gesture=None, sil=True):
		self.toggleModifier("shift", sil)
		if sil:
			self.getActualModifiers()
		return

	@script(description=_modifier_keys_script_description("control+windows"))
	def script_ctrlWin(self, gesture):
		self.script_ctrl(None, False)
		return self.script_win(None)

	@script(description=_modifier_keys_script_description("ALT+windows"))
	def script_altWin(self, gesture):
		self.script_alt(None, False)
		return self.script_win(None)

	@script(description=_modifier_keys_script_description("Windows+Shift"))
	def script_winShift(self, gesture):
		self.script_shift(None, False)
		return self.script_win(None)

	@script(description=_modifier_keys_script_description("control+SHIFT"))
	def script_ctrlShift(self, gesture):
		self.script_ctrl(None, False)
		return self.script_shift(None)

	@script(description=_modifier_keys_script_description("control+Windows+SHIFT"))
	def script_ctrlWinShift(self, gesture):
		self.script_ctrl(None, False)
		self.script_shift(None, False)
		return self.script_win(None)

	@script(description=_modifier_keys_script_description("ALT+SHIFT"))
	def script_altShift(self, gesture):
		self.script_alt(None, False)
		return self.script_shift()

	@script(description=_modifier_keys_script_description("ALT+Windows+Shift"))
	def script_altWinShift(self, gesture):
		self.script_alt(None, False)
		self.script_shift(None, False)
		return self.script_win()

	@script(description=_modifier_keys_script_description("control+ALT"))
	def script_ctrlAlt(self, gesture):
		self.script_ctrl(None, False)
		return self.script_alt()

	@script(description=_modifier_keys_script_description("control+ALT+Windows"))
	def script_ctrlAltWin(self, gesture):
		self.script_ctrl(None, False)
		self.script_alt(None, False)
		return self.script_win()

	@script(description=_modifier_keys_script_description("control+ALT+SHIFT"))
	def script_ctrlAltShift(self, gesture):
		self.script_ctrl(None, False)
		self.script_alt(None, False)
		return self.script_shift()

	@script(description=_modifier_keys_script_description("control+ALT+Windows+SHIFT"))
	def script_ctrlAltWinShift(self, gesture):
		self.script_ctrl(None, False)
		self.script_alt(None, False)
		self.script_shift(None, False)
		return self.script_win()

	@script(
		description=_("Cancel staged modifier keys from the braille keyboard before emulating a PC shortcut"),
		bypassInputHelp=True,
	)
	def script_cancelShortcut(self, g):
		self.clearModifiers()
		self.clearMessageFlash()
		if not config.conf["brailleExtender"]["beepsModifiers"]:
			ui.message(_("Keyboard shortcut cancelled"))
		return

	@script(description=_("Scroll the braille display backward by one full width"), bypassInputHelp=True)
	def script_braille_scrollBack(self, gesture):
		braille.handler.scrollBack()

	@script(description=_("Scroll the braille display forward by one full width"), bypassInputHelp=True)
	def script_braille_scrollForward(self, gesture):
		braille.handler.scrollForward()

	def reverseScrollBtns(self, gesture=None, cancel=False):
		"""Swap which physical braille keys run scroll back vs forward (except excluded FS wiz-wheel lines)."""
		key_braille = globalCommands.SCRCAT_BRAILLE
		braille_map = inputCore.manager.getAllGestureMappings().get(key_braille)
		if not braille_map:
			return
		excluded = _REVERSE_SCROLL_EXCLUDED_BRAILLE_IDS
		ids_forward: set[str] = set()
		ids_back: set[str] = set()
		for key in braille_map:
			mapping = braille_map[key]
			script_name = getattr(mapping, "scriptName", None)
			if script_name == "braille_scrollForward":
				bucket = ids_forward
			elif script_name == "braille_scrollBack":
				bucket = ids_back
			else:
				continue
			for gid in mapping.gestures:
				if gid.lower() not in excluded:
					bucket.add(gid)
		if cancel:
			bind_forward, bind_back = ids_forward, ids_back
		else:
			bind_forward, bind_back = ids_back, ids_forward
		gesture_map = getattr(self.__class__, "_%s__gestures" % self.__class__.__name__)
		for gid in bind_forward:
			gesture_map[gid] = "braille_scrollForward"
		for gid in bind_back:
			gesture_map[gid] = "braille_scrollBack"
		self.bindGestures(gesture_map)

	@script(
		description=_("Developer: toggle verbose logging of text info at the review cursor"),
	)
	def script_logFieldsAtCursor(self, gesture):
		documentformatting.logTextInfo = not documentformatting.logTextInfo
		msg = ["stop", "start"]
		ui.message(f"debug textInfo {msg[documentformatting.logTextInfo]}")

	@script(
		description=_(
			"Save the current braille window as a snapshot; press twice quickly to clear the saved snapshot"
		)
	)
	def script_saveCurrentBrailleView(self, gesture):
		if scriptHandler.getLastScriptRepeatCount() == 0:
			config.conf["brailleExtender"]["viewSaved"] = "".join(
				chr(c | 0x2800) for c in braille.handler.mainBuffer.brailleCells
			)
			ui.message(_("Current braille view saved"))
		else:
			config.conf["brailleExtender"]["viewSaved"] = addoncfg.NOVIEWSAVED
			ui.message(_("Buffer cleaned"))

	@script(
		description=_("Show the saved braille snapshot briefly; press twice for a browseable copy")
		+ HLP_browseModeInfo,
	)
	def script_showBrailleViewSaved(self, gesture):
		if config.conf["brailleExtender"]["viewSaved"] != addoncfg.NOVIEWSAVED:
			if scriptHandler.getLastScriptRepeatCount() == 0:
				braille.handler.message("⣇ %s ⣸" % config.conf["brailleExtender"]["viewSaved"])
			else:
				ui.browseableMessage(config.conf["brailleExtender"]["viewSaved"], _("View saved"), True)
		else:
			ui.message(_("Buffer empty"))

	# section autoTest
	autoTestPlayed = False
	autoTestTimer = None
	autoTestInterval = 1000
	autoTest_tests = ["⠁⠂⠄⡀⠈⠐⠠⢀", "⠉⠒⠤⣀ ⣀⣤⣶⣿⠿⠛⠉ ", "⡇⢸", "⣿"]
	autoTest_gestures = {
		"kb:escape": "autoTest",
		"kb:q": "autoTest",
		"kb:space": "autoTestPause",
		"kb:p": "autoTestPause",
		"kb:r": "autoTestPause",
		"kb:s": "autoTestPause",
		"kb:j": "autoTestPrior",
		"kb:leftarrow": "autoTestPrior",
		"kb:rightarrow": "autoTestNext",
		"kb:k": "autoTestNext",
		"kb:uparrow": "autoTestIncrease",
		"kb:i": "autoTestIncrease",
		"kb:downarrow": "autoTestDecrease",
		"kb:o": "autoTestDecrease",
	}

	autoTest_type = 0
	autoTest_cellPtr = 0
	autoTest_charPtr = 0
	autoTest_pause = False
	autoTest_RTL = False

	@script(description=_("Pause or resume the braille display cell test pattern"))
	def script_autoTestPause(self, gesture):
		if self.autoTest_charPtr > 0:
			self.autoTest_charPtr -= 1
		else:
			self.autoTest_charPtr = len(self.autoTest_tests[self.autoTest_type]) - 1
		self.autoTest_pause = not self.autoTest_pause
		msg = _("Pause") if self.autoTest_pause else _("Resume")
		speech.speakMessage(msg)

	def showAutoTest(self):
		if self.autoTest_type == 1:
			braille.handler.message(
				"%s"
				% (
					self.autoTest_tests[self.autoTest_type][self.autoTest_charPtr]
					* braille.handler.displaySize
				)
			)
		else:
			braille.handler.message(
				"%s%s"
				% (
					" " * self.autoTest_cellPtr,
					self.autoTest_tests[self.autoTest_type][self.autoTest_charPtr],
				)
			)
		if self.autoTest_pause:
			return
		if self.autoTest_RTL:
			if self.autoTest_charPtr == 0:
				if self.autoTest_cellPtr == 0 or self.autoTest_type == 1:
					self.autoTest_RTL = False
				else:
					self.autoTest_cellPtr -= 1
					self.autoTest_charPtr = len(self.autoTest_tests[self.autoTest_type]) - 1
			else:
				self.autoTest_charPtr -= 1
		else:
			if self.autoTest_charPtr + 1 == len(self.autoTest_tests[self.autoTest_type]):
				if self.autoTest_cellPtr + 1 == braille.handler.displaySize or self.autoTest_type == 1:
					self.autoTest_RTL = True
				else:
					self.autoTest_cellPtr += 1
					self.autoTest_charPtr = 0
			else:
				self.autoTest_charPtr += 1

	@script(description=_("Slow down the braille cell test pattern (longer interval between updates)"))
	def script_autoTestDecrease(self, gesture):
		self.autoTestInterval += 125
		self.autoTestTimer.Stop()
		self.autoTestTimer.Start(self.autoTestInterval)
		speech.speakMessage("%d ms" % self.autoTestInterval)

	@script(description=_("Speed up the braille cell test pattern (shorter interval between updates)"))
	def script_autoTestIncrease(self, gesture):
		if self.autoTestInterval - 125 < 125:
			return
		self.autoTestInterval -= 125
		self.autoTestTimer.Stop()
		self.autoTestTimer.Start(self.autoTestInterval)
		speech.speakMessage("%d ms" % self.autoTestInterval)

	@script(description=_("Switch to the previous braille cell test pattern"))
	def script_autoTestPrior(self, gesture):
		if self.autoTest_type > 0:
			self.autoTest_type -= 1
		else:
			self.autoTest_type = len(self.autoTest_tests) - 1
		self.autoTest_charPtr = self.autoTest_cellPtr = 0
		self.showAutoTest()
		speech.speakMessage(_("Auto test type %d" % self.autoTest_type))

	@script(description=_("Switch to the next braille cell test pattern"))
	def script_autoTestNext(self, gesture):
		if self.autoTest_type + 1 < len(self.autoTest_tests):
			self.autoTest_type += 1
		else:
			self.autoTest_type = 0
		self.autoTest_charPtr = self.autoTest_cellPtr = 0
		self.showAutoTest()
		speech.speakMessage(_("Auto test type %d" % self.autoTest_type))

	@script(
		description=_(
			"Start or stop the built-in braille cell test pattern (for display alignment and timing)"
		)
	)
	def script_autoTest(self, gesture):
		if self.autoTestPlayed:
			self.autoTestTimer.Stop()
			for k in self.autoTest_gestures:
				try:
					self.removeGestureBinding(k)
				except BaseException:
					pass
			self.autoTest_charPtr = self.autoTest_cellPtr = 0
			self.clearMessageFlash()
			speech.speakMessage(_("Auto test stopped"))
			if addoncfg.noMessageTimeout:
				config.conf["braille"]["noMessageTimeout"] = self.backupMessageTimeout
		else:
			if addoncfg.noMessageTimeout:
				self.backupMessageTimeout = config.conf["braille"]["noMessageTimeout"]
				config.conf["braille"]["noMessageTimeout"] = True
			self.showAutoTest()
			self.autoTestTimer = wx.PyTimer(self.showAutoTest)
			self.bindGestures(self.autoTest_gestures)
			self.autoTestTimer.Start(self.autoTestInterval)
			speech.speakMessage(
				_(
					"Auto test started. Use the up and down arrow keys to change speed. Use the left and right arrow keys to change test type. Use space key to pause or resume the test. Use escape key to quit"
				)
			)
		self.autoTestPlayed = not self.autoTestPlayed

	# end of section autoTest

	@script(
		description=_(
			"Open the dialog to add or inspect a Liblouis dictionary entry for the character under the review cursor"
		),
		gesture="kb:nvda+alt+y",
	)
	def script_addDictionaryEntry(self, gesture):
		curChar = utils.getCurrentChar()
		_popupSettingsDialog(
			tabledictionaries.DictionaryEntryDlg,
			title=_("Add dictionary entry or see a dictionary"),
			textPattern=curChar,
			specifyDict=True,
		)

	@script(description=_("Skip or include blank lines when scrolling long text in braille"))
	def script_toggle_blank_line_scroll(self, gesture):
		config.conf["brailleExtender"]["skipBlankLinesScroll"] = not config.conf["brailleExtender"][
			"skipBlankLinesScroll"
		]
		if config.conf["brailleExtender"]["skipBlankLinesScroll"]:
			ui.message(_("Skip blank lines enabled"))
		else:
			ui.message(_("Skip blank lines disabled"))

	@script(
		description=_(
			"Cycle how routing keys behave in edit fields (normal, emulate arrows with beeps, or emulate arrows silently)"
		)
	)
	def script_toggleRoutingCursorsEditFields(self, gesture):
		routingCursorsEditFields = config.conf["brailleExtender"]["routingCursorsEditFields"]
		count = scriptHandler.getLastScriptRepeatCount()
		if count == 0:
			if routingCursorsEditFields == RC_NORMAL:
				config.conf["brailleExtender"]["routingCursorsEditFields"] = RC_EMULATE_ARROWS_BEEP
			else:
				config.conf["brailleExtender"]["routingCursorsEditFields"] = RC_NORMAL
		else:
			config.conf["brailleExtender"]["routingCursorsEditFields"] = RC_EMULATE_ARROWS_SILENT
		label = addoncfg.routingCursorsEditFields_labels[
			config.conf["brailleExtender"]["routingCursorsEditFields"]
		]
		ui.message(label[0].upper() + label[1:])

	@script(
		description=_(
			"Turn Braille Extender speech history mode on or off (captures speech for later review)"
		)
	)
	def script_toggleSpeechHistoryMode(self, gesture):
		newState = not config.conf["brailleExtender"]["speechHistoryMode"]["enabled"]
		config.conf["brailleExtender"]["speechHistoryMode"]["enabled"] = newState
		msg = _("Speech History Mode disabled")
		if newState:
			msg = _("Speech History Mode enabled")
		else:
			braille.handler.initialDisplay()
			braille.handler.buffer.update()
			braille.handler.update()
		speech.speakMessage(msg)

	def terminate(self):
		from .custom_braille_tables import ensure_nvda_braille_config_valid

		ensure_nvda_braille_config_valid()
		self.removeMenu()
		rolelabels.discardRoleLabels()
		if addoncfg.noUnicodeTable:
			brailleInput.handler.table = self.backupInputTable
		if self.hourDatePlayed:
			self.hourDateTimer.Stop()
			if addoncfg.noMessageTimeout:
				config.conf["braille"]["noMessageTimeout"] = self.backupMessageTimeout
			_restoreMainBuffer()
		if patches.is_patch_applied("braille_handler") and patches.get_auto_scroll():
			try:
				braille.handler.toggle_auto_scroll()
			except AttributeError:
				pass
		if self.autoTestPlayed:
			self.autoTestTimer.Stop()
		tabledictionaries.remove_temporary_dictionary()
		advancedinput.terminate()
		patches.unload_patches()
		super().terminate()

	def removeMenu(self):
		gui.mainFrame.sysTrayIcon.menu.DestroyItem(self.submenu_item)

	@staticmethod
	def errorMessage(msg):
		wx.CallAfter(gui.messageBox, msg, _("Braille Extender"), wx.OK | wx.ICON_ERROR)
