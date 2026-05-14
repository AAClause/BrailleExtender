# coding: utf-8
from __future__ import annotations

# documentformatting.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.
from collections import namedtuple
from typing import Any

import addonHandler
import braille
import config
import gui
import louis
import textInfos
import ui
import wx
from logHandler import log

from . import regionhelper
from .common import (
	N_,
	BRLEX_CELL_MASK_BY_METHOD,
	CHOICE_none,
	CHOICE_dot7,
	CHOICE_dot8,
	CHOICE_dots78,
	CHOICE_tags,
	CHOICE_liblouis,
	CHOICE_likeSpeech,
	CHOICE_enabled,
	CHOICE_disabled,
	TAG_SEPARATOR,
	CHOICE_spacing
)

addonHandler.initTranslation()

# Attributes read from each format-change field when building Liblouis flags and dot-7/8 overlays.
_FORMAT_CHANGE_TYPEFORM_ATTRS: tuple[str, ...] = (
	"bold",
	"italic",
	"underline",
	"strikethrough",
	"strong",
	"emphasised",
	"marked",
	"text-position",
	"invalid-spelling",
	"invalid-grammar",
)

_LIBLOUIS_FLAGS_BY_ATTR: dict[str, int] = {
	"bold": louis.bold,
	"italic": louis.italic,
	"underline": louis.underline,
	"strong": louis.bold,
	"emphasised": louis.italic,
	"marked": louis.underline,
}

_NVDA_MANAGED_SPELLING_ATTRS: frozenset[str] = frozenset(("invalid-spelling", "invalid-grammar"))
_NVDA_MANAGED_CLASSIC_FONT_ATTRS: frozenset[str] = frozenset(
	("bold", "italic", "underline", "strikethrough")
)
_NVDA_SEMANTIC_EMPHASIS_ATTRS: frozenset[str] = frozenset(("strong", "emphasised"))
_NVDA_SEMANTIC_MARK_ATTRS: frozenset[str] = frozenset(("marked",))

CHOICES_LABELS = {
	CHOICE_none: _("nothing"),
	CHOICE_liblouis: _("hand over to Liblouis (defined in tables)"),
	CHOICE_dots78: _("dots 7 and 8"),
	CHOICE_dot7: _("dot 7"),
	CHOICE_dot8: _("dot 8"),
	CHOICE_tags: _("tags"),
}

TAG_FORMATTING = namedtuple("TAG_FORMATTING", ("start", "end"))

LABELS_FORMATTING = {
	"bold": _("bold"),
	"italic": _("italic"),
	"underline": _("underline"),
	"strikethrough": _("strikethrough"),
	"strong": _("strong emphasis"),
	"emphasised": _("emphasised text"),
	"marked": _("marked (highlighted)"),
	"text-position:sub": _("subscript"),
	"text-position:super": _("superscript"),
	"invalid-spelling": _("spelling errors"),
	"invalid-grammar": _("grammar errors"),
	"text-align:center": _("centered alignment"),
	"text-align:distribute": _("distributed alignment"),
	"text-align:justified": _("justified alignment"),
	"text-align:left": _("left alignment"),
	"text-align:right": _("right alignment"),
	"text-align:start": _("default alignment"),
	"revision-insertion": _("inserted revision"),
	"revision-deletion": _("deleted revision"),
	"comments": _("notes and comments"),
}

LABELS_STATES = {
	# Translators: First option in each document-formatting report row. This follows NVDA’s “Document formatting” category (what NVDA reports, including braille-related bits), and NVDA’s own braille markers when NVDA defines them. It is not the same as “output like speech only”. If your language needs a shorter string, consider: “Use NVDA defaults (document formatting & core braille)”.
	CHOICE_likeSpeech: _("Follow NVDA document formatting"),
	CHOICE_enabled: _("enabled"),
	CHOICE_disabled: _("disabled"),
}

