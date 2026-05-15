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
	CHOICE_linePad,
	CHOICE_spacing,
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
_NVDA_MANAGED_CLASSIC_FONT_ATTRS: frozenset[str] = frozenset(("bold", "italic", "underline", "strikethrough"))
_NVDA_SEMANTIC_EMPHASIS_ATTRS: frozenset[str] = frozenset(("strong", "emphasised"))
_NVDA_SEMANTIC_MARK_ATTRS: frozenset[str] = frozenset(("marked",))

# Alignment method buckets (config string values).
_ALIGNMENT_PAD_METHODS: frozenset[str] = frozenset((CHOICE_linePad, CHOICE_spacing))
_ALIGNMENT_NO_BRLEX_OVERLAY: frozenset[str] = frozenset(
	(CHOICE_none, CHOICE_tags, CHOICE_linePad, CHOICE_spacing, CHOICE_liblouis)
)

CHOICES_LABELS = {
	CHOICE_none: _("nothing"),
	CHOICE_liblouis: _("hand over to Liblouis (defined in tables)"),
	CHOICE_dots78: _("dots 7 and 8"),
	CHOICE_dot7: _("dot 7"),
	CHOICE_dot8: _("dot 8"),
	CHOICE_tags: _("tags"),
}

# Alignment methods (Methods dialog). ``CHOICE_spacing`` is legacy; treated like ``CHOICE_linePad``. Liblouis is not used for alignment.
ALIGNMENT_METHOD_ORDER: tuple[str, ...] = (
	CHOICE_none,
	CHOICE_linePad,
	CHOICE_dot7,
	CHOICE_dot8,
	CHOICE_dots78,
	CHOICE_tags,
)
ALIGNMENT_METHOD_LABELS: dict[str, str] = {
	CHOICE_none: CHOICES_LABELS[CHOICE_none],
	CHOICE_linePad: _("Pad display line (blanks)"),
	CHOICE_dot7: CHOICES_LABELS[CHOICE_dot7],
	CHOICE_dot8: CHOICES_LABELS[CHOICE_dot8],
	CHOICE_dots78: CHOICES_LABELS[CHOICE_dots78],
	CHOICE_tags: CHOICES_LABELS[CHOICE_tags],
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
	"tableCellCoords": N_("Cell c&oordinates"),
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
			return config.conf["documentFormatting"][normalized_key]
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
		if "enabled" not in conf["reports"][k]:
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
	state_keys = list(LABELS_STATES.keys())
	cur_index = state_keys.index(cur)
	new_index = (cur_index + 1) % len(state_keys)
	set_report(report, state_keys[new_index])


def report_formatting(report):
	cur = get_report(report, 0)
	label_report = LABELS_REPORTS[report].replace("&", "")
	label_state = LABELS_STATES.get(cur)
	if not label_state:
		label_state = N_("unknown")
	ui.message(_("{}: {}").format(label_report, label_state))


def get_method(k):
	candidates = [k]
	if ":" in k:
		candidates.append(k.split(":", 1)[0])
	for e in candidates:
		if e in conf["methods"]:
			return conf["methods"][e]
	return CHOICE_none


def get_liblouis_typeform(attr_name: str) -> int:
	return _LIBLOUIS_FLAGS_BY_ATTR.get(attr_name, louis.plain_text)


def _or_braille_mask_on_cell_span(region: Any, start_b: int, end_b: int, mask: int) -> None:
	if not mask:
		return
	for bp in range(start_b, end_b + 1):
		region.brailleCells[bp] |= mask


def _or_braille_mask_across_raw_positions(region: Any, mask: int) -> None:
	if not mask or not getattr(region, "rawText", None):
		return
	for raw_pos in range(len(region.rawText)):
		sb, eb = regionhelper.getBraillePosFromRawPos(region, raw_pos)
		_or_braille_mask_on_cell_span(region, sb, eb, mask)


def decorator(fn, s):
	def _getTypeformFromFormatField(self, field, formatConfig=None):
		if formatConfig is None:
			formatConfig = {}
		spell_attrs_delegated_to_nvda = report_row_follows_nvda(
			"spellingErrors"
		) and format_config_indicates_spelling_braille(formatConfig)
		classic_font_attrs_delegated_to_nvda = report_row_follows_nvda(
			"fontAttributes"
		) and format_config_font_attributes_report_braille(formatConfig)
		semantic_emphasis_delegated_to_nvda = report_row_follows_nvda("emphasis") and bool(
			formatConfig.get("reportEmphasis", False)
		)
		semantic_highlight_delegated_to_nvda = report_row_follows_nvda("highlight") and bool(
			formatConfig.get("reportHighlight", False)
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
			if isinstance(field, textInfos.FieldCommand) and isinstance(field.field, textInfos.FormatField):
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
					s = (int(IA2Attributes["level"]) - 1) * 2 if IA2Attributes.get("level") else 0
					noAlign = True
					postReplacements.append(
						regionhelper.BrailleCellReplacement(start=0, insertBefore=("⠀" * s))
					)
		formatField = self.formatField
		if not noAlign and get_report("alignments"):
			textAlign = formatField.get("text-align")
			if (
				textAlign
				and alignment_uses_display_line_pad(textAlign)
				and textAlign not in ("start", "left")
			):
				textAlign_norm = normalizeTextAlign(textAlign) or textAlign
				displaySize = braille.handler.displaySize
				content_cells = len(self.brailleCells) - 1
				pad_len = alignment_display_line_pad_len(textAlign_norm, displaySize, content_cells)
				if pad_len > 0:
					postReplacements.append(
						regionhelper.BrailleCellReplacement(start=0, insertBefore=("⠀" * pad_len))
					)
		if postReplacements:
			regionhelper.replaceBrailleCells(self, postReplacements)
		if self.brlex_typeforms:
			cell_masks_by_raw_pos = self.brlex_typeforms
			active_cell_mask = 0
			for raw_pos in range(len(self.rawText)):
				if raw_pos in cell_masks_by_raw_pos:
					active_cell_mask = cell_masks_by_raw_pos[raw_pos]
				if active_cell_mask:
					sb, eb = regionhelper.getBraillePosFromRawPos(self, raw_pos)
					_or_braille_mask_on_cell_span(self, sb, eb, active_cell_mask)
		align_dots = alignment_dots_cell_mask(formatField.get("text-align"))
		if align_dots and not noAlign and get_report("alignments"):
			_or_braille_mask_across_raw_positions(self, align_dots)

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
	if ":" in k and k.split(":")[0] in tags:
		return tags[k.split(":")[0]]
	return None


def normalizeTextAlign(desc):
	if not desc or not isinstance(desc, str):
		return None
	desc = desc.replace("-moz-", "").replace("justify", "justified")
	return desc


def get_method_alignment(desc: str) -> str | None:
	sect = conf["alignments"]
	if desc not in sect:
		return None
	return sect[desc]


def alignment_config_side_key(text_align_raw: str | None) -> str | None:
	"""Map a ``text-align`` field value to ``alignments`` keys ``left`` / ``center`` / ``right`` / ``justified``."""
	if not text_align_raw or not isinstance(text_align_raw, str):
		return None
	al = (normalizeTextAlign(text_align_raw) or text_align_raw).lower()
	if al in ("start", "left"):
		return "left"
	if al in ("end", "right"):
		return "right"
	if al in ("center",):
		return "center"
	if al in ("justified", "distribute"):
		return "justified"
	return None


def _alignment_side_and_method(text_align_raw: str | None) -> tuple[str | None, str | None]:
	side = alignment_config_side_key(text_align_raw)
	if not side:
		return None, None
	return side, get_method_alignment(side)


def alignment_uses_display_line_pad(text_align_raw: str | None) -> bool:
	_, method = _alignment_side_and_method(text_align_raw)
	return bool(method) and method in _ALIGNMENT_PAD_METHODS


def alignment_dots_cell_mask(text_align_raw: str | None) -> int:
	_, method = _alignment_side_and_method(text_align_raw)
	if not method or method in _ALIGNMENT_NO_BRLEX_OVERLAY:
		return 0
	return int(BRLEX_CELL_MASK_BY_METHOD.get(method, 0))


def alignment_method_shows_format_tags(text_align_raw: str | None) -> bool:
	_, method = _alignment_side_and_method(text_align_raw)
	return method == CHOICE_tags


def alignment_display_line_pad_len(
	text_align: str,
	display_size: int,
	content_cells: int,
) -> int:
	"""How many leading blank cells to insert in pad alignment mode.

	``usable = display_size - 1`` reserves one cell (routing).

	When ``content_cells <= usable``, the whole line fits in the logical width: use classic
	block alignment (center / flush right / capped 25% lead for justified).

	When the line is longer than ``usable``, anchor the first content cell at a fixed fraction
	of ``usable`` (center ~50%, right ~75%, justified ~25%); NVDA scrolls the rest as usual.
	"""
	usable = max(0, display_size - 1)
	content_cells = max(0, content_cells)
	al = (normalizeTextAlign(text_align) or text_align or "").lower()
	if al in ("start", "left"):
		return 0
	if content_cells <= usable:
		if al == "center":
			return (usable - content_cells) // 2
		if al == "right":
			return usable - content_cells
		if al in ("justified", "distribute"):
			lead = (usable + 2) // 4
			return min(lead, usable - content_cells)
		return 0
	if al == "center":
		return usable // 2
	if al == "right":
		return (3 * usable + 2) // 4
	if al in ("justified", "distribute"):
		return (usable + 2) // 4
	return 0


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

		# Translators: Short help text at the top of the Formatting Method dialog.
		sHelper.addItem(
			wx.StaticText(
				self,
				label=_(
					"For each item, choose how it is shown in braille (nothing, Liblouis, dots 7–8, tags, …). "
					"For alignment, you can use nothing, pad the line with blanks, dots 7 / 8 / 7+8 on the line, or tags."
				),
			)
		)

		choices = list(CHOICES_LABELS.values())

		def add_group(title: str) -> gui.guiHelper.BoxSizerHelper:
			box = wx.StaticBox(self, label=title)
			boxSizer = wx.StaticBoxSizer(box, wx.VERTICAL)
			inner = gui.guiHelper.BoxSizerHelper(self, sizer=boxSizer)
			sHelper.addItem(boxSizer)
			return inner

		# --- Spelling and grammar ---
		gSpell = add_group(_("Spelling and grammar"))
		self.spellingErrors = gSpell.addLabeledControl(_("&Spelling errors:"), wx.Choice, choices=choices)
		self.spellingErrors.SetSelection(self.getItemToSelect("invalid-spelling"))
		self.grammarError = gSpell.addLabeledControl(_("&Grammar errors:"), wx.Choice, choices=choices)
		self.grammarError.SetSelection(self.getItemToSelect("invalid-grammar"))

		# --- Classic font attributes ---
		gFont = add_group(_("Font styling (bold, italic, …)"))
		self.bold = gFont.addLabeledControl(_("B&old:"), wx.Choice, choices=choices)
		self.bold.SetSelection(self.getItemToSelect("bold"))
		self.italic = gFont.addLabeledControl(_("&Italic:"), wx.Choice, choices=choices)
		self.italic.SetSelection(self.getItemToSelect("italic"))
		self.underline = gFont.addLabeledControl(_("&Underline:"), wx.Choice, choices=choices)
		self.underline.SetSelection(self.getItemToSelect("underline"))
		self.strikethrough = gFont.addLabeledControl(_("Strike&through:"), wx.Choice, choices=choices)
		self.strikethrough.SetSelection(self.getItemToSelect("strikethrough"))

		# --- Semantic emphasis / highlight ---
		gEm = add_group(_("Emphasis and highlighting"))
		self.strong = gEm.addLabeledControl(_("Strong e&mphasis:"), wx.Choice, choices=choices)
		self.strong.SetSelection(self.getItemToSelect("strong"))
		self.emphasised = gEm.addLabeledControl(_("E&mphasised text:"), wx.Choice, choices=choices)
		self.emphasised.SetSelection(self.getItemToSelect("emphasised"))
		self.marked = gEm.addLabeledControl(_("Mar&ked (highlighted):"), wx.Choice, choices=choices)
		self.marked.SetSelection(self.getItemToSelect("marked"))

		# --- Subscript / superscript ---
		gScript = add_group(_("Subscripts and superscripts"))
		self.sub = gScript.addLabeledControl(_("Su&bscripts:"), wx.Choice, choices=choices)
		self.sub.SetSelection(self.getItemToSelect("text-position:sub"))
		self.super = gScript.addLabeledControl(_("Su&perscripts:"), wx.Choice, choices=choices)
		self.super.SetSelection(self.getItemToSelect("text-position:super"))

		# --- Alignment (subset of methods) ---
		gAlign = add_group(_("Text alignment (braille)"))
		align_choices = [ALIGNMENT_METHOD_LABELS[k] for k in ALIGNMENT_METHOD_ORDER]
		self._align_controls: dict[str, wx.Choice] = {}
		for side, label in (
			("left", _("&Left / start:")),
			("center", _("C&entered:")),
			("right", _("&Right:")),
			("justified", _("&Justified:")),
		):
			ch = gAlign.addLabeledControl(label, wx.Choice, choices=align_choices)
			ch.SetSelection(ManageMethods._alignment_method_index(side))
			self._align_controls[side] = ch

		sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL | wx.EXPAND)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.spellingErrors.SetFocus()

	@staticmethod
	def _alignment_method_index(side: str) -> int:
		raw = conf["alignments"].get(side, CHOICE_tags)
		if raw == CHOICE_spacing:
			raw = CHOICE_linePad
		if raw not in ALIGNMENT_METHOD_ORDER:
			return ALIGNMENT_METHOD_ORDER.index(CHOICE_tags)
		return ALIGNMENT_METHOD_ORDER.index(raw)

	@staticmethod
	def getItemToSelect(attribute: str) -> int:
		try:
			return list(CHOICES_LABELS.keys()).index(conf["methods"].get(attribute, CHOICE_none))
		except ValueError:
			log.debugWarning("BrailleExtender: unknown formatting method %r", attribute)
			return 0

	def onOk(self, evt):
		method_keys = list(CHOICES_LABELS.keys())
		for attr, ctrl in (
			("invalid-spelling", self.spellingErrors),
			("invalid-grammar", self.grammarError),
			("bold", self.bold),
			("italic", self.italic),
			("underline", self.underline),
			("strikethrough", self.strikethrough),
			("strong", self.strong),
			("emphasised", self.emphasised),
			("marked", self.marked),
			("text-position:sub", self.sub),
			("text-position:super", self.super),
		):
			conf["methods"][attr] = method_keys[ctrl.GetSelection()]
		for side, ch in self._align_controls.items():
			conf["alignments"][side] = ALIGNMENT_METHOD_ORDER[ch.GetSelection()]
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
		self.formatting = sHelper.addLabeledControl(_("&Formatting"), wx.Choice, choices=choices)
		self.formatting.SetSelection(0)
		self.formatting.Bind(wx.EVT_CHOICE, self.onFormatting)
		self.startTag = sHelper.addLabeledControl(_("&Start tag"), wx.TextCtrl)
		self.startTag.Bind(wx.EVT_TEXT, self.onTags)

		self.endTag = sHelper.addLabeledControl(_("&End tag"), wx.TextCtrl)
		self.endTag.Bind(wx.EVT_TEXT, self.onTags)
		self.onFormatting()

		sHelper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		mainSizer.Add(sHelper.sizer, border=20, flag=wx.ALL)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		self.formatting.SetFocus()

	def get_key_attribute(self):
		formatting_keys = list(LABELS_FORMATTING.keys())
		selection = self.formatting.GetSelection()
		return formatting_keys[selection] if 0 <= selection < len(formatting_keys) else 0

	def onTags(self, evt=None):
		k = self.get_key_attribute()
		self.tags[k] = TAG_FORMATTING(self.startTag.GetValue(), self.endTag.GetValue())

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
		self.plainText = sHelper.addItem(wx.CheckBox(self, label=label))
		self.plainText.SetValue(conf["plainText"])

		label = _("Process formatting line per line")
		self.processLinePerLine = sHelper.addItem(wx.CheckBox(self, label=label))
		self.processLinePerLine.SetValue(conf["processLinePerLine"])

		keys = list(LABELS_STATES.keys())
		choices = list(LABELS_STATES.values())
		self.dynamic_options = []
		for key, val in LABELS_REPORTS.items():
			self.dynamic_options.append(
				sHelper.addLabeledControl(_("{label}:").format(label=val), wx.Choice, choices=choices)
			)
			self.dynamic_options[-1].SetSelection(keys.index(get_report(key, 0)))

		label = _("Cell &formula (Excel only for now)")
		self.cellFormula = sHelper.addItem(wx.CheckBox(self, label=label))
		self.cellFormula.SetValue(conf["cellFormula"])

		label = _("Le&vel of items in a nested list")
		self.levelItemsList = sHelper.addItem(wx.CheckBox(self, label=label))
		self.levelItemsList.SetValue(conf["lists"]["showLevelItem"])

		bHelper = gui.guiHelper.ButtonHelper(orientation=wx.HORIZONTAL)
		self.methodsBtn = bHelper.addButton(self, label=_("Met&hods..."))
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
		self.methodsBtn.SetFocus()

	def onSave(self):
		conf["plainText"] = self.plainText.IsChecked()
		conf["processLinePerLine"] = self.processLinePerLine.IsChecked()
		conf["lists"]["showLevelItem"] = self.levelItemsList.IsChecked()

		for i, key in enumerate(LABELS_REPORTS.keys()):
			val = list(LABELS_STATES.keys())[self.dynamic_options[i].GetSelection()]
			set_report(key, val)
		conf["cellFormula"] = self.cellFormula.IsChecked()
