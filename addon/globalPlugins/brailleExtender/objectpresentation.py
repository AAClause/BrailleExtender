# coding: utf-8
# objectpresentation.py
# Part of BrailleExtender addon for NVDA
# Copyright 2020-2022 Emil Hesmyr, André-Abush Clause, released under GPL.

import re
import gui
import wx

import addonHandler
import braille
import config
import controlTypes
import queueHandler
import ui
from logHandler import log
from NVDAObjects.behaviors import ProgressBar

from . import addoncfg
from .common import N_, CHOICE_liblouis, CHOICE_none, ADDON_ORDER_PROPERTIES, IS_CURRENT_NO
from .documentformatting import CHOICES_LABELS, get_report, LABELS_STATES
from .utils import get_output_reason, get_control_type

addonHandler.initTranslation()

MOVE_UP = 0
MOVE_DOWN = 1

NVDA_ORDER = 0
ADDON_ORDER = 1
PROPERTIES_ORDER = {
	"name": _("name"),
	"value": _("value"),
	"states": _("state"),
	"roleText": _("role text"),
	"description": _("description"),
	"keyboardShortcut": _("keyboard shortcut"),
	"positionInfo": _("position info"),
	"positionInfoLevel": _("position info level"),
	"current": _("current labels"),
	"placeholder": _("place-holder"),
	"cellCoordsText": _("cell coordinates text"),
}


def getDefaultOrderProperties(addon=False):
	if addon:
		return ADDON_ORDER_PROPERTIES.split(",")
	else:
		return list(PROPERTIES_ORDER.keys())


def loadOrderProperties():
	global orderProperties
	orderProperties = getOrderPropertiesFromConfig()


def getOrderPropertiesFromConfig():
	defaultOrderProperties = getDefaultOrderProperties()
	orderProperties = config.conf["brailleExtender"]["objectPresentation"]["orderProperties"].split(",")
	if len(defaultOrderProperties) > len(orderProperties):
		log.error("Missing one or more elements")
		setOrderProperties(defaultOrderProperties, True)
		return defaultOrderProperties
	for e in orderProperties:
		if e not in defaultOrderProperties:
			log.warning(f"Unknown '{e}'")
			setOrderProperties(defaultOrderProperties, True)
			return defaultOrderProperties
	return orderProperties


orderProperties = getDefaultOrderProperties()


def getOrderProperties():
	return orderProperties


def setOrderProperties(newOrder, save=False):
	global orderProperties
	orderProperties = newOrder
	if save:
		config.conf["brailleExtender"]["objectPresentation"]["orderProperties"] = ",".join(newOrder)


def selectedElementEnabled():
	return config.conf["brailleExtender"]["objectPresentation"]["selectedElement"] != CHOICE_none


def update_NVDAObjectRegion(self):
	obj = self.obj
	presConfig = config.conf["presentation"]
	role = obj.role
	placeholderValue = obj.placeholder
	if placeholderValue and not obj._isTextEmpty:
		placeholderValue = None
	cellInfo = None
	if hasattr(obj, "excelCellInfo"):
		cellInfo = obj.excelCellInfo
	text = getPropertiesBraille(
		name=obj.name,
		role=role,
		roleText=obj.roleTextBraille,
		current=obj.isCurrent,
		placeholder=placeholderValue,
		value=obj.value if not braille.NVDAObjectHasUsefulText(obj) else None,
		states=obj.states,
		description=obj.description if presConfig["reportObjectDescriptions"] else None,
		keyboardShortcut=obj.keyboardShortcut if presConfig["reportKeyboardShortcuts"] else None,
		positionInfo=obj.positionInfo if presConfig["reportObjectPositionInformation"] else None,
		cellCoordsText=obj.cellCoordsText if get_report("tableCellCoords") else None,
		cellInfo=cellInfo,
	)
	try:
		if getattr(obj, "columnHeaderText"):
			text += "⣀" + obj.columnHeaderText
	except NotImplementedError:
		pass
	try:
		if getattr(obj, "rowHeaderText"):
			text += "⡀" + obj.rowHeaderText
	except NotImplementedError:
		pass
	if not getattr(obj, "cellCoordsText"):
		coordinates = ""
		try:
			if getattr(obj, "rowNumber"):
				coordinates += N_("r{rowNumber}").format(rowNumber=obj.rowNumber)
		except NotImplementedError:
			pass
		try:
			if getattr(obj, "columnNumber"):
				coordinates += N_("c{columnNumber}").format(columnNumber=obj.columnNumber)
		except NotImplementedError:
			pass
		if coordinates:
			text += " " + coordinates
	if role == get_control_type("ROLE_MATH"):
		import mathPres

		mathPres.ensureInit()
		if mathPres.brailleProvider:
			try:
				text += braille.TEXT_SEPARATOR + mathPres.brailleProvider.getBrailleForMathMl(obj.mathMl)
			except (NotImplementedError, LookupError):
				pass
	self.rawText = text + self.appendText
	super(braille.NVDAObjectRegion, self).update()