LABELS_REPORTS = {
	"fontAttributes": N_("Font attrib&utes"),
	"superscriptsAndSubscripts": N_("Su&perscripts and subscripts"),
	"emphasis": N_("E&mphasis"),
	"highlight": N_("Marked (highlighted text)"),
	"spellingErrors": _("Spelling and grammar &errors"),
	"alignment": N_("&Alignment"),
	"color": N_("&Colors"),
	"style": N_("St&yle"),
	"borderColor": N_("Border &color"),
	"borderStyle": N_("Border St&yle"),
	"fontName": N_("&Font name"),
	"fontSize": N_("Font &size"),
	"page": N_("&Pages"),
	"lineNumber": N_("Line &numbers"),
	"paragraphIndentation": N_("&Paragraph indentation"),
	"links": N_("Lin&ks"),
	"headings": N_("&Headings"),
	"graphics": N_("&Graphics"),
	"lists": N_("&Lists"),
	"blockQuotes": N_("Block &quotes"),
	"groupings": N_("&Groupings"),
	"landmarks": N_("Lan&dmarks and regions"),
	"articles": N_("Arti&cles"),
	"frames": N_("Fra&mes"),
	"clickable": N_("&Clickable"),
	"comments": N_("No&tes and comments"),
	"revisions": N_("&Editor revisions"),
	"tables": N_("&Tables"),
	"tableHeaders": N_("Row/column h&eaders"),
	"tableCellCoords": N_("Cell c&oordinates")
}

logTextInfo = False
conf = config.conf["brailleExtender"]["documentFormatting"]


def normalize_report_key(key: str) -> str | None:
	"""Map add-on report ids to keys present in NVDA ``documentFormatting``."""
	aliases = {
		"fontAttributes": ("fontAttributeReporting",),
		"spellingErrors": ("reportSpellingErrors2", "reportSpellingErrors"),
		"emphasis": ("reportEmphasis",),
		"highlight": ("reportHighlight",),
	}
	if key in aliases:
		for candidate in aliases[key]:
			if candidate in config.conf["documentFormatting"]:
				return candidate
	key_ = "report" + key[0].upper() + key[1:]
	if key_ in config.conf["documentFormatting"]:
		return key_
	if key_ == "reportFontAttributes":
		return "fontAttributeReporting"
	return None


def format_config_indicates_spelling_braille(formatConfig: dict[str, Any] | None) -> bool:
	"""True when NVDA format flags request spelling/grammar indication in braille (bitmask or legacy bool)."""
	if not formatConfig:
		return False
	val = formatConfig.get("reportSpellingErrors2")
	if val is None:
		val = formatConfig.get("reportSpellingErrors")
	if val is None:
		return False
	if isinstance(val, bool):
		return val
	try:
		from config.configFlags import ReportSpellingErrors

		return (int(val) & int(ReportSpellingErrors.BRAILLE)) != 0
	except (TypeError, ValueError, AttributeError, ImportError):
		return bool(val)


def format_config_font_attributes_report_braille(formatConfig: dict[str, Any] | None) -> bool:
	"""True when NVDA requests font attribute information in braille (bitmask or legacy bool)."""
	if not formatConfig:
		return False
	raw_flag = formatConfig.get("fontAttributeReporting")
	if raw_flag is None:
		return bool(formatConfig.get("reportFontAttributes", False))
	try:
		from config.configFlags import OutputMode

		# ``addTextWithFields_edit`` may set ``fontAttributeReporting`` to ``True`` when the add-on
		# report row is "enabled"; ``True & OutputMode.BRAILLE`` is wrong when the braille bit is not 1.
		if isinstance(raw_flag, bool):
			return raw_flag
		if isinstance(raw_flag, int):
			return (raw_flag & int(OutputMode.BRAILLE)) != 0
		return bool(raw_flag & OutputMode.BRAILLE)
	except (ImportError, TypeError, ValueError, AttributeError):
		return raw_flag == 1 or raw_flag is True


