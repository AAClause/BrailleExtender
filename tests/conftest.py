# coding: utf-8
"""Test fixtures and mock environment for NVDA and BrailleExtender."""

import os
import sys
import types
from unittest.mock import MagicMock

# Ensure addon directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIR = os.path.join(BASE_DIR, "addon")
GLOBAL_PLUGINS_DIR = os.path.join(ADDON_DIR, "globalPlugins")

if ADDON_DIR not in sys.path:
	sys.path.insert(0, ADDON_DIR)
if GLOBAL_PLUGINS_DIR not in sys.path:
	sys.path.insert(0, GLOBAL_PLUGINS_DIR)


class BrailleTableMock:
	def __init__(
		self,
		file_name: str,
		display_name: str,
		*,
		input_table: bool = True,
		output_table: bool = True,
		contracted: bool = False,
	):
		self.fileName = file_name
		self.displayName = display_name
		self.input = input_table
		self.output = output_table
		self.contracted = contracted

	def __getitem__(self, index):
		if index == 0:
			return self.fileName
		elif index == 1:
			return self.displayName
		raise IndexError(index)


# Define standard tables for tests
SAMPLE_TABLES = [
	BrailleTableMock(
		"en-us-comp8.utb",
		"English (U.S.) 8 dot computer braille",
		input_table=True,
		output_table=True,
		contracted=False,
	),
	BrailleTableMock(
		"unicode-braille.utb", "Unicode braille", input_table=True, output_table=True, contracted=False
	),
	BrailleTableMock(
		"en-ueb-g2.ctb",
		"Unified English Braille Code (grade 2)",
		input_table=True,
		output_table=True,
		contracted=True,
	),
	BrailleTableMock(
		"fr-bfu-comp8.utb",
		"French 8 dot computer braille",
		input_table=True,
		output_table=True,
		contracted=False,
	),
	BrailleTableMock("ar-ar-g1.utb", "Arabic 6 dot", input_table=True, output_table=True, contracted=False),
]


class ConfDict(dict):
	"""Dict that returns sub-ConfDict for missing keys."""

	def __getitem__(self, key):
		if key not in self:
			self[key] = ConfDict()
		return super().__getitem__(key)