def is_current_display_string(current):
	if hasattr(current, "displayString"):
		return current.displayString
	if hasattr(controlTypes, "isCurrentLabels"):
		try:
			return controlTypes.isCurrentLabels[current]
		except KeyError:
			pass
	log.debugWarning("Aria-current value not handled: %s" % current)
	return ""


def get_roleLabel(role):
	if hasattr(controlTypes, "Role"):
		if isinstance(role, controlTypes.Role):
			return role.displayString
		if isinstance(role, str):
			return getattr(controlTypes.Role, role).displayString
		raise TypeError()
	return controlTypes.roleLabels[role]


def getPropertiesBraille(**propertyValues) -> str:
	properties = {}
	positiveStateLabels = braille.positiveStateLabels
	negativeStateLabels = braille.negativeStateLabels
	TEXT_SEPARATOR = braille.TEXT_SEPARATOR
	roleLabels = braille.roleLabels
	name = propertyValues.get("name")
	if name:
		properties["name"] = name
	description = propertyValues.get("description")
	states = propertyValues.get("states")
	role = propertyValues.get("role")
	roleText = propertyValues.get("roleText")
	roleTextPost = propertyValues.get("roleTextPost")
	positionInfo = propertyValues.get("positionInfo")
	level = positionInfo.get("level") if positionInfo else None
	cellCoordsText = propertyValues.get("cellCoordsText")
	cellInfo = propertyValues.get("cellInfo")
	rowNumber = propertyValues.get("rowNumber")
	columnNumber = propertyValues.get("columnNumber")
	# When fetching row and column span
	# default the values to 1 to make further checks a lot simpler.
	# After all, a table cell that has no rowspan implemented is assumed to span one row.
	rowSpan = propertyValues.get("rowSpan") or 1
	columnSpan = propertyValues.get("columnSpan") or 1
	includeTableCellCoords = get_report("tableCellCoords") and propertyValues.get(
		"includeTableCellCoords", True
	)
	if role is not None and not roleText:
		if role == get_control_type("ROLE_HEADING") and level:
			roleText = N_("h%s") % level
			level = None
		elif role == get_control_type("ROLE_LINK") and states and get_control_type("STATE_VISITED") in states:
			states = states.copy()
			states.discard(get_control_type("STATE_VISITED"))
			roleText = N_("vlnk")
		elif (
			not description
			and config.conf["brailleExtender"]["documentFormatting"]["cellFormula"]
			and states
			and get_control_type("STATE_HASFORMULA") in states
			and cellInfo
			and hasattr(cellInfo, "formula")
			and cellInfo.formula
		):
			states = states.copy()
			states.discard(get_control_type("STATE_HASFORMULA"))
			description = cellInfo.formula
		elif (
			name or cellCoordsText or rowNumber or columnNumber
		) and role in controlTypes.silentRolesOnFocus:
			roleText = None
		else:
			roleText = roleLabels.get(role, get_roleLabel(role))
	elif role is None:
		role = propertyValues.get("_role")
	if roleText and roleTextPost:
		roleText += roleTextPost
	if roleText:
		properties["roleText"] = roleText
	value = propertyValues.get("value") if role not in controlTypes.silentValuesForRoles else None
	if value:
		properties["value"] = value
	if states:
		if name and selectedElementEnabled():
			states = states.copy()
			states.discard(get_control_type("STATE_SELECTED"))
			states.discard(get_control_type("STATE_SELECTABLE"))
		properties["states"] = " ".join(
			controlTypes.processAndLabelStates(
				role,
				states,
				REASON_FOCUS,
				states,
				None,
				positiveStateLabels,
				negativeStateLabels,
			)
		)
	if description:
		properties["description"] = description
	keyboardShortcut = propertyValues.get("keyboardShortcut")
	if keyboardShortcut:
		properties["keyboardShortcut"] = keyboardShortcut
	if positionInfo:
		indexInGroup = positionInfo.get("indexInGroup")
		similarItemsInGroup = positionInfo.get("similarItemsInGroup")
		if indexInGroup and similarItemsInGroup:
			properties["positionInfo"] = "{number}/{total}".format(
				number=indexInGroup, total=similarItemsInGroup
			)
		if level is not None:
			properties["positionInfoLevel"] = N_("lv %s") % positionInfo["level"]

	rowCoordinate = ""
	columnCoordinate = ""
	columnHeaderText = ""
	if rowNumber:
		if includeTableCellCoords and not cellCoordsText:
			if rowSpan > 1:
				rowCoordinate = N_("r{rowNumber}-{rowSpan}").format(
					rowNumber=rowNumber, rowSpan=rowNumber + rowSpan - 1
				)
			else:
				rowCoordinate = N_("r{rowNumber}").format(rowNumber=rowNumber)
	if columnNumber:
		columnHeaderText = propertyValues.get("columnHeaderText")
		if includeTableCellCoords and not cellCoordsText:
			if columnSpan > 1:
				columnCoordinate = N_("c{columnNumber}-{columnSpan}").format(
					columnNumber=columnNumber, columnSpan=columnNumber + columnSpan - 1
				)
			else:
				columnCoordinate = N_("c{columnNumber}").format(columnNumber=columnNumber)
	if not cellCoordsText and columnHeaderText or rowCoordinate or columnCoordinate:
		includeTableCellCoords = True
		if rowCoordinate and columnCoordinate:
			cellCoordsText = rowCoordinate + columnCoordinate
			if columnHeaderText:
				cellCoordsText += "(%s)" % columnHeaderText
		elif rowCoordinate:
			cellCoordsText = rowCoordinate
		elif columnCoordinate:
			cellCoordsText = columnHeaderText
	isCurrent = propertyValues.get("current", IS_CURRENT_NO)
	if isCurrent != IS_CURRENT_NO:
		properties["current"] = is_current_display_string(isCurrent)
	placeholder = propertyValues.get("placeholder", None)
	if placeholder:
		properties["placeholder"] = placeholder
	if includeTableCellCoords and cellCoordsText:
		properties["cellCoordsText"] = cellCoordsText
	finalStr = []
	for k in orderProperties:
		if k in properties and properties[k]:
			finalStr.append(properties[k])
	return TEXT_SEPARATOR.join(finalStr)