def get_report(key, simple=True):
	if key in conf["reports"]:
		val = conf["reports"][key]
		if not simple:
			return val
		if conf["plainText"]:
			return False
		if val == CHOICE_likeSpeech:
			normalized_key = normalize_report_key(key)
			if not normalized_key:
				return
			return config.conf["documentFormatting"][
				normalized_key
			]
		return val == CHOICE_enabled
	if key not in conf:
		log.error(f"unknown {key} key")
		return None
	if isinstance(conf[key], config.AggregatedSection) and "enabled" in conf[key]:
		return conf[key]["enabled"]
	return conf[key]


def set_report(k, v, sect=False):
	if k not in conf["reports"]:
		log.error(f"unknown key/section '{k}'")
		return False
	if sect:
		if not isinstance(conf["reports"][k], config.AggregatedSection):
			log.error(f"'{k}' is not a section")
			return False
		if not "enabled" in conf["reports"][k]:
			log.error(f"'{k}' is not a valid section")
			return False
		conf[k]["enabled"] = v
	else:
		if isinstance(conf["reports"][k], config.AggregatedSection):
			log.error(f"'{k}' is not a key")
		conf["reports"][k] = v
	return True


def report_row_follows_nvda(key: str) -> bool:
	"""True when this add-on document-formatting row follows NVDA (``CHOICE_likeSpeech`` / "Follow NVDA document formatting")."""
	if key not in conf["reports"]:
		return False
	return get_report(key, simple=False) == CHOICE_likeSpeech


def use_be_format_field_chrome(key: str) -> bool:
	"""When False, skip BrailleExtender-only braille (⣏ wrappers, configured Tags for that row, …) and match NVDA core."""
	return not report_row_follows_nvda(key)


def toggle_report(report):
	cur = get_report(report, 0)
	if not cur:
		cur = CHOICE_likeSpeech
	l = list(LABELS_STATES.keys())
	cur_index = l.index(cur)
	new_index = (cur_index + 1) % len(l)
	set_report(report, l[new_index])


def report_formatting(report):
	cur = get_report(report, 0)
	label_report = LABELS_REPORTS[report].replace('&', '')
	label_state = LABELS_STATES.get(cur)
	if not label_state:
		label_state = N_("unknown")
	ui.message(_("{}: {}").format(label_report, label_state))


def get_method(k):
	l = [k]
	if ':' in k:
		l.append(k.split(':', 1)[0])
	for e in l:
		if e in conf["methods"]:
			return conf["methods"][e]
	return CHOICE_none


def get_liblouis_typeform(attr_name: str) -> int:
	return _LIBLOUIS_FLAGS_BY_ATTR.get(attr_name, louis.plain_text)


