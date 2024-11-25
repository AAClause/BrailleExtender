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
import speech
import tones
import ui
import virtualBuffers
import wx
from logHandler import log

from . import addoncfg

config.conf.spec["brailleExtender"] = addoncfg.getConfspec()
from . import advancedinput
from . import tablegroups
from . import huc
from . import documentformatting
from . import objectpresentation
from . import patches
from . import rolelabels
from . import settings
from . import tabledictionaries
from . import undefinedchars
from . import updatecheck
from . import utils
from .tablehelper import get_table_by_file_name
from .common import (addonName, addonURL, addonVersion, punctuationSeparator,
	RC_NORMAL, RC_EMULATE_ARROWS_BEEP, RC_EMULATE_ARROWS_SILENT)

addonHandler.initTranslation()

instanceGP = None

rotorItems = [
	("default", _("Default")),
	("moveInText", _("Moving in the text")),
	("textSelection", _("Text selection")),
	("object", _("Objects")),
	("review", _("Review")),
	("Link", _("Links")),
	("UnvisitedLink", _("Unvisited links")),
	("VisitedLink", _("Visited links")),
	("Landmark", _("Landmarks")),
	("Heading", _("Headings")),
	("Heading1", _("Level 1 headings")),
	("Heading2", _("Level 2 headings")),
	("Heading3", _("Level 3 headings")),
	("Heading4", _("Level 4 headings")),
	("Heading5", _("Level 5 headings")),
	("Heading6", _("Level 6 headings")),
	("List", _("Lists")),
	("ListItem", _("List items")),
	("Graphic", _("Graphics")),
	("BlockQuote", _("Block quotes")),
	("Button", _("Buttons")),
	("FormField", _("Form fields")),
	("Edit", _("Edit fields")),
	("RadioButton", _("Radio buttons")),
	("ComboBox", _("Combo boxes")),
	("CheckBox", _("Check boxes")),
	("NotLinkBlock", _("Non-link blocks")),
	("Frame", _("Frames")),
	("Separator", _("Separators")),
	("EmbeddedObject", _("Embedded objects")),
	("Annotation", _("Annotations")),
	("Error", _("Spelling errors")),
	("Table", _("Tables")),
	("moveInTable", _("Move in table")),
]
rotorItem = 0
rotorRange = 0
lastRotorItemInVD = 0
lastRotorItemInVDSaved = True
HLP_browseModeInfo = ". %s" % _("If pressed twice, presents the information in browse mode")


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
	backupInputTable = brailleInput.handler.table
	backupMessageTimeout = None

	def __init__(self):
		startTime = time.time()
		super(globalPluginHandler.GlobalPlugin, self).__init__()
		patches.instanceGP = self
		self.reloadBrailleTables()
		settings.instanceGP = self
		addoncfg.loadConf()
		addoncfg.initGestures()
		addoncfg.loadGestures()
		self.gesturesInit()
		checkingForced = False
		if config.conf["brailleExtender"]["lastNVDAVersion"] != updatecheck.versionInfo.version:
			config.conf["brailleExtender"]["lastNVDAVersion"] = updatecheck.versionInfo.version
			checkingForced = True
		delayChecking = 86400 if config.conf["brailleExtender"]["updateChannel"] != addoncfg.CHANNEL_stable else 604800
		if not globalVars.appArgs.secure and config.conf["brailleExtender"]["autoCheckUpdate"] and (checkingForced or (time.time() - config.conf["brailleExtender"]["lastCheckUpdate"]) > delayChecking):
			updatecheck.checkUpdates(True)
			config.conf["brailleExtender"]["lastCheckUpdate"] = time.time()
		self.backup__addTextWithFields = braille.TextInfoRegion._addTextWithFields
		self.backup__update = braille.TextInfoRegion.update
		self.backup__getTypeformFromFormatField = braille.TextInfoRegion._getTypeformFromFormatField
		braille.TextInfoRegion._addTextWithFields = documentformatting.decorator(braille.TextInfoRegion._addTextWithFields, "addTextWithFields")
		braille.TextInfoRegion.update = documentformatting.decorator(braille.TextInfoRegion.update, "update")
		braille.TextInfoRegion._getTypeformFromFormatField = documentformatting.decorator(braille.TextInfoRegion._getTypeformFromFormatField, "_getTypeformFromFormatField")
		if config.conf["brailleExtender"]["reverseScrollBtns"]: self.reverseScrollBtns()
		self.createMenu()

		advancedinput.initialize()
		tablegroups.initializeGroups()
		if config.conf["brailleExtender"]["features"]["roleLabels"]:
			rolelabels.loadRoleLabels()
		objectpresentation.loadOrderProperties()
		documentformatting.load_tags()
		log.info(f"{addonName} {addonVersion} loaded ({round(time.time()-startTime, 2)}s)")

	def event_gainFocus(self, obj, nextHandler):
		global rotorItem, lastRotorItemInVD, lastRotorItemInVDSaved
		isVirtualBuff = obj is not None and isinstance(obj.treeInterceptor, virtualBuffers.VirtualBuffer)
		if lastRotorItemInVDSaved and isVirtualBuff:
			rotorItem = lastRotorItemInVD
			self.bindRotorGES()
			lastRotorItemInVDSaved = False
		elif not lastRotorItemInVDSaved and not isVirtualBuff:
			lastRotorItemInVD = rotorItem
			lastRotorItemInVDSaved = True
			rotorItem = 0
			self.bindRotorGES()

		if "tabSize_%s" % addoncfg.curBD not in config.conf["brailleExtender"]["tables"].copy().keys(): self.onReload(None, 1)
		if self.hourDatePlayed: self.script_hourDate(None)
		if self.autoTestPlayed: self.script_autoTest(None)
		if braille.handler is not None and addoncfg.curBD != braille.handler.display.name:
			addoncfg.curBD = braille.handler.display.name
			self.onReload(None, 1)

		nextHandler()

	def event_foreground(self, obj, nextHandler):
		if braille.handler._auto_scroll:
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
			if config.conf["brailleExtender"]["objectPresentation"]["progressBarUpdate"] == 1:#show value
				braille.handler.message(value)
			else:
				string = objectpresentation.generateProgressBarString(value, braille.handler.displaySize) or value
				braille.handler.message(string)
		except BaseException as e:
			log.error(e)
		nextHandler()

	def createMenu(self):
		self.submenu = wx.Menu()
		item = self.submenu.Append(wx.ID_ANY, _("Docu&mentation"), _("Opens the addon's documentation."))
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda event: self.script_getHelp(None),
			item
		)
		item = self.submenu.Append(wx.ID_ANY, _("&Settings..."), _("Opens the addons' settings."))
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda event: wx.CallAfter(gui.mainFrame._popupSettingsDialog, settings.AddonSettingsDialog),
			item
		)
		tabledictionariesMenu = wx.Menu()
		self.submenu.AppendSubMenu(tabledictionariesMenu, _("Table &dictionaries"), _("'Braille dictionaries' menu"))
		item = tabledictionariesMenu.Append(wx.ID_ANY, _("&Global dictionary"), _("A dialog where you can set global dictionary by adding dictionary entries to the list."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onDefaultDictionary, item)
		item = tabledictionariesMenu.Append(wx.ID_ANY, _("&Table dictionary"), _("A dialog where you can set table-specific dictionary by adding dictionary entries to the list."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onTableDictionary, item)
		item = tabledictionariesMenu.Append(wx.ID_ANY, _("Te&mporary dictionary"), _("A dialog where you can set temporary dictionary by adding dictionary entries to the list."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onTemporaryDictionary, item)

		item = self.submenu.Append(wx.ID_ANY, _("Advanced &input mode dictionary..."), _("Advanced input mode configuration"))
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda event: gui.mainFrame._popupSettingsDialog(advancedinput.AdvancedInputModeDlg),
			item
		)
		item = self.submenu.Append(wx.ID_ANY, "%s..." % _("&Quick launches"), _("Quick launches configuration"))
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda event: wx.CallAfter(gui.mainFrame._popupSettingsDialog, settings.QuickLaunchesDlg),
			item
		)
		item = self.submenu.Append(wx.ID_ANY, _("Braille input table &overview"), _("Overview of the current input braille table"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda event: self.script_getTableOverview(None), item)
		item = self.submenu.Append(wx.ID_ANY, _("&Reload add-on"), _("Reload this add-on."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onReload, item)
		item = self.submenu.Append(wx.ID_ANY, _("Check for &update..."), _("Checks if Braille Extender update is available"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onUpdate, item)
		item = self.submenu.Append(wx.ID_ANY, _("&Website"), _("Open addon's website."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.onWebsite, item)
		item = self.submenu.Append(wx.ID_ANY, _("Get the latest template &translation file (.pot)"), _("Opens the URL to download the latest Portable Object Template file of the add-on"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_pot_file, item)
		self.submenu_item = gui.mainFrame.sysTrayIcon.menu.Insert(2, wx.ID_ANY, "%s (%s)" % (_("&Braille Extender"), addonVersion), self.submenu)

	def reloadBrailleTables(self):
		patches.louis.liblouis.lou_free()
		#tabledictionaries.setDictTables()
		#tabledictionaries.notifyInvalidTables()
		if config.conf["brailleExtender"]["tables"]["tabSpace"]:
			liblouisDef = r"always \t " + ("0-" * addoncfg.getTabSize()).strip('-')
			patches.louis.compileString(patches.getCurrentBrailleTables(), bytes(liblouisDef, "ASCII"))
		undefinedchars.setUndefinedChar()

	@staticmethod
	def onDefaultDictionary(evt):
		gui.mainFrame._popupSettingsDialog(tabledictionaries.DictionaryDlg, _("Global dictionary"), "default")

	@staticmethod
	def onTableDictionary(evt):
		outTable = tablegroups.listTablesDisplayName()[tablegroups.listTablesFileName().index(config.conf["braille"]["translationTable"])]
		gui.mainFrame._popupSettingsDialog(tabledictionaries.DictionaryDlg, _("Table dictionary ({})").format(outTable), "table")

	@staticmethod
	def onTemporaryDictionary(evt):
		gui.mainFrame._popupSettingsDialog(tabledictionaries.DictionaryDlg, _("Temporary dictionary"), "tmp")

	def getGestureWithBrailleIdentifier(self, gesture = ''):
		return ("br(%s):" % addoncfg.curBD if ':' not in gesture else '') + gesture

	def gesturesInit(self):
		# rotor gestures
		if 'rotor' in addoncfg.iniProfile.keys():
			for k in addoncfg.iniProfile["rotor"]:
				if isinstance(addoncfg.iniProfile["rotor"][k], list):
					for l in addoncfg.iniProfile["rotor"][k]:
						self.rotorGES[self.getGestureWithBrailleIdentifier(l)] = k
				else:
					self.rotorGES[self.getGestureWithBrailleIdentifier(addoncfg.iniProfile["rotor"][k])] = k
			log.debug(self.rotorGES)
		else:
			log.debug("No rotor gestures for this profile")

		# keyboard layout gestures
		gK = OrderedDict()
		try:
			cK = addoncfg.iniProfile["keyboardLayouts"][config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD]] if config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD] and config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD] in addoncfg.iniProfile["keyboardLayouts"] is not None else addoncfg.iniProfile["keyboardLayouts"].keys()[0]
			for k in cK:
				if k in ["enter", "backspace"]:
					if isinstance(cK[k], list):
						for l in cK[k]:
							gK[inputCore.normalizeGestureIdentifier(self.getGestureWithBrailleIdentifier(l))] = 'kb:%s' % k
					else:
						gK['kb:%s' % k] = inputCore.normalizeGestureIdentifier(self.getGestureWithBrailleIdentifier(cK[k]))
				elif k in ["braille_dots", "braille_enter", "braille_translate"]:
					if isinstance(cK[k], list):
						for i in range(len(cK[k])):
							if ':' not in cK[k][i]:
								cK[k][i] = inputCore.normalizeGestureIdentifier(self.getGestureWithBrailleIdentifier(cK[k][i]))
					else:
						if ':' not in cK[k]:
							cK[k] = self.getGestureWithBrailleIdentifier(cK[k])
					gK[k] = cK[k]
			inputCore.manager.localeGestureMap.update({'globalCommands.GlobalCommands': gK})
			self.noKC = False
			log.debug("Keyboard conf found, loading layout `%s`" % config.conf["brailleExtender"]["keyboardLayout_%s" % addoncfg.curBD])
		except BaseException:
			log.debug("No keyboard conf found")
			self.noKC = True
		if addoncfg.gesturesFileExists:
			self._pGestures = OrderedDict()
			for k, v in (addoncfg.iniProfile["modifierKeys"].items() + [k for k in addoncfg.iniProfile["miscs"].items() if k[0] != 'defaultQuickLaunches']):
				if isinstance(v, list):
					for i, gesture in enumerate(v):
						self._pGestures[inputCore.normalizeGestureIdentifier(self.getGestureWithBrailleIdentifier(gesture))] = k
				else:
					self._pGestures[inputCore.normalizeGestureIdentifier(self.getGestureWithBrailleIdentifier(v))] = k
		self.bindGestures(self._pGestures)
		self.loadQuickLaunchesGes()

	def loadQuickLaunchesGes(self):
		self.bindGestures({k: "quickLaunch" for k in config.conf["brailleExtender"]["quickLaunches"].copy().keys() if '(%s' % addoncfg.curBD in k})

	def bindRotorGES(self):
		for k in self.rotorGES:
			try: self.removeGestureBinding(k)
			except BaseException: pass
		if rotorItems[rotorItem][0] == "default": return
		if rotorItems[rotorItem][0] in ["object", "review", "textSelection", "moveInText", "moveInTable"]:
			self.bindGestures(self.rotorGES)
		else:
			for k in self.rotorGES:
				if self.rotorGES[k] not in ["selectElt", "nextSetRotor", "priorSetRotor"]:
					self.bindGestures({k: self.rotorGES[k]})

	def script_priorRotor(self, gesture):
		global rotorItem
		if rotorItem > 0:
			rotorItem -= 1
		else:
			rotorItem = len(rotorItems) - 1
		self.bindRotorGES()
		return ui.message(rotorItems[rotorItem][1])
	script_priorRotor.__doc__ = _("Switches to the previous rotor setting")

	def script_nextRotor(self, gesture):
		global rotorItem
		rotorItem = 0 if rotorItem >= len(rotorItems) - 1 else rotorItem + 1
		self.bindRotorGES()
		return ui.message(rotorItems[rotorItem][1])
	script_nextRotor.__doc__ = _("Switches to the next rotor setting")

	@staticmethod
	def getCurrentSelectionRange(pretty=True, back=False):
		if pretty:
			labels = [
				_("Character"),
				_("Word"),
				_("Line"),
				_("Paragraph"),
				_("Page"),
				_("Document")]
			return labels[rotorRange]
		keys = [
			('leftarrow', 'rightarrow'),
			('control+leftarrow', 'control+rightarrow'),
			('uparrow', 'downarrow'),
			('control+uparrow', 'control+downarrow'),
			('pageup', 'pagedown'),
			('control+home', 'control+end')]
		if rotorItems[rotorItem][0] == "textSelection":
			return "shift+%s" % (keys[rotorRange][0] if back else keys[rotorRange][1])
		return keys[rotorRange][0] if back else keys[rotorRange][1]

	def switchSelectionRange(self, previous=False):
		global rotorRange
		if previous: rotorRange = rotorRange - 1 if rotorRange > 0 else 5
		else: rotorRange = rotorRange + 1 if rotorRange < 5 else 0
		ui.message(self.getCurrentSelectionRange())

	@staticmethod
	def moveTo(direction, gesture = None):
		global rotorItem
		obj = api.getFocusObject()
		if obj.treeInterceptor is not None:
			func = getattr(obj.treeInterceptor, "script_%s%s" % (direction, rotorItems[rotorItem][0]), None)
			if func: return func(gesture)
		ui.message(_("Not available here"))

	def script_nextEltRotor(self, gesture):
		if rotorItems[rotorItem][0] == "default": return self.sendComb('rightarrow', gesture)
		if rotorItems[rotorItem][0] in ["moveInText", "textSelection"]:
			return self.sendComb(self.getCurrentSelectionRange(False), gesture)
		if rotorItems[rotorItem][0] == "object":
			self.sendComb('nvda+shift+rightarrow', gesture)
		elif rotorItems[rotorItem][0] == "review":
			scriptHandler.executeScript(
				globalCommands.commands.script_braille_scrollForward, gesture)
		elif rotorItems[rotorItem][0] == "moveInTable":
			self.sendComb('control+alt+rightarrow', gesture)
		elif rotorItems[rotorItem][0] == "spellingErrors":
			obj = api.getFocusObject()
			if obj.treeInterceptor is not None:
				obj.treeInterceptor.script_nextError(gesture)
			else:
				ui.message(_("Not supported here or not in browse mode"))
		else: return self.moveTo("next", gesture)
	script_nextEltRotor.__doc__ = _("Moves to the next item based on rotor setting")

	def script_priorEltRotor(self, gesture):
		if rotorItems[rotorItem][0] == "default":
			return self.sendComb('leftarrow', gesture)
		if rotorItems[rotorItem][0] in ["moveInText", "textSelection"]:
			return self.sendComb(self.getCurrentSelectionRange(False, True), gesture)
		if rotorItems[rotorItem][0] == "object":
			return self.sendComb("nvda+shift+leftarrow", gesture)
		if rotorItems[rotorItem][0] == "review":
			return scriptHandler.executeScript(
				globalCommands.commands.script_braille_scrollBack, gesture)
		if rotorItems[rotorItem][0] == "moveInTable":
			return self.sendComb('control+alt+leftarrow', gesture)
		if rotorItems[rotorItem][0] == "spellingErrors":
			obj = api.getFocusObject()
			if obj.treeInterceptor is not None:
				obj.treeInterceptor.script_previousError(gesture)
			else:
				ui.message(_("Not supported here or not in browse mode"))
		else: return self.moveTo("previous", gesture)
	script_priorEltRotor.__doc__ = _("Moves to the previous item based on rotor setting")

	def script_nextSetRotor(self, gesture):
		if rotorItems[rotorItem][0] in ["moveInText", "textSelection"]:
			return self.switchSelectionRange()
		if rotorItems[rotorItem][0] == "object":
			self.sendComb('nvda+shift+downarrow', gesture)
		elif rotorItems[rotorItem][0] == "review":
			scriptHandler.executeScript(
				globalCommands.commands.script_braille_nextLine, gesture)
		elif rotorItems[rotorItem][0] == "moveInTable":
			self.sendComb('control+alt+downarrow', gesture)
		else:
			return self.sendComb('downarrow', gesture)
	script_nextSetRotor.__doc__ = _("Moves to the next item based on rotor setting")

	def script_priorSetRotor(self, gesture):
		if rotorItems[rotorItem][0] in ["moveInText", "textSelection"]:
			self.switchSelectionRange(True)
		elif rotorItems[rotorItem][0] == "object":
			self.sendComb('nvda+shift+uparrow', gesture)
		elif rotorItems[rotorItem][0] == "review":
			scriptHandler.executeScript(
				globalCommands.commands.script_braille_previousLine, gesture)
		elif rotorItems[rotorItem][0] == "moveInTable":
			self.sendComb('control+alt+uparrow', gesture)
		else:
			self.sendComb('uparrow', gesture)
	script_priorSetRotor.__doc__ = _("Moves to the previous item based on rotor setting")

	def script_selectElt(self, gesture):
		if rotorItems[rotorItem][0] == "object":
			self.sendComb('NVDA+enter', gesture)
		self.sendComb('enter', gesture)
	script_selectElt.__doc__ = _("Selects the item under the braille cursor e.g. doing default action if moving by objects")

	def script_toggleLockBrailleKeyboard(self, gesture):
		self.brailleKeyboardLocked = not self.brailleKeyboardLocked
		if self.brailleKeyboardLocked:
			ui.message(_("Braille keyboard locked"))
		else:
			ui.message(_("Braille keyboard unlocked"))
	script_toggleLockBrailleKeyboard.__doc__ = _("Toggle braille keyboard lock")

	def script_toggleOneHandMode(self, gesture):
		config.conf["brailleExtender"]["oneHandedMode"]["enabled"] = not config.conf["brailleExtender"]["oneHandedMode"]["enabled"]
		if config.conf["brailleExtender"]["oneHandedMode"]["enabled"]:
			ui.message(_("One-handed mode enabled"))
		else:
			ui.message(_("One handed mode disabled"))
	script_toggleOneHandMode.__doc__ = _("Toggle one-handed mode")

	def script_toggleDots78(self, gesture):
		self.hideDots78 = not self.hideDots78
		if self.hideDots78:
			speech.speakMessage(_("Dots 7 and 8 disabled"))
		else:
			speech.speakMessage(_("Dots 7 and 8 enabled"))
		utils.refreshBD()
	script_toggleDots78.__doc__ = _("Toggle showing or hiding dots 7 and 8")

	def script_toggleBRFMode(self, gesture):
		self.BRFMode = not self.BRFMode
		utils.refreshBD()
		if self.BRFMode:
			speech.speakMessage(_("BRF mode enabled"))
		else:
			speech.speakMessage(_("BRF mode disabled"))
	script_toggleBRFMode.__doc__ = _("Toggle BRF mode")

	def script_toggleLockModifiers(self, gesture):
		self.modifiersLocked = not self.modifiersLocked
		if self.modifiersLocked:
			ui.message(_("Modifier keys locked"))
		else:
			ui.message(_("Modifier keys unlocked"))
	script_toggleLockModifiers.__doc__ = _("Toggle locking modifier keys when using braille input")

	def script_toggleTextAttributes(self, gesture):
		key = "fontAttributes"
		documentformatting.toggle_report(key)
		documentformatting.report_formatting(key)
		utils.refreshBD()
	script_toggleTextAttributes.__doc__ = _("Toggle font attributes report")

	def script_toggleReportAlignments(self, gesture):
		key = "alignment"
		documentformatting.toggle_report(key)
		documentformatting.report_formatting(key)
		utils.refreshBD()
	script_toggleReportAlignments.__doc__ = _("Toggle alignments report")

	def script_toggle_plain_text(self, gesture):
		cur = config.conf["brailleExtender"]["documentFormatting"]["plainText"]
		config.conf["brailleExtender"]["documentFormatting"]["plainText"] = not cur
		cur = config.conf["brailleExtender"]["documentFormatting"]["plainText"]
		if cur:
			ui.message(_("Plain text mode enabled"))
		else:
			ui.message(_("Plain text mode disabled"))
		utils.refreshBD()
	script_toggle_plain_text.__doc__ = _("Toggle plain text mode")

	def script_toggleSpeechScrollFocusMode(self, gesture):
		choices = addoncfg.focusOrReviewChoices
		curChoice = config.conf["brailleExtender"]["speakScroll"]
		curChoiceID = list(choices.keys()).index(curChoice)
		newChoiceID = (curChoiceID+1) % len(choices)
		newChoice = list(choices.keys())[newChoiceID]
		config.conf["brailleExtender"]["speakScroll"] = newChoice
		ui.message(list(choices.values())[newChoiceID].capitalize())
	script_toggleSpeechScrollFocusMode.__doc__ = _("Toggle between say current line while scrolling options between none, focus mode, review mode, or both")

	def script_toggleSpeech(self, gesture):
		if utils.is_speechMode_talk():
			utils.set_speech_off()
			ui.message(_("Speech off"))
		else:
			utils.set_speech_talk()
			ui.message(_("Speech on"))
	script_toggleSpeech.__doc__ = _("Toggle speech on or off")

	def script_reportExtraInfos(self, gesture):
		obj = api.getNavigatorObject()
		msg = []
		if obj.name: msg.append(obj.name)
		if obj.description: msg.append(obj.description)
		if obj.value: msg.append(obj.value)
		if len(msg) == 0: return ui.message(_("No extra info for this element"))
		if scriptHandler.getLastScriptRepeatCount() == 0: ui.message((punctuationSeparator+": ").join(msg))
		else: ui.browseableMessage(('\n').join(msg))
	# Translators: Input help mode message for report extra infos command.
	script_reportExtraInfos.__doc__ = _("Reports some extra infos for the current element. For example, the URL on a link") + HLP_browseModeInfo

	def script_getTableOverview(self, gesture):
		inTable = brailleInput.handler.table.displayName
		ouTable = tablegroups.listTablesDisplayName()[tablegroups.listTablesFileName().index(config.conf["braille"]["translationTable"])]
		t = (_(" Input table")+": %s\n"+_("Output table")+": %s\n\n") % (inTable+' (%s)' % (brailleInput.handler.table.fileName), ouTable+' (%s)' % (config.conf["braille"]["translationTable"]))
		t += utils.getTableOverview()
		ui.browseableMessage("<pre>%s</pre>" % t, _("Table overview (%s)") % brailleInput.handler.table.displayName, True)
	script_getTableOverview.__doc__ = _("Shows an overview of current input braille table in a browseable message")

	def script_translateInBRU(self, gesture):
		tm = time.time()
		t = utils.getTextInBraille('', patches.getCurrentBrailleTables())
		if not t.strip(): return ui.message(_("No text selection"))
		ui.browseableMessage("<pre>%s</pre>" % t, _("Unicode Braille conversion") + (" (%.2f s)" % (time.time()-tm)), True)
	script_translateInBRU.__doc__ = _("Convert the text selection in unicode braille and display it in a browseable message")

	def script_charsToCellDescriptions(self, gesture):
		tm = time.time()
		t = utils.getTextInBraille('', patches.getCurrentBrailleTables())
		t = huc.unicodeBrailleToDescription(t)
		if not t.strip(): return ui.message(_("No text selection"))
		ui.browseableMessage(t, _("Braille Unicode to cell descriptions")+(" (%.2f s)" % (time.time()-tm)))
	script_charsToCellDescriptions.__doc__ = _("Convert text selection in braille cell descriptions and display it in a browseable message")

	def script_cellDescriptionsToChars(self, gesture):
		tm = time.time()
		t = utils.getTextSelection()
		if not t.strip(): return ui.message(_("No text selection"))
		t = huc.cellDescriptionsToUnicodeBraille(t)
		ui.browseableMessage(t, _("Cell descriptions to braille Unicode")+(" (%.2f s)" % (time.time()-tm)))
	script_cellDescriptionsToChars.__doc__ = _("Braille cell description to Unicode Braille. E.g.: in a edit field type '125-24-0-1-123-123'. Then select this text and execute this command")

	def script_advancedInput(self, gesture):
		self.advancedInput = not self.advancedInput
		if self.advancedInput:
			tones.beep(700, 30)
		else:
			tones.beep(300, 30)
	script_advancedInput.__doc__ = _("Toggle advanced input mode")

	def script_undefinedCharsDesc(self, gesture):
		config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"] = not config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"]
		if config.conf["brailleExtender"]["undefinedCharsRepr"]["desc"]:
			speech.speakMessage(_("Describe undefined characters enabled"))
		else:
			speech.speakMessage(_("Describe undefined characters disabled"))
		utils.refreshBD()
	script_undefinedCharsDesc.__doc__ = _("Toggle description of undefined characters")

	def script_position(self, gesture=None):
		curpos, total = utils.getTextPosition()
		if total:
			percentage = round((curpos / total * 100), 2)
			ui.message(f"{percentage}% ({curpos}/{total})")
		else:
			ui.message(_("No text"))
	script_position.__doc__ = _("Reports the cursor position of text under the braille cursor")

	def script_hourDate(self, gesture=None):
		if braille.handler._auto_scroll:
			return
		if self.hourDatePlayed:
			self.hourDateTimer.Stop()
			self.clearMessageFlash()
			if addoncfg.noMessageTimeout:
				config.conf["braille"]["noMessageTimeout"] = self.backupMessageTimeout
		else:
			if config.conf["brailleExtender"]["hourDynamic"]:
				if addoncfg.noMessageTimeout:
					self.backupMessageTimeout = config.conf["braille"]["noMessageTimeout"]
					config.conf["braille"]["noMessageTimeout"] = True
			self.showHourDate()
			if config.conf["brailleExtender"]["hourDynamic"]:
				self.hourDateTimer = wx.PyTimer(self.showHourDate)
				time.sleep(1.02 - round(time.time() - int(time.time()), 3))
				self.showHourDate()
				self.hourDateTimer.Start(1000)
			else:
				return
		self.hourDatePlayed = not self.hourDatePlayed
		return
	script_hourDate.__doc__ = _("Shows hour and date changes automatically on a braille display")

	@staticmethod
	def showHourDate():
		currentHourDate = time.strftime('%X %x (%a, %W/53, %b)', time.localtime())
		return braille.handler.message(currentHourDate)

	def script_autoScroll(self, gesture):
		braille.handler.toggle_auto_scroll()
	script_autoScroll.__doc__ = _("Toggle automatic braille scroll")

	def script_volumePlus(self, gesture):
		keyboardHandler.KeyboardInputGesture.fromName('volumeup').send()
		utils.report_volume_level()
	script_volumePlus.__doc__ = _("Increases the master volume")

	def script_volumeMinus(self, gesture):
		keyboardHandler.KeyboardInputGesture.fromName('volumedown').send()
		utils.report_volume_level()
	script_volumeMinus.__doc__ = _("Decreases the master volume")

	def script_toggleVolume(self, gesture):
		keyboardHandler.KeyboardInputGesture.fromName('volumemute').send()
		utils.report_volume_level()
	script_toggleVolume.__doc__ = _("Toggle sound mute")

	@staticmethod
	def clearMessageFlash():
		if config.conf["braille"]["messageTimeout"] != 0:
			if braille.handler.buffer is braille.handler.messageBuffer:
				braille.handler._dismissMessage()

	def script_getHelp(self, g):
		from . import addondoc
		addondoc.AddonDoc(self)
	script_getHelp.__doc__ = _("Shows the Braille Extender documentation")

	def noKeyboarLayout(self):
		return self.noKC

	def getKeyboardLayouts(self):
		if not self.noKC and "keyboardLayouts" in addoncfg.iniProfile:
			for layout in addoncfg.iniProfile["keyboardLayouts"]:
				t = []
				for lk in addoncfg.iniProfile["keyboardLayouts"][layout]:
					if lk in ["braille_dots", "braille_enter", "braille_translate"]:
						scriptName = 'script_%s' % lk
						func = getattr(globalCommands.GlobalCommands, scriptName, None)
						if isinstance(addoncfg.iniProfile["keyboardLayouts"][layout][lk], list):
							t.append(utils.beautifulSht(addoncfg.iniProfile["keyboardLayouts"][layout][lk]) + punctuationSeparator + ": " + func.__doc__)
						else:
							t.append(utils.beautifulSht(addoncfg.iniProfile["keyboardLayouts"][layout][lk]) + punctuationSeparator + ": " + func.__doc__)
					else:
						if isinstance(
								addoncfg.iniProfile["keyboardLayouts"][layout][lk], list):
							t.append(utils.beautifulSht(addoncfg.iniProfile["keyboardLayouts"][layout][lk]) + punctuationSeparator + ": " + utils.getKeysTranslation(lk))
						else:
							t.append(utils.beautifulSht(addoncfg.iniProfile["keyboardLayouts"][layout][lk]) + punctuationSeparator + ": " + utils.getKeysTranslation(lk))
				yield ((punctuationSeparator + '; ').join(t))

	def getGestures(s): return s.__gestures

	def script_quickLaunch(self, gesture):
		g = gesture.normalizedIdentifiers[0]
		quickLaunches = config.conf["brailleExtender"]["quickLaunches"].copy()
		if g not in quickLaunches.keys():
			ui.message('Target for %s not defined.' % gesture.id)
			return
		try: return subprocess.Popen(quickLaunches[g])
		except BaseException:
			try:
				os.startfile(quickLaunches[g])
			except BaseException:
				ui.message(_("No such file or directory"))
			return
	script_quickLaunch.__doc__ = _("Opens a custom program/file. Go to Braille Extender settings to define them")

	def script_checkUpdate(self, gesture):
		if not globalVars.appArgs.secure:
			updatecheck.checkUpdates()
		return
	script_checkUpdate.__doc__ = _("Checks for Braille Extender updates")

	def script_increaseDelayAutoScroll(self, gesture):
		braille.handler.increase_auto_scroll_delay()
		if not braille.handler._auto_scroll:
			braille.handler.report_auto_scroll_delay()
	script_increaseDelayAutoScroll.__doc__ = _("Increase braille autoscroll delay")

	def script_decreaseDelayAutoScroll(self, gesture):
		braille.handler.decrease_auto_scroll_delay()
		if not braille.handler._auto_scroll:
			braille.handler.report_auto_scroll_delay()
	script_decreaseDelayAutoScroll.__doc__ = _("Decrease braille autoscroll delay")

	def script_switchInputBrailleTable(self, gesture):
		table = config.conf["braille"]["inputTable"]
		usageIn = tablegroups.USAGE_INPUT
		choices = tablegroups.TableGroups(
			tablegroups.tablesToGroups(
				tablegroups.getPreferredTables()[0] + tablegroups._groups.get_groups()[0],
				usageIn
			)
		)
		if len(choices) < 2:
			return ui.message(_("Please fill at least two tables and/or groups of tables for this feature first"))
		newGroup = tablegroups.getGroup(
			position=tablegroups.POSITION_NEXT,
			usageIn=usageIn,
			choices=choices
		)
		if newGroup:
			res = tablegroups.setTableOrGroup(
				usageIn=usageIn,
				e=newGroup
			)
			if not res:
				log.error(f"Unable to set table or group (res={res}, usageIn={usageIn} newGroup={newGroup})")
				ui.message(_(f"Unable to set table or group"))
				return
		brailleInput.handler.table = newGroup.members[0]
		self.reloadBrailleTables()
		utils.refreshBD()
		#tabledictionaries.setDictTables()
		desc = (newGroup.name + (" (%s)" % _("group") if len(newGroup.members) > 1 else '') if newGroup else _("Default") + " (%s)" % brailleInput.handler.table.displayName)
		ui.message(_("Input: %s") % desc)
	script_switchInputBrailleTable.__doc__ = _("Switch between your favorite input braille tables including groups")

	def script_switchOutputBrailleTable(self, gesture):
		table = config.conf["braille"]["translationTable"]
		usageIn = tablegroups.USAGE_OUTPUT
		choices = tablegroups.TableGroups(
			tablegroups.tablesToGroups(
				tablegroups.getPreferredTables()[1] + tablegroups._groups.get_groups()[1],
				usageIn
			)
		)
		if len(choices) < 2:
			return ui.message(_("Please fill at least two tables and/or groups of tables for this feature first"))
		newGroup = tablegroups.getGroup(
			position=tablegroups.POSITION_NEXT,
			usageIn=usageIn,
			choices=choices
		)
		if newGroup:
			res = tablegroups.setTableOrGroup(
				usageIn=usageIn,
				e=newGroup
			)
			if not res:
				log.error(f"Unable to set table or group (res={res}, usageIn={usageIn} newGroup={newGroup})")
				ui.message(_(f"Unable to set table or group"))
				return
		self.reloadBrailleTables()
		utils.refreshBD()
		#tabledictionaries.setDictTables()
		desc = (newGroup.name + (" (%s)" % _("group") if len(newGroup.members) > 1 else '') if newGroup else (_("Default") + " (%s)" % tablegroups.fileName2displayName([config.conf["braille"]["translationTable"]])[0]))
		ui.message(_("Output: %s") % desc)

	script_switchOutputBrailleTable.__doc__ = _("Switch between your favorite output braille tables including groups")

	def script_currentBrailleTable(self, gesture):
		inTable = None
		ouTable = None
		if tablegroups.groupEnabled():
			i = tablegroups.getGroup(tablegroups.USAGE_INPUT)
			o = tablegroups.getGroup(tablegroups.USAGE_OUTPUT)
			if i: inTable = i.name
			if o: ouTable = o.name
		if not inTable: inTable = brailleInput.handler.table.displayName
		if not ouTable: ouTable = tablegroups.listTablesDisplayName()[tablegroups.listTablesFileName().index(config.conf["braille"]["translationTable"])]
		if ouTable == inTable:
			braille.handler.message(_("I⣿O:{I}").format(I=inTable, O=ouTable))
			speech.speakMessage(_("Input and output: {I}.").format(I=inTable, O=ouTable))
		else:
			braille.handler.message(_("I:{I} ⣿ O: {O}").format(I=inTable, O=ouTable))
			speech.speakMessage(_("Input: {I}; Output: {O}").format(I=inTable, O=ouTable))
	script_currentBrailleTable.__doc__ = _("Reports the current braille input and output tables")

	def script_brlDescChar(self, gesture):
		utils.currentCharDesc()
	script_brlDescChar.__doc__ = _("Reports the Unicode value of the character where the cursor is located and the decimal, binary and octal values")

	def script_getSpeechOutput(self, gesture):
		out = utils.getSpeechSymbols()
		if scriptHandler.getLastScriptRepeatCount() == 0: braille.handler.message(out)
		else: ui.browseableMessage(out)
	script_getSpeechOutput.__doc__ = _("Shows the output speech for selected text in braille, useful for emojis for example") + HLP_browseModeInfo

	def script_repeatLastShortcut(self, gesture):
		if not self.lastShortcutPerformed:
			ui.message(_("No shortcut performed from a braille display"))
			return
		sht =  self.lastShortcutPerformed
		inputCore.manager.emulateGesture(keyboardHandler.KeyboardInputGesture.fromName(sht))
	script_repeatLastShortcut.__doc__ = _("Repeats the last shortcut performed from a braille display")

	def onReload(self, evt=None, sil=False, sv=False):
		self.clearGestureBindings()
		self.bindGestures(self.__gestures)
		self._pGestures=OrderedDict()
		addoncfg.quickLaunches = OrderedDict()
		config.conf.spec["brailleExtender"] = addoncfg.getConfspec()
		addoncfg.loadConf()
		addoncfg.initGestures()
		addoncfg.loadGestures()
		self.gesturesInit()
		if config.conf["brailleExtender"]["reverseScrollBtns"]:
			self.reverseScrollBtns()
		if not sil: ui.message(_("Braille Extender reloaded"))
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


	def script_reloadAddon(self, gesture): self.onReload()
	script_reloadAddon.__doc__ = _("Reloads Braille Extender")

	def script_reload_brailledisplay1(self, gesture): self.reload_brailledisplay(1)
	script_reload_brailledisplay1.__doc__ = _("Reloads the primary braille display defined in settings")

	def script_reload_brailledisplay2(self, gesture): self.reload_brailledisplay(2)
	script_reload_brailledisplay2.__doc__ = _("Reloads the secondary braille display defined in settings")

	def reload_brailledisplay(self, n):
		k = "brailleDisplay%s" % (2 if n == 2 else 1)
		if config.conf["brailleExtender"][k] == "last":
			if config.conf["braille"]["display"] == "noBraille":
				return ui.message(_("No braille display specified. No reload to do"))
			utils.reload_brailledisplay(config.conf["braille"]["display"])
			addoncfg.curBD = braille.handler.display.name
			utils.refreshBD()
		else:
			utils.reload_brailledisplay(config.conf["brailleExtender"][k])
			addoncfg.curBD = config.conf["brailleExtender"][k]
			utils.refreshBD()
		return self.onReload(None, True)


	def clearModifiers(self, forced = False):
		if self.modifiersLocked and not forced: return
		brailleInput.handler.currentModifiers.clear()


	def sendComb(self, sht, gesture = None):
		inputCore.manager.emulateGesture(keyboardHandler.KeyboardInputGesture.fromName(sht))

	def getActualModifiers(self, short=True):
		modifiers = brailleInput.handler.currentModifiers
		if len(modifiers) == 0:
			return self.script_cancelShortcut(None)
		s = ""
		t = {
			"windows": _("WIN"),
			"control": _("CTRL"),
			"shift": _("SHIFT"),
			"alt": _("ALT"),
			"nvda": "NVDA"}
		for k in modifiers:
			s += t[k] + '+' if short else k + '+'
		if not short:
			return s
		if config.conf["brailleExtender"]["modifierKeysFeedback"] in [addoncfg.CHOICE_braille, addoncfg.CHOICE_speechAndBraille]:
			braille.handler.message('%s...' % s)
		if config.conf["brailleExtender"]["modifierKeysFeedback"] in [addoncfg.CHOICE_speech, addoncfg.CHOICE_speechAndBraille]:
			speech.speakMessage(keyLabels.getKeyCombinationLabel('+'.join([m for m in self.modifiers])))

	def toggleModifier(self, modifier, beep = True):
		if modifier.lower() not in ["alt","control","nvda","shift","windows"]:
			return
		modifiers = brailleInput.handler.currentModifiers
		if modifier not in modifiers:
			modifiers.add(modifier)
			if beep and config.conf["brailleExtender"]["beepsModifiers"]: tones.beep(275, 50)
		else:
			modifiers.discard(modifier)
			if beep and config.conf["brailleExtender"]["beepsModifiers"]: tones.beep(100, 100 if len(modifiers) > 0 else 200)
		if len(modifiers) == 0: self.clearModifiers(True)

	def script_ctrl(self, gesture=None, sil=True):
		self.toggleModifier("control", sil)
		if sil: self.getActualModifiers()
		return

	def script_nvda(self, gesture=None):
		self.toggleModifier("nvda")
		self.getActualModifiers()
		return

	def script_alt(self, gesture=None, sil=True):
		self.toggleModifier("alt", sil)
		if sil: self.getActualModifiers()
		return

	def script_win(self, gesture=None, sil=True):
		self.toggleModifier("windows", sil)
		if sil: self.getActualModifiers()
		return

	def script_shift(self, gesture=None, sil=True):
		self.toggleModifier("shift", sil)
		if sil: self.getActualModifiers()
		return

	def script_ctrlWin(self, gesture):
		self.script_ctrl(None, False)
		return self.script_win(None)

	def script_altWin(self, gesture):
		self.script_alt(None, False)
		return self.script_win(None)

	def script_winShift(self, gesture):
		self.script_shift(None, False)
		return self.script_win(None)

	def script_ctrlShift(self, gesture):
		self.script_ctrl(None, False)
		return self.script_shift(None)

	def script_ctrlWinShift(self, gesture):
		self.script_ctrl(None, False)
		self.script_shift(None, False)
		return self.script_win(None)

	def script_altShift(self, gesture):
		self.script_alt(None, False)
		return self.script_shift()

	def script_altWinShift(self, gesture):
		self.script_alt(None, False)
		self.script_shift(None, False)
		return self.script_win()

	def script_ctrlAlt(self, gesture):
		self.script_ctrl(None, False)
		return self.script_alt()

	def script_ctrlAltWin(self, gesture):
		self.script_ctrl(None, False)
		self.script_alt(None, False)
		return self.script_win()

	def script_ctrlAltShift(self, gesture):
		self.script_ctrl(None, False)
		self.script_alt(None, False)
		return self.script_shift()

	def script_ctrlAltWinShift(self, gesture):
		self.script_ctrl(None, False)
		self.script_alt(None, False)
		self.script_shift(None, False)
		return self.script_win()

	def script_cancelShortcut(self, g):
		self.clearModifiers()
		self.clearMessageFlash()
		if not config.conf["brailleExtender"]["beepsModifiers"]:
			ui.message(_("Keyboard shortcut cancelled"))
		return
	script_nvda.bypassInputHelp = True
	script_alt.bypassInputHelp = True
	script_ctrl.bypassInputHelp = True
	script_cancelShortcut.bypassInputHelp = True

	# /* docstrings for modifier keys */
	def docModKeys(k): return _("Emulate pressing down ") + '+'.join(
		[utils.getKeysTranslation(l) for l in k.split('+')]) + _(" on the system keyboard")
	script_ctrl.__doc__ = docModKeys("control")
	script_alt.__doc__ = docModKeys("ALT")
	script_win.__doc__ = docModKeys("windows")
	script_shift.__doc__ = docModKeys("SHIFT")
	script_nvda.__doc__ = docModKeys("NVDA")
	script_altShift.__doc__ = docModKeys("ALT+SHIFT")
	script_ctrlShift.__doc__ = docModKeys("control+SHIFT")
	script_ctrlAlt.__doc__ = docModKeys("control+ALT")
	script_ctrlAltShift.__doc__ = docModKeys("control+ALT+SHIFT")
	script_ctrlWin.__doc__ = docModKeys("control+windows")
	script_altWin.__doc__ = docModKeys("ALT+windows")
	script_winShift.__doc__ = docModKeys("Windows+Shift")
	script_altWinShift.__doc__ = docModKeys("ALT+Windows+Shift")
	script_ctrlWinShift.__doc__ = docModKeys("control+Windows+SHIFT")
	script_ctrlAltWin.__doc__ = docModKeys("control+ALT+Windows")
	script_ctrlAltWinShift.__doc__ = docModKeys("control+ALT+Windows+SHIFT")

	def script_braille_scrollBack(self, gesture):
		braille.handler.scrollBack()
	script_braille_scrollBack.bypassInputHelp = True

	def script_braille_scrollForward(self, gesture):
		braille.handler.scrollForward()
	script_braille_scrollForward.bypassInputHelp = True

	def reverseScrollBtns(self, gesture=None, cancel=False):
		keyBraille = globalCommands.SCRCAT_BRAILLE
		if cancel:
			scbtns = [inputCore.manager.getAllGestureMappings()[keyBraille][g].gestures for g in inputCore.manager.getAllGestureMappings()[keyBraille] if inputCore.manager.getAllGestureMappings()[keyBraille][g].scriptName == 'braille_scrollForward'] + \
				[inputCore.manager.getAllGestureMappings()[keyBraille][g].gestures for g in inputCore.manager.getAllGestureMappings()[keyBraille] if inputCore.manager.getAllGestureMappings()[keyBraille][g].scriptName == 'braille_scrollBack']
		else:
			scbtns = [inputCore.manager.getAllGestureMappings()[keyBraille][g].gestures for g in inputCore.manager.getAllGestureMappings()[keyBraille] if inputCore.manager.getAllGestureMappings()[keyBraille][g].scriptName == 'braille_scrollBack'] + \
				[inputCore.manager.getAllGestureMappings()[keyBraille][g].gestures for g in inputCore.manager.getAllGestureMappings()[keyBraille] if inputCore.manager.getAllGestureMappings()[keyBraille][g].scriptName == 'braille_scrollForward']
		for k in scbtns[0]:
			if k.lower() not in [
				'br(freedomscientific):leftwizwheelup',
					'br(freedomscientific):leftwizwheeldown']:
				self.__gestures[k] = "braille_scrollForward"
		for k in scbtns[1]:
			if k.lower() not in [
				'br(freedomscientific):leftwizwheelup',
					'br(freedomscientific):leftwizwheeldown']:
				self.__gestures[k] = "braille_scrollBack"
		self.bindGestures(self.__gestures)
		return

	def script_logFieldsAtCursor(self, gesture):
		documentformatting.logTextInfo = not documentformatting.logTextInfo
		msg = ["stop", "start"]
		ui.message(f"debug textInfo {msg[documentformatting.logTextInfo]}")

	def script_saveCurrentBrailleView(self, gesture):
		if scriptHandler.getLastScriptRepeatCount() == 0:
			config.conf["brailleExtender"]["viewSaved"] = ''.join(chr(c | 0x2800) for c in braille.handler.mainBuffer.brailleCells)
			ui.message(_("Current braille view saved"))
		else:
			config.conf["brailleExtender"]["viewSaved"] = addoncfg.NOVIEWSAVED
			ui.message(_("Buffer cleaned"))
	script_saveCurrentBrailleView.__doc__ = _("Saves the current braille view. Press twice quickly to clean the buffer")

	def script_showBrailleViewSaved(self, gesture):
		if config.conf["brailleExtender"]["viewSaved"] != addoncfg.NOVIEWSAVED:
			if scriptHandler.getLastScriptRepeatCount() == 0: braille.handler.message("⣇ %s ⣸" % config.conf["brailleExtender"]["viewSaved"])
			else: ui.browseableMessage(config.conf["brailleExtender"]["viewSaved"], _("View saved"), True)
		else: ui.message(_("Buffer empty"))
	script_showBrailleViewSaved.__doc__ = _("Shows the saved braille view through a flash message") + HLP_browseModeInfo

	# section autoTest
	autoTestPlayed = False
	autoTestTimer = None
	autoTestInterval = 1000
	autoTest_tests = ['⠁⠂⠄⡀⠈⠐⠠⢀', '⠉⠒⠤⣀ ⣀⣤⣶⣿⠿⠛⠉ ', '⡇⢸', '⣿']
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

	def script_autoTestPause(self, gesture):
		if self.autoTest_charPtr > 0: self.autoTest_charPtr -= 1
		else: self.autoTest_charPtr = len(self.autoTest_tests[self.autoTest_type])-1
		self.autoTest_pause = not self.autoTest_pause
		msg = _("Pause") if self.autoTest_pause else _("Resume",)
		speech.speakMessage(msg)

	def showAutoTest(self):
		if self.autoTest_type == 1:
			braille.handler.message("%s" % (self.autoTest_tests[self.autoTest_type][self.autoTest_charPtr]*braille.handler.displaySize))
		else:
			braille.handler.message("%s%s" % (' '*self.autoTest_cellPtr, self.autoTest_tests[self.autoTest_type][self.autoTest_charPtr]))
		if self.autoTest_pause: return
		if self.autoTest_RTL:
			if self.autoTest_charPtr == 0:
				if self.autoTest_cellPtr == 0 or self.autoTest_type == 1: self.autoTest_RTL = False
				else:
					self.autoTest_cellPtr -= 1
					self.autoTest_charPtr = len(self.autoTest_tests[self.autoTest_type])-1
			else: self.autoTest_charPtr -= 1
		else:
			if self.autoTest_charPtr+1 == len(self.autoTest_tests[self.autoTest_type]):
				if self.autoTest_cellPtr+1 == braille.handler.displaySize or self.autoTest_type == 1: self.autoTest_RTL = True
				else:
					self.autoTest_cellPtr += 1
					self.autoTest_charPtr = 0
			else: self.autoTest_charPtr += 1

	def script_autoTestDecrease(self, gesture):
		self.autoTestInterval += 125
		self.autoTestTimer.Stop()
		self.autoTestTimer.Start(self.autoTestInterval)
		speech.speakMessage("%d ms" % self.autoTestInterval)

	def script_autoTestIncrease(self, gesture):
		if self.autoTestInterval-125 < 125: return
		self.autoTestInterval -= 125
		self.autoTestTimer.Stop()
		self.autoTestTimer.Start(self.autoTestInterval)
		speech.speakMessage("%d ms" % self.autoTestInterval)

	def script_autoTestPrior(self, gesture):
		if self.autoTest_type > 0: self.autoTest_type -= 1
		else: self.autoTest_type = len(self.autoTest_tests)-1
		self.autoTest_charPtr = self.autoTest_cellPtr = 0
		self.showAutoTest()
		speech.speakMessage(_("Auto test type %d" % self.autoTest_type))

	def script_autoTestNext(self, gesture):
		if self.autoTest_type+1 < len(self.autoTest_tests): self.autoTest_type += 1
		else: self.autoTest_type = 0
		self.autoTest_charPtr = self.autoTest_cellPtr = 0
		self.showAutoTest()
		speech.speakMessage(_("Auto test type %d" % self.autoTest_type))

	def script_autoTest(self, gesture):
		if self.autoTestPlayed:
			self.autoTestTimer.Stop()
			for k in self.autoTest_gestures:
				try: self.removeGestureBinding(k)
				except BaseException: pass
			self.autoTest_charPtr = self.autoTest_cellPtr = 0
			self.clearMessageFlash()
			speech.speakMessage(_("Auto test stopped"))
			if addoncfg.noMessageTimeout: config.conf["braille"]["noMessageTimeout"] = self.backupMessageTimeout
		else:
			if addoncfg.noMessageTimeout:
				self.backupMessageTimeout = config.conf["braille"]["noMessageTimeout"]
				config.conf["braille"]["noMessageTimeout"] = True
			self.showAutoTest()
			self.autoTestTimer = wx.PyTimer(self.showAutoTest)
			self.bindGestures(self.autoTest_gestures)
			self.autoTestTimer.Start(self.autoTestInterval)
			speech.speakMessage(_("Auto test started. Use the up and down arrow keys to change speed. Use the left and right arrow keys to change test type. Use space key to pause or resume the test. Use escape key to quit"))
		self.autoTestPlayed = not self.autoTestPlayed
	script_autoTest.__doc__ = _("Auto test")
	# end of section autoTest

	def script_addDictionaryEntry(self, gesture):
		curChar = utils.getCurrentChar()
		gui.mainFrame._popupSettingsDialog(tabledictionaries.DictionaryEntryDlg, title=_("Add dictionary entry or see a dictionary"), textPattern=curChar, specifyDict=True)
	script_addDictionaryEntry.__doc__ = _("Adds an entry in braille dictionary")

	def script_toggle_blank_line_scroll(self, gesture):
		config.conf["brailleExtender"]["skipBlankLinesScroll"] = not config.conf["brailleExtender"]["skipBlankLinesScroll"]
		if config.conf["brailleExtender"]["skipBlankLinesScroll"]:
			ui.message(_("Skip blank lines enabled"))
		else:
			ui.message(_("Skip blank lines disabled"))
	script_toggle_blank_line_scroll.__doc__ = _("Toggle blank lines during text scrolling")

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
		label = addoncfg.routingCursorsEditFields_labels[config.conf["brailleExtender"]["routingCursorsEditFields"]]
		ui.message(label[0].upper() + label[1:])
	script_toggleRoutingCursorsEditFields.__doc__ = _("Toggle routing cursors behavior in edit fields")

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
	script_toggleSpeechHistoryMode.__doc__ = _("Toggle Speech History Mode")

	__gestures = OrderedDict()
	__gestures["kb:NVDA+control+shift+a"] = "logFieldsAtCursor"
	__gestures["kb:shift+NVDA+p"] = "currentBrailleTable"
	__gestures["kb:shift+NVDA+i"] = "switchInputBrailleTable"
	__gestures["kb:shift+NVDA+u"] = "switchOutputBrailleTable"
	__gestures["kb:nvda+j"] = "reload_brailledisplay1"
	__gestures["kb:nvda+shift+j"] = "reload_brailledisplay2"
	__gestures["kb:nvda+alt+f"] = "toggleBRFMode"
	__gestures["kb:nvda+windows+i"] = "advancedInput"
	__gestures["kb:nvda+windows+u"] = "undefinedCharsDesc"
	__gestures["kb:volumeMute"] = "toggleVolume"
	__gestures["kb:volumeUp"] = "volumePlus"
	__gestures["kb:volumeDown"] = "volumeMinus"
	__gestures["kb:nvda+alt+u"] = "translateInBRU"
	__gestures["kb:nvda+alt+i"] = "charsToCellDescriptions"
	__gestures["kb:nvda+alt+o"] = "cellDescriptionsToChars"
	__gestures["kb:nvda+alt+y"] = "addDictionaryEntry"

	def terminate(self):
		braille.TextInfoRegion._addTextWithFields = self.backup__addTextWithFields
		braille.TextInfoRegion.update = self.backup__update
		braille.TextInfoRegion._getTypeformFromFormatField = self.backup__getTypeformFromFormatField
		self.removeMenu()
		rolelabels.discardRoleLabels()
		if self.hourDatePlayed:
			self.hourDateTimer.Stop()
			if addoncfg.noMessageTimeout:
				config.conf["braille"]["noMessageTimeout"] = self.backupMessageTimeout
		if braille.handler._auto_scroll:
			braille.handler.toggle_auto_scroll()
		if self.autoTestPlayed: self.autoTestTimer.Stop()
		#tabledictionaries.removeTmpDict()
		advancedinput.terminate()
		super().terminate()

	def removeMenu(self):
		gui.mainFrame.sysTrayIcon.menu.DestroyItem(self.submenu_item)

	@staticmethod
	def errorMessage(msg):
		wx.CallAfter(gui.messageBox, msg, _("Braille Extender"), wx.OK|wx.ICON_ERROR)