def build_mock_modules():
	"""Create mock NVDA modules and register them in sys.modules."""
	# addonHandler
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.initTranslation = MagicMock()

	class AddonMock:
		def __init__(self, *args, **kwargs):
			self.manifest = {
				"name": "brailleExtender",
				"summary": "Braille Extender",
				"version": "26.1.0",
				"url": "https://example.com",
				"author": "Test Author",
				"description": "Test Description",
				"updateChannel": "stable",
			}

	addonHandler.Addon = AddonMock

	# versionInfo
	versionInfo = types.ModuleType("versionInfo")
	versionInfo.version = "2025.1.0"

	# globalVars
	globalVars = types.ModuleType("globalVars")
	config_dir = "/tmp/nvda_test_config"
	os.makedirs(os.path.join(config_dir, "brailleExtender"), exist_ok=True)
	appArgs = types.SimpleNamespace(configPath=config_dir, secure=True)
	globalVars.appArgs = appArgs

	# languageHandler
	languageHandler = types.ModuleType("languageHandler")
	languageHandler.getLanguage = MagicMock(return_value="en_US")

	# logHandler
	logHandler = types.ModuleType("logHandler")
	logHandler.log = MagicMock()

	# speech
	speech = types.ModuleType("speech")
	speech.speakMessage = MagicMock()

	# ui
	ui = types.ModuleType("ui")
	ui.message = MagicMock(side_effect=lambda msg: speech.speakMessage(msg))

	# core
	core = types.ModuleType("core")
	core.restart = MagicMock()

	# config
	config = types.ModuleType("config")
	conf = ConfDict(
		{
			"braille": ConfDict(
				{
					"inputTable": "en-us-comp8.utb",
					"translationTable": "en-us-comp8.utb",
					"display": "noBraille",
					"expandAtCursor": False,
				}
			),
			"brailleExtender": ConfDict(
				{
					"inputTables": "en-us-comp8.utb,unicode-braille.utb",
					"outputTables": "en-us-comp8.utb",
					"activeInputTable": "",
					"activeOutputTable": "",
					"primaryInputTable": "",
					"secondaryInputTable": "None",
					"inputTableShortcuts": "?",
					"postTable": "None",
					"brailleDisplay1": "last",
					"brailleDisplay2": "last",
					"tabSpace": False,
					"tabSize_noBraille": 2,
					"updateChannel": "stable",
					"objectPresentation": ConfDict(
						{
							"orderProperties": "typeform,controlField,name,role,states,value,description,keyboardShortcut,positionInfoLevel,current,placeholder,cellCoordsText",
						}
					),
					"features": ConfDict(
						{
							"roleLabels": False,
							"attributes": True,
						}
					),
				}
			),
		}
	)
	conf.spec = ConfDict()
	config.conf = conf

	appModuleHandler = types.ModuleType("appModuleHandler")
	appModuleHandler.registerExecutableWithAppModule = MagicMock()
	appModuleHandler.getAppModuleForNVDAObject = MagicMock(return_value=types.SimpleNamespace(appName="nvda"))

	appModules_excel = types.ModuleType("appModules.excel")

	class AppModuleMock:
		pass

	appModules_excel.AppModule = AppModuleMock

	globalCommands = types.ModuleType("globalCommands")
	globalCommands.commands = MagicMock()

	class GlobalCommands:
		script_braille_routeTo = MagicMock()

	globalCommands.GlobalCommands = GlobalCommands

	keyLabels = types.ModuleType("keyLabels")
	keyLabels.localizedKeyLabels = {}

	tones = types.ModuleType("tones")
	tones.beep = MagicMock()

	virtualBuffers = types.ModuleType("virtualBuffers")

	vision = types.ModuleType("vision")

	# brailleTables
	brailleTables = types.ModuleType("brailleTables")
	table_dict = {t.fileName: t for t in SAMPLE_TABLES}
	brailleTables._tables = table_dict
	brailleTables.listTables = MagicMock(return_value=list(SAMPLE_TABLES))

	def get_table(table_id):
		if table_id in table_dict:
			return table_dict[table_id]
		raise LookupError(f"Table not found: {table_id}")

	brailleTables.getTable = MagicMock(side_effect=get_table)

	class TableType:
		INPUT = 1
		OUTPUT = 2

	brailleTables.TableType = TableType
	brailleTables.getDefaultTableForCurLang = MagicMock(return_value="en-us-comp8.utb")
	brailleTables.DEFAULT_TABLE = "en-us-comp8.utb"
	brailleTables.TABLES_DIR = os.path.join(config_dir, "tables")
	os.makedirs(brailleTables.TABLES_DIR, exist_ok=True)
	with open(os.path.join(brailleTables.TABLES_DIR, "braille-patterns.cti"), "w") as f:
		f.write("")
	for t in SAMPLE_TABLES:
		with open(os.path.join(brailleTables.TABLES_DIR, t.fileName), "w") as f:
			f.write("")

	# brailleInput
	brailleInput = types.ModuleType("brailleInput")

	class BrailleInputHandler:
		_translate = MagicMock()
		emulateKey = MagicMock()
		input = MagicMock()
		sendChars = MagicMock()

	brailleInput.BrailleInputHandler = BrailleInputHandler
	braille_input_handler = types.SimpleNamespace(
		table=table_dict["en-us-comp8.utb"],
		_table=table_dict["en-us-comp8.utb"],
	)
	brailleInput.handler = braille_input_handler

	# braille
	braille = types.ModuleType("braille")
	braille.getControlFieldBraille = MagicMock()
	braille.getFormatFieldBraille = MagicMock()
	braille.getPropertiesBraille = MagicMock()

	class Region:
		update = MagicMock()

	class NVDAObjectRegion(Region):
		update = MagicMock()

	class TextInfoRegion(Region):
		_addTextWithFields = MagicMock()
		update = MagicMock()
		previousLine = MagicMock()
		nextLine = MagicMock()
		_getTypeformFromFormatField = MagicMock()

	class ReviewTextInfoRegion(TextInfoRegion):
		pass

	class BrailleHandler:
		getTether = MagicMock()
		handleGainFocus = MagicMock()
		handleCaretMove = MagicMock()
		setTether = MagicMock()
		_displayWithCursor = MagicMock()

	braille.Region = Region
	braille.NVDAObjectRegion = NVDAObjectRegion
	braille.TextInfoRegion = TextInfoRegion
	braille.ReviewTextInfoRegion = ReviewTextInfoRegion
	braille.BrailleHandler = BrailleHandler
	braille_display = types.SimpleNamespace(name="noBraille")
	braille_handler = types.SimpleNamespace(
		display=braille_display,
		displaySize=40,
		_table=table_dict["en-us-comp8.utb"],
		message=MagicMock(),
		report_auto_scroll_delay=MagicMock(),
		handleGainFocus=MagicMock(),
	)
	braille.handler = braille_handler
	braille.getDisplayList = MagicMock(return_value=[("noBraille", "No braille")])

	controlTypes = types.ModuleType("controlTypes")
	controlTypes.IsCurrent = types.SimpleNamespace(NO=0, YES=1)

	class OutputReason:
		FOCUS = 1
		CARET = 2
		SAYALL = 3
		ONLY = 4

	controlTypes.OutputReason = OutputReason

	class Role:
		UNKNOWN = 0

	controlTypes.Role = Role

	# scriptHandler
	scriptHandler = types.ModuleType("scriptHandler")

	def script_decorator(**kwargs):
		def decorator(fn):
			fn._script_kwargs = kwargs
			return fn

		return decorator

	scriptHandler.script = script_decorator

	# globalPluginHandler
	globalPluginHandler = types.ModuleType("globalPluginHandler")

	class GlobalPluginMock:
		def bindGestures(self, *args, **kwargs):
			pass

		def bindGesture(self, *args, **kwargs):
			pass

		def clearGestures(self, *args, **kwargs):
			pass

	globalPluginHandler.GlobalPlugin = GlobalPluginMock

	# inputCore
	inputCore = types.ModuleType("inputCore")
	inputCore.normalizeGestureIdentifier = MagicMock(side_effect=lambda x: x)

	# keyboardHandler
	keyboardHandler = types.ModuleType("keyboardHandler")
	keyboardHandler.KeyboardInputGesture = MagicMock()

	# treeInterceptorHandler
	treeInterceptorHandler = types.ModuleType("treeInterceptorHandler")
	treeInterceptorHandler.update = MagicMock(return_value=MagicMock(passThrough=True))
	treeInterceptorHandler.getTreeInterceptor = MagicMock(return_value=None)

	# characterProcessing
	characterProcessing = types.ModuleType("characterProcessing")

	# textInfos
	textInfos = types.ModuleType("textInfos")

	# api
	api = types.ModuleType("api")
	api.getNavigatorObject = MagicMock(return_value=MagicMock())
	api.getFocusObject = MagicMock(return_value=MagicMock(treeInterceptor=None))

	# louis
	louis = types.ModuleType("louis")
	louis.dotsIO = 1
	louis.compbrlAtCursor = 2
	louis.pass1Only = 4
	louis.plain_text = 0
	louis.bold = 1
	louis.italic = 2
	louis.underline = 4
	louis.translate = MagicMock(return_value=("", [], [], 0))
	louis.compileString = MagicMock()
	louis.liblouis = types.SimpleNamespace(lou_free=MagicMock())

	# queueHandler
	queueHandler = types.ModuleType("queueHandler")
	queueHandler.queueFunction = MagicMock()
	queueHandler.eventQueue = MagicMock()

	# gui
	gui = types.ModuleType("gui")
	guiHelper = types.ModuleType("guiHelper")
	guiHelper.BoxSizerHelper = MagicMock()
	guiHelper.ButtonHelper = MagicMock()
	gui.guiHelper = guiHelper

	nvdaControls = types.ModuleType("nvdaControls")
	nvdaControls.CustomCheckListBox = MagicMock()
	nvdaControls.SelectOnFocusSpinCtrl = MagicMock()
	gui.nvdaControls = nvdaControls

	settingsDialogs = types.ModuleType("settingsDialogs")
	settingsDialogs.SettingsPanel = object
	settingsDialogs.SettingsDialog = object
	settingsDialogs.MultiCategorySettingsDialog = object
	gui.settingsDialogs = settingsDialogs

	gui.mainFrame = types.SimpleNamespace(
		sysTrayIcon=MagicMock(),
		popupSettingsDialog=MagicMock(),
		_popupSettingsDialog=MagicMock(),
	)

	# wx
	wx = types.ModuleType("wx")
	wx.Panel = object
	wx.Dialog = object
	wx.Sizer = object
	wx.BoxSizer = object
	wx.CommandEvent = object
	wx.HORIZONTAL = 0
	wx.VERTICAL = 1
	wx.Menu = MagicMock
	wx.Choice = MagicMock()
	wx.CheckBox = MagicMock()
	wx.Button = MagicMock()
	wx.StaticText = MagicMock()
	wx.TextCtrl = MagicMock()
	wx.ID_ANY = -1
	wx.OK = 4
	wx.YES = 2
	wx.NO = 8
	wx.ICON_INFORMATION = 1
	wx.ICON_QUESTION = 16
	wx.CallAfter = MagicMock(side_effect=lambda f, *a, **k: f(*a, **k))
	wx.EVT_MENU = MagicMock()
	wx.EVT_BUTTON = MagicMock()
	wx.EVT_CHOICE = MagicMock()

	# configobj
	configobj = types.ModuleType("configobj")
	configobj_validate = types.ModuleType("configobj.validate")
	configobj_validate.Validator = MagicMock()
	configobj_validate.VdtValueError = ValueError
	configobj.validate = configobj_validate

	# colors
	colors = types.ModuleType("colors")

	# comtypes
	comtypes = types.ModuleType("comtypes")
	comtypes.__path__ = []
	comtypes_client = types.ModuleType("comtypes.client")
	comtypes.client = comtypes_client
	comtypes_automation = types.ModuleType("comtypes.automation")
	comtypes_automation.BSTR = str
	comtypes.automation = comtypes_automation
	import ctypes

	class GUID(ctypes.Structure):
		_fields_ = [("Data1", ctypes.c_ulong)]

		def __init__(self, *args, **kwargs):
			pass

	comtypes.c_float = ctypes.c_float
	comtypes.COMMETHOD = MagicMock(return_value=lambda f: f)
	comtypes.GUID = GUID
	comtypes.HRESULT = ctypes.c_long
	comtypes.IUnknown = type("IUnknown", (ctypes.c_void_p,), {})
	comtypes.STDMETHOD = MagicMock(return_value=lambda f: f)
	comtypes.COMError = Exception
	comtypes.CoCreateInstance = MagicMock()
	comtypes.CLSCTX_INPROC_SERVER = 1

	# eventHandler
	eventHandler = types.ModuleType("eventHandler")
	eventHandler.requestEvents = MagicMock()

	# NVDAHelper
	NVDAHelper = types.ModuleType("NVDAHelper")
	NVDAHelper.__path__ = []
	NVDAHelper_localLib = types.ModuleType("NVDAHelper.localLib")

	class EXCEL_CELLINFO:
		pass

	NVDAHelper_localLib.EXCEL_CELLINFO = EXCEL_CELLINFO
	NVDAHelper.localLib = NVDAHelper_localLib

	# NVDAObjects
	NVDAObjects = types.ModuleType("NVDAObjects")
	NVDAObjects.__path__ = []
	NVDAObjects_behaviors = types.ModuleType("NVDAObjects.behaviors")

	class ProgressBar:
		pass

	NVDAObjects_behaviors.ProgressBar = ProgressBar
	NVDAObjects.behaviors = NVDAObjects_behaviors

	NVDAObjects_window = types.ModuleType("NVDAObjects.window")
	NVDAObjects_window.__path__ = []
	NVDAObjects_window_excel = types.ModuleType("NVDAObjects.window.excel")

	class ExcelCellInfo:
		pass

	NVDAObjects_window_excel.ExcelCellInfo = ExcelCellInfo
	NVDAObjects_window.excel = NVDAObjects_window_excel
	NVDAObjects.window = NVDAObjects_window

	# cursorManager
	cursorManager = types.ModuleType("cursorManager")

	# louisHelper
	louisHelper = types.ModuleType("louisHelper")

	# nvwave
	nvwave = types.ModuleType("nvwave")
	nvwave.playWaveFile = MagicMock()

	# winUser
	winUser = types.ModuleType("winUser")

	# Built-in translation functions in builtins
	import builtins

	builtins._ = lambda s: s
	builtins.ngettext = lambda s, p, n: s if n == 1 else p
	builtins.pgettext = lambda c, s: s
	builtins.npgettext = lambda c, s, p, n: s if n == 1 else p

	modules = {
		"addonHandler": addonHandler,
		"versionInfo": versionInfo,
		"globalVars": globalVars,
		"languageHandler": languageHandler,
		"logHandler": logHandler,
		"speech": speech,
		"ui": ui,
		"core": core,
		"config": config,
		"brailleTables": brailleTables,
		"brailleInput": brailleInput,
		"braille": braille,
		"controlTypes": controlTypes,
		"scriptHandler": scriptHandler,
		"globalPluginHandler": globalPluginHandler,
		"inputCore": inputCore,
		"keyboardHandler": keyboardHandler,
		"treeInterceptorHandler": treeInterceptorHandler,
		"characterProcessing": characterProcessing,
		"textInfos": textInfos,
		"api": api,
		"louis": louis,
		"queueHandler": queueHandler,
		"gui": gui,
		"gui.guiHelper": guiHelper,
		"gui.nvdaControls": nvdaControls,
		"gui.settingsDialogs": settingsDialogs,
		"wx": wx,
		"appModuleHandler": appModuleHandler,
		"globalCommands": globalCommands,
		"keyLabels": keyLabels,
		"tones": tones,
		"virtualBuffers": virtualBuffers,
		"vision": vision,
		"configobj": configobj,
		"configobj.validate": configobj_validate,
		"colors": colors,
		"comtypes": comtypes,
		"comtypes.client": comtypes_client,
		"comtypes.automation": comtypes_automation,
		"cursorManager": cursorManager,
		"louisHelper": louisHelper,
		"nvwave": nvwave,
		"winUser": winUser,
		"eventHandler": eventHandler,
		"NVDAHelper": NVDAHelper,
		"NVDAHelper.localLib": NVDAHelper_localLib,
		"appModules.excel": appModules_excel,
		"NVDAObjects": NVDAObjects,
		"NVDAObjects.behaviors": NVDAObjects_behaviors,
		"NVDAObjects.window": NVDAObjects_window,
		"NVDAObjects.window.excel": NVDAObjects_window_excel,
	}

	for name, mod in modules.items():
		sys.modules[name] = mod

	return modules


# Initialize mocks immediately when conftest is imported
build_mock_modules()