def decorator(fn, s):
	def _getTypeformFromFormatField(self, field, formatConfig=None):
		if formatConfig is None:
			formatConfig = {}
		spell_attrs_delegated_to_nvda = (
			report_row_follows_nvda("spellingErrors")
			and format_config_indicates_spelling_braille(formatConfig)
		)
		classic_font_attrs_delegated_to_nvda = (
			report_row_follows_nvda("fontAttributes")
			and format_config_font_attributes_report_braille(formatConfig)
		)
		semantic_emphasis_delegated_to_nvda = (
			report_row_follows_nvda("emphasis")
			and bool(formatConfig.get("reportEmphasis", False))
		)
		semantic_highlight_delegated_to_nvda = (
			report_row_follows_nvda("highlight")
			and bool(formatConfig.get("reportHighlight", False))
		)
		nvda_format_markers = getattr(braille, "fontAttributeFormattingMarkers", None) or {}
		louis_typeform_flags = louis.plain_text
		extra_dots_cell_mask = 0
		for attr_name in _FORMAT_CHANGE_TYPEFORM_ATTRS:
			if spell_attrs_delegated_to_nvda and attr_name in _NVDA_MANAGED_SPELLING_ATTRS:
				continue
			if classic_font_attrs_delegated_to_nvda and attr_name in _NVDA_MANAGED_CLASSIC_FONT_ATTRS:
				continue
			if (
				semantic_emphasis_delegated_to_nvda
				and attr_name in _NVDA_SEMANTIC_EMPHASIS_ATTRS
				and attr_name in nvda_format_markers
			):
				continue
			if (
				semantic_highlight_delegated_to_nvda
				and attr_name in _NVDA_SEMANTIC_MARK_ATTRS
				and "marked" in nvda_format_markers
			):
				continue
			attr_value = field.get(attr_name, False)
			if not attr_value:
				continue
			if isinstance(attr_value, bool):
				attr_value = "1"
			presentation_method = get_method(f"{attr_name}:{attr_value}")
			if presentation_method == CHOICE_liblouis:
				louis_typeform_flags |= get_liblouis_typeform(attr_name)
			else:
				overlay = BRLEX_CELL_MASK_BY_METHOD.get(presentation_method, 0)
				if overlay:
					extra_dots_cell_mask |= overlay
		return louis_typeform_flags, extra_dots_cell_mask

	def addTextWithFields_edit(self, info, formatConfig, isSelection=False):
		formatConfig_ = formatConfig.copy()
		keysToEnable = []
		for e in LABELS_REPORTS.keys():
			normalized_key = normalize_report_key(e)
			if not normalized_key:
				continue
			addon_row = conf["reports"].get(e)
			if addon_row == CHOICE_enabled and normalized_key == "fontAttributeReporting":
				try:
					from config.configFlags import OutputMode

					prev = formatConfig_.get(normalized_key)
					mask = int(OutputMode.SPEECH) | int(OutputMode.BRAILLE)
					if isinstance(prev, int):
						formatConfig_[normalized_key] = prev | mask
					else:
						formatConfig_[normalized_key] = mask
				except Exception:
					formatConfig_[normalized_key] = True
			else:
				formatConfig_[normalized_key] = get_report(e)
		textInfo_ = info.getTextWithFields(formatConfig_)
		formatField = textInfos.FormatField()
		for field in textInfo_:
			if isinstance(field, textInfos.FieldCommand) and isinstance(
					field.field, textInfos.FormatField
			):
				formatField.update(field.field)
		if logTextInfo:
			log.info(formatField)
		self.formatField = formatField
		fn(self, info, formatConfig_, isSelection)

	def update(self):
		fn(self)
		postReplacements = []
		noAlign = False
		if conf["lists"]["showLevelItem"] and self and hasattr(self.obj, "currentNVDAObject"):
			curObj = self.obj.currentNVDAObject
			if curObj and hasattr(curObj, "IA2Attributes"):
				IA2Attributes = curObj.IA2Attributes
				tag = IA2Attributes.get("tag")
				if tag == "li":
					s = (int(IA2Attributes["level"]) - 1) * \
						2 if IA2Attributes.get("level") else 0
					noAlign = True
					postReplacements.append(regionhelper.BrailleCellReplacement(
						start=0, insertBefore=('⠀' * s)))
		formatField = self.formatField
		"""
		if get_report("indentations") and not noAlign and formatField.get("left-indent"):
			leftIndent = formatField.get("left-indent").split('.')
			postReplacements.append(regionhelper.BrailleCellReplacement(
				start=0, insertBefore=('⠀' * abs(int(leftIndent[0])))))
		"""
		if not noAlign and get_report("alignments"):
			textAlign = formatField.get("text-align")
			if textAlign and get_method_alignment(textAlign) == CHOICE_spacing and textAlign not in ["start", "left"]:
				textAlign = normalizeTextAlign(textAlign)
				pct = {
					"justified": 0.25,
					"center": 0.5,
					"right": 0.75,
				}
				displaySize = braille.handler.displaySize
				sizeBrailleCells = len(self.brailleCells) - 1
				start = None
				if textAlign in ["center", "right"] and displaySize - 1 > sizeBrailleCells:
					if textAlign == "center":
						start = int((displaySize - sizeBrailleCells) / 2)
					else:
						start = displaySize - sizeBrailleCells
				elif textAlign == "justified":
					start = 3
				elif textAlign in pct:
					start = int(pct[textAlign] *
								braille.handler.displaySize) - 1
				else:
					log.error(f"Unknown text-align {textAlign}")
				if start is not None:
					s = "⠀" * start
					postReplacements.append(
						regionhelper.BrailleCellReplacement(start=0, insertBefore=s))
		if postReplacements:
			regionhelper.replaceBrailleCells(self, postReplacements)
		if self.brlex_typeforms:
			cell_masks_by_raw_pos = self.brlex_typeforms
			active_cell_mask = 0
			for raw_pos in range(len(self.rawText)):
				if raw_pos in cell_masks_by_raw_pos:
					active_cell_mask = cell_masks_by_raw_pos[raw_pos]
				if active_cell_mask:
					start_braille, end_braille = regionhelper.getBraillePosFromRawPos(self, raw_pos)
					for braille_pos in range(start_braille, end_braille + 1):
						self.brailleCells[braille_pos] |= active_cell_mask

	if s == "addTextWithFields":
		return addTextWithFields_edit
	if s == "update":
		return update
	if s == "_getTypeformFromFormatField":
		return _getTypeformFromFormatField