def validProgressBar(obj):
	List = [
		isinstance(obj, ProgressBar),
		config.conf["brailleExtender"]["objectPresentation"]["progressBarUpdate"],
		controlTypes.STATE_INVISIBLE not in obj.states,
		controlTypes.STATE_OFFSCREEN not in obj.states,
	]
	inForeground = obj.isInForeground
	if not config.conf["brailleExtender"]["objectPresentation"]["reportBackgroundProgressBars"]:
		List.append(
			config.conf["presentation"]["progressBarUpdates"]["reportBackgroundProgressBars"] or inForeground
		)
	elif config.conf["brailleExtender"]["objectPresentation"]["reportBackgroundProgressBars"] == int(
		addoncfg.CHOICE_disabled
	):
		List.append(inForeground)
	return List


def generateProgressBarString(value, displaySize):
	if isinstance(value, str):
		intString = ""
		try:
			intString = re.search(r"(\d+)", value).group(1)
		except AttributeError:
			return
		if not intString == "100" and len(intString) > 2:
			intString = intString[:2]
		value = int(intString)
	return "⣿" * (value * displaySize // 100)


class ManageOrderProperties(gui.settingsDialogs.SettingsDialog):
	# Translators: title of a dialog.
	title = _("Order Properties")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		self.orderProperties = {k: PROPERTIES_ORDER[k] for k in getOrderProperties()}
		self.orderPropertiesList = sHelper.addLabeledControl(
			_("Properties"), wx.Choice, choices=self.getProperties()
		)
		self.orderPropertiesList.Bind(wx.EVT_CHOICE, self.onOrderPropertiesList)
		self.orderPropertiesList.SetSelection(0)
		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.moveUpBtn = bHelper.addButton(self, label=_("Move &up"))
		self.moveUpBtn.Bind(wx.EVT_BUTTON, lambda evt: self.move(evt, MOVE_UP))
		self.moveDownBtn = bHelper.addButton(self, label=_("Move &down"))
		self.moveDownBtn.Bind(wx.EVT_BUTTON, lambda evt: self.move(evt, MOVE_DOWN))
		sHelper.addItem(bHelper)

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.resetNVDAOrder = bHelper.addButton(self, label=_("Reset to the default &NVDA order"))
		self.resetNVDAOrder.Bind(wx.EVT_BUTTON, lambda evt: self.assign(evt, NVDA_ORDER))
		self.resetAddonOrder = bHelper.addButton(self, label=_("Reset to the &default add-on order"))
		self.resetAddonOrder.Bind(wx.EVT_BUTTON, lambda evt: self.assign(evt, ADDON_ORDER))
		sHelper.addItem(bHelper)

	def onOrderPropertiesList(self, evt=None):
		curPos = self.orderPropertiesList.GetSelection()
		if not curPos:
			self.moveUpBtn.Disable()
			self.moveDownBtn.Enable()
		elif curPos >= len(self.orderProperties) - 1:
			self.moveDownBtn.Disable()
			self.moveUpBtn.Enable()
		else:
			self.moveDownBtn.Enable()
			self.moveUpBtn.Enable()

	def assign(self, evt, name):
		if name == NVDA_ORDER:
			order = self.orderProperties = getDefaultOrderProperties()
		else:
			order = getDefaultOrderProperties(True)
		self.orderProperties = {e: PROPERTIES_ORDER[e] for e in order}
		setOrderProperties(self.getPropertiesKeys())
		self.refresh()
		self.orderPropertiesList.SetSelection(0)
		self.orderPropertiesList.SetFocus()

	def move(self, evt, direction):
		firstPos = self.orderPropertiesList.GetSelection()
		secondPos = firstPos + (1 if direction == MOVE_DOWN else -1)
		if secondPos < 0 or secondPos > len(self.getProperties()) - 1:
			return
		toReplace = {
			self.getPropertiesKeys()[firstPos]: self.getPropertiesKeys()[secondPos],
			self.getPropertiesKeys()[secondPos]: self.getPropertiesKeys()[firstPos],
		}
		firstLabel = self.getProperties()[firstPos]
		secondLabel = self.getProperties()[secondPos]
		ordered_keys = [k if k not in toReplace else toReplace[k] for k in self.getPropertiesKeys()]
		self.orderProperties = {e: PROPERTIES_ORDER[e] for e in ordered_keys}
		setOrderProperties(self.getPropertiesKeys())
		self.refresh()
		self.orderPropertiesList.SetSelection(secondPos)
		directionLabel = _("after") if direction == MOVE_DOWN else _("before")
		queueHandler.queueFunction(
			queueHandler.eventQueue,
			ui.message,
			f"{firstLabel} {directionLabel} {secondLabel}",
		)

	def refresh(self):
		self.orderPropertiesList.SetItems(self.getProperties())
		self.onOrderPropertiesList()

	def getPropertiesKeys(self):
		return list(self.orderProperties.keys())

	def getProperties(self):
		return list(self.orderProperties.values())

	def postInit(self):
		self.onOrderPropertiesList()
		self.orderPropertiesList.SetFocus()

	def onOk(self, evt):
		setOrderProperties(list(self.getPropertiesKeys()), True)
		loadOrderProperties()
		super().onOk(evt)


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = N_("Object Presentation")

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.choices = {k: v for k, v in CHOICES_LABELS.items() if k != CHOICE_liblouis}
		try:
			itemToSelect = list(self.choices.keys()).index(
				config.conf["brailleExtender"]["objectPresentation"]["selectedElement"]
			)
		except IndexError:
			itemToSelect = 0
		self.selectedElement = sHelper.addLabeledControl(
			_("Selected &elements:"),
			wx.Choice,
			choices=list(self.choices.values()),
		)
		self.selectedElement.SetSelection(itemToSelect)
		self.progressBarUpdate = sHelper.addLabeledControl(
			_("Progress bar output using braille messages:"),
			wx.Choice,
			choices=[
				_("disabled (original behavior)"),
				_("enabled, show raw value"),
				_("enabled, show a progress bar using ⣿"),
			],
		)
		self.progressBarUpdate.SetSelection(
			config.conf["brailleExtender"]["objectPresentation"]["progressBarUpdate"]
		)
		self.background = sHelper.addLabeledControl(
			_("Report background progress bars:"),
			wx.Choice,
			choices=list(LABELS_STATES.values()),
		)
		self.background.SetSelection(
			config.conf["brailleExtender"]["objectPresentation"]["reportBackgroundProgressBars"]
		)

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.orderPropertiesBtn = bHelper.addButton(self, label="&Order Properties...")
		self.orderPropertiesBtn.Bind(wx.EVT_BUTTON, self.onOrderPropertiesBtn)

		sHelper.addItem(bHelper)

	def onOrderPropertiesBtn(self, evt):
		manageOrderProperties = ManageOrderProperties(self)
		manageOrderProperties.ShowModal()
		manageOrderProperties.Destroy()
		self.orderPropertiesBtn.SetFocus()

	def onSave(self):
		config.conf["brailleExtender"]["objectPresentation"]["selectedElement"] = list(self.choices.keys())[
			self.selectedElement.GetSelection()
		]
		config.conf["brailleExtender"]["objectPresentation"]["progressBarUpdate"] = (
			self.progressBarUpdate.GetSelection()
		)
		config.conf["brailleExtender"]["objectPresentation"]["reportBackgroundProgressBars"] = (
			self.background.GetSelection()
		)


REASON_FOCUS = get_output_reason("FOCUS")