_tags = {}


def load_tags():
	global _tags
	tags = conf["tags"].copy()
	for k, v in tags.items():
		if len(v.split(TAG_SEPARATOR)) == 2:
			v_ = v.split(TAG_SEPARATOR)
			_tags[k] = TAG_FORMATTING(v_[0], v_[1])


def save_tags(newTags):
	tags = {k: f"{v.start}{TAG_SEPARATOR}{v.end}" for k, v in newTags.items()}
	conf["tags"] = tags


def get_tags(k, tags=None):
	if not tags:
		tags = _tags
	if not tags:
		return None
	if k in tags:
		return tags[k]
	if ':' in k and k.split(':')[0] in tags:
		return tags[k.split(':')[0]]
	return None


def normalizeTextAlign(desc):
	if not desc or not isinstance(desc, str):
		return None
	desc = desc.replace("-moz-", "").replace("justify", "justified")
	return desc


def get_method_alignment(desc):
	sect = conf["alignments"]
	if desc in sect:
		return sect[desc]
	return None


class ManageMethods(wx.Dialog):
	def __init__(
			self,
			parent=None,
			# Translators: title of a dialog.
			title=_("Formatting Method"),
	):
		super().__init__(parent, title=title)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		choices = list(CHOICES_LABELS.values())
		self.spellingErrors = sHelper.addLabeledControl(
			_("&Spelling errors:"), wx.Choice, choices=choices
		)
		self.spellingErrors.SetSelection(
			self.getItemToSelect("invalid-spelling"))
		self.grammarError = sHelper.addLabeledControl(
			_("&Grammar errors:"), wx.Choice, choices=choices
		)
		self.grammarError.SetSelection(self.getItemToSelect("invalid-grammar"))
		self.bold = sHelper.addLabeledControl(
			_("B&old:"), wx.Choice, choices=choices
		)
		self.bold.SetSelection(self.getItemToSelect("bold"))
		self.italic = sHelper.addLabeledControl(
			_("&Italic:"), wx.Choice, choices=choices
		)
		self.italic.SetSelection(self.getItemToSelect("italic"))
		self.underline = sHelper.addLabeledControl(
			_("&Underline:"), wx.Choice, choices=choices
		)
		self.underline.SetSelection(self.getItemToSelect("underline"))
		self.strikethrough = sHelper.addLabeledControl(
			_("Strike&through:"), wx.Choice, choices=choices
		)
		self.strikethrough.SetSelection(self.getItemToSelect("strikethrough"))
		self.strong = sHelper.addLabeledControl(
			_("Strong e&mphasis:"), wx.Choice, choices=choices
		)
		self.strong.SetSelection(self.getItemToSelect("strong"))
		self.emphasised = sHelper.addLabeledControl(
			_("E&mphasised text:"), wx.Choice, choices=choices
		)
		self.emphasised.SetSelection(self.getItemToSelect("emphasised"))
		self.marked = sHelper.addLabeledControl(
			_("Mar&ked (highlighted):"), wx.Choice, choices=choices
		)
		self.marked.SetSelection(self.getItemToSelect("marked"))
		self.sub = sHelper.addLabeledControl(
			_("Su&bscripts:"), wx.Choice, choices=choices
		)
		self.sub.SetSelection(self.getItemToSelect("text-position:sub"))
		self.super = sHelper.addLabeledControl(
			_("Su&perscripts:"), wx.Choice, choices=choices
		)
		self.super.SetSelection(self.getItemToSelect("text-position:super"))

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		sHelper.addItem(bHelper)
		sHelper.addDialogDismissButtons(
			self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.spellingErrors.SetFocus()

	@staticmethod
	def getItemToSelect(attribute):
		try:
			idx = list(CHOICES_LABELS.keys()).index(
				conf["methods"][attribute]
			)
		except BaseException as err:
			log.error(err)
			idx = 0
		return idx

	def onOk(self, evt):
		conf["methods"]["invalid-spelling"] = list(
			CHOICES_LABELS.keys()
		)[self.spellingErrors.GetSelection()]
		conf["methods"]["invalid-grammar"] = list(
			CHOICES_LABELS.keys()
		)[self.grammarError.GetSelection()]
		conf["methods"]["bold"] = list(
			CHOICES_LABELS.keys()
		)[self.bold.GetSelection()]
		conf["methods"]["italic"] = list(
			CHOICES_LABELS.keys()
		)[self.italic.GetSelection()]
		conf["methods"]["underline"] = list(
			CHOICES_LABELS.keys()
		)[self.underline.GetSelection()]
		conf["methods"]["strikethrough"] = list(
			CHOICES_LABELS.keys()
		)[self.strikethrough.GetSelection()]
		conf["methods"]["strong"] = list(
			CHOICES_LABELS.keys()
		)[self.strong.GetSelection()]
		conf["methods"]["emphasised"] = list(
			CHOICES_LABELS.keys()
		)[self.emphasised.GetSelection()]
		conf["methods"]["marked"] = list(
			CHOICES_LABELS.keys()
		)[self.marked.GetSelection()]
		conf["methods"]["text-position:sub"] = list(
			CHOICES_LABELS.keys()
		)[self.sub.GetSelection()]
		conf["methods"]["text-position:super"] = list(
			CHOICES_LABELS.keys()
		)[self.super.GetSelection()]
		self.Destroy()


class ManageTags(wx.Dialog):

	def __init__(
			self,
			parent=None,
			# Translators: title of a dialog.
			title=_("Customize formatting tags"),
	):
		self.tags = _tags.copy()
		super().__init__(parent, title=title)
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		choices = list(LABELS_FORMATTING.values())
		self.formatting = sHelper.addLabeledControl(
			_("&Formatting"), wx.Choice, choices=choices
		)
		self.formatting.SetSelection(0)
		self.formatting.Bind(wx.EVT_CHOICE, self.onFormatting)
		self.startTag = sHelper.addLabeledControl(_("&Start tag"), wx.TextCtrl)
		self.startTag.Bind(wx.EVT_TEXT, self.onTags)

		self.endTag = sHelper.addLabeledControl(_("&End tag"), wx.TextCtrl)
		self.endTag.Bind(wx.EVT_TEXT, self.onTags)
		self.onFormatting()

		sHelper.addDialogDismissButtons(
			self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.formatting.SetFocus()

	def get_key_attribute(self):
		l = list(LABELS_FORMATTING.keys())
		selection = self.formatting.GetSelection()
		return l[selection] if 0 <= selection < len(l) else 0

	def onTags(self, evt=None):
		k = self.get_key_attribute()
		self.tags[k] = self.startTag.GetValue()
		tag = TAG_FORMATTING(
			self.startTag.GetValue(),
			self.endTag.GetValue()
		)
		self.tags[k] = tag

	def onFormatting(self, evt=None):
		k = self.get_key_attribute()
		tag = get_tags(k, self.tags)
		self.startTag.SetValue(tag.start)
		self.endTag.SetValue(tag.end)
		if "text-align" in k:
			self.endTag.Disable()
		else:
			self.endTag.Enable()

	def onOk(self, evt):
		save_tags(self.tags)
		load_tags()
		self.Destroy()


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	# Translators: title of a dialog.
	title = N_("Document formatting")
	panelDescription = _(
		"Each row: follow NVDA’s Document formatting settings, always show this information in braille (see Methods and Tags), or turn it off. “Follow NVDA” is not limited to speech; it uses the same report toggles as NVDA’s Document formatting dialog."
	)

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		sHelper.addItem(wx.StaticText(self, label=self.panelDescription))

		label = _("Plain text mode (disable all text formatting)")
		self.plainText = sHelper.addItem(
			wx.CheckBox(self, label=label))
		self.plainText.SetValue(conf["plainText"])

		label = _("Process formatting line per line")
		self.processLinePerLine = sHelper.addItem(
			wx.CheckBox(self, label=label))
		self.processLinePerLine.SetValue(conf["processLinePerLine"])

		keys = list(LABELS_STATES.keys())
		choices = list(LABELS_STATES.values())
		self.dynamic_options = []
		for key, val in LABELS_REPORTS.items():
			self.dynamic_options.append(sHelper.addLabeledControl(
				_("{label}:").format(label=val),
				wx.Choice,
				choices=choices
			))
			self.dynamic_options[-1].SetSelection(keys.index(
				get_report(key, 0)
			))

		label = _("Cell &formula (Excel only for now)")
		self.cellFormula = sHelper.addItem(wx.CheckBox(self, label=label))
		self.cellFormula.SetValue(conf["cellFormula"])

		label = _("Le&vel of items in a nested list")
		self.levelItemsList = sHelper.addItem(wx.CheckBox(self, label=label))
		self.levelItemsList.SetValue(conf["lists"]["showLevelItem"])

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.methodsBtn = bHelper.addButton(
			self, label=_("Met&hods...")
		)
		self.methodsBtn.Bind(wx.EVT_BUTTON, self.onMethodsBtn)
		self.tagsBtn = bHelper.addButton(self, label="Tag&s...")
		self.tagsBtn.Bind(wx.EVT_BUTTON, self.onTagsBtn)
		sHelper.addItem(bHelper)

	def onMethodsBtn(self, evt=None):
		manageMethods = ManageMethods(self)
		manageMethods.ShowModal()
		self.methodsBtn.SetFocus()

	def onTagsBtn(self, evt=None):
		manageTags = ManageTags(self)
		manageTags.ShowModal()
		self.tagsBtn.SetFocus()

	def postInit(self):
		self.reportFontAttributes.SetFocus()

	def onSave(self):
		conf["plainText"] = self.plainText.IsChecked()
		conf["processLinePerLine"] = self.processLinePerLine.IsChecked()
		conf["lists"]["showLevelItem"] = self.levelItemsList.IsChecked()

		for i, key in enumerate(LABELS_REPORTS.keys()):
			val = list(LABELS_STATES.keys())[
				self.dynamic_options[i].GetSelection()
			]
			set_report(key, val)
		conf["cellFormula"] = self.cellFormula.IsChecked()
