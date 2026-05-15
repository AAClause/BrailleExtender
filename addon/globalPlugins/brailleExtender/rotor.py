# coding: utf-8
# Rotor navigation for BrailleExtender
# Part of Braille Extender addon for NVDA
# Copyright (C) 2016-2023 André-Abush Clause, released under GPL.

from enum import StrEnum, auto
from typing import Any, Dict, List, Optional, Sequence, Tuple, Final

import addonHandler
import api
import config
import treeInterceptorHandler
from logHandler import log


class RotorId(StrEnum):
	default = auto()
	moveInText = auto()
	textSelection = auto()
	object = auto()
	review = auto()
	Link = auto()
	UnvisitedLink = auto()
	VisitedLink = auto()
	Landmark = auto()
	Heading = auto()
	Heading1 = auto()
	Heading2 = auto()
	Heading3 = auto()
	Heading4 = auto()
	Heading5 = auto()
	Heading6 = auto()
	List = auto()
	ListItem = auto()
	Graphic = auto()
	BlockQuote = auto()
	Button = auto()
	FormField = auto()
	Edit = auto()
	RadioButton = auto()
	ComboBox = auto()
	CheckBox = auto()
	ToggleButton = auto()
	NotLinkBlock = auto()
	Frame = auto()
	Separator = auto()
	EmbeddedObject = auto()
	Annotation = auto()
	Error = auto()
	Article = auto()
	Grouping = auto()
	Tab = auto()
	Figure = auto()
	MenuItem = auto()
	ProgressBar = auto()
	Math = auto()
	TextParagraph = auto()
	VerticalParagraph = auto()
	SameStyle = auto()
	DifferentStyle = auto()
	Reference = auto()
	Table = auto()
	moveInTable = auto()
	prefOutputTable = auto()
	prefInputTable = auto()


addonHandler.initTranslation()

ROTOR_LABELS: Dict[str, str] = {
	RotorId.default.value: _("Default"),
	RotorId.moveInText.value: _("Text navigation"),
	RotorId.textSelection.value: _("Selection navigation"),
	RotorId.object.value: _("Object navigation"),
	RotorId.review.value: _("Review cursor"),
	RotorId.Link.value: _("Links"),
	RotorId.UnvisitedLink.value: _("Unvisited links"),
	RotorId.VisitedLink.value: _("Visited links"),
	RotorId.Landmark.value: _("Landmarks"),
	RotorId.Heading.value: _("Headings"),
	RotorId.Heading1.value: _("Heading level 1"),
	RotorId.Heading2.value: _("Heading level 2"),
	RotorId.Heading3.value: _("Heading level 3"),
	RotorId.Heading4.value: _("Heading level 4"),
	RotorId.Heading5.value: _("Heading level 5"),
	RotorId.Heading6.value: _("Heading level 6"),
	RotorId.List.value: _("Lists"),
	RotorId.ListItem.value: _("List items"),
	RotorId.Graphic.value: _("Images and graphics"),
	RotorId.BlockQuote.value: _("Quotations"),
	RotorId.Button.value: _("Buttons"),
	RotorId.FormField.value: _("Form fields"),
	RotorId.Edit.value: _("Edit fields"),
	RotorId.RadioButton.value: _("Radio buttons"),
	RotorId.ComboBox.value: _("Combo boxes"),
	RotorId.CheckBox.value: _("Check boxes"),
	RotorId.ToggleButton.value: _("Toggle buttons"),
	RotorId.NotLinkBlock.value: _("Text blocks (not links)"),
	RotorId.Frame.value: _("Frames"),
	RotorId.Separator.value: _("Separators"),
	RotorId.EmbeddedObject.value: _("Embedded objects"),
	RotorId.Annotation.value: _("Annotations"),
	RotorId.Error.value: _("Spelling and grammar"),
	RotorId.Article.value: _("Articles"),
	RotorId.Grouping.value: _("Groupings"),
	RotorId.Tab.value: _("Tabs"),
	RotorId.Figure.value: _("Figures"),
	RotorId.MenuItem.value: _("Menu items"),
	RotorId.ProgressBar.value: _("Progress bars"),
	RotorId.Math.value: _("Math content"),
	RotorId.TextParagraph.value: _("Paragraphs"),
	RotorId.VerticalParagraph.value: _("Vertical text"),
	RotorId.SameStyle.value: _("Same text formatting (font, emphasis, …)"),
	RotorId.DifferentStyle.value: _("Formatting changes"),
	RotorId.Reference.value: _("References"),
	RotorId.Table.value: _("Tables"),
	RotorId.moveInTable.value: _("Table navigation"),
	RotorId.prefOutputTable.value: _("Output braille tables"),
	RotorId.prefInputTable.value: _("Input braille tables"),
}

ROTOR_IDS: Tuple[str, ...] = tuple(m.value for m in RotorId)

_DEFAULT_ORDER_MEMBERS: Final[Tuple[RotorId, ...]] = (
	RotorId.default,
	RotorId.moveInText,
	RotorId.textSelection,
	RotorId.object,
	RotorId.review,
	RotorId.Link,
	RotorId.Landmark,
	RotorId.Heading,
	RotorId.Error,
	RotorId.Table,
	RotorId.moveInTable,
)
DEFAULT_MASTER_ORDER: Tuple[str, ...] = tuple(m.value for m in _DEFAULT_ORDER_MEMBERS)
DEFAULT_ENABLED_ROTOR_IDS: frozenset[str] = frozenset(DEFAULT_MASTER_ORDER)

FULL_ROTOR_GESTURE_IDS: frozenset[str] = frozenset(
	m.value
	for m in {
		RotorId.object,
		RotorId.review,
		RotorId.textSelection,
		RotorId.moveInText,
		RotorId.moveInTable,
	}
)

# Rotor slots that never use browse quick nav (no document probe).
_NO_QUICKNAV_PROBE_IDS: frozenset[str] = frozenset(
	m.value
	for m in (
		RotorId.default,
		RotorId.moveInText,
		RotorId.textSelection,
		RotorId.object,
		RotorId.review,
		RotorId.moveInTable,
		RotorId.prefOutputTable,
		RotorId.prefInputTable,
	)
)

# Browse quick nav entries we treat as always supported without calling iterators (NVDA-specific logic).
_SKIP_ITER_PROBE_IDS: frozenset[str] = frozenset(
	(m.value for m in (RotorId.TextParagraph, RotorId.VerticalParagraph))
)

# No iterator work: non-browse rotor slots + paragraph quick nav (handled elsewhere in NVDA).
_NO_DOC_ITER_PROBE_IDS: frozenset[str] = frozenset(_NO_QUICKNAV_PROBE_IDS | _SKIP_ITER_PROBE_IDS)

# RotorId StrEnum values are lowercased; NVDA browseMode.addQuickNav uses camelCase itemType strings.
_NVDA_QUICKNAV_ITEM_TYPES: Dict[str, str] = {
	"visitedlink": "visitedLink",
	"unvisitedlink": "unvisitedLink",
	"formfield": "formField",
	"listitem": "listItem",
	"radiobutton": "radioButton",
	"combobox": "comboBox",
	"checkbox": "checkBox",
	"blockquote": "blockQuote",
	"notlinkblock": "notLinkBlock",
	"embeddedobject": "embeddedObject",
	"menuitem": "menuItem",
	"progressbar": "progressBar",
	"togglebutton": "toggleButton",
	"textparagraph": "textParagraph",
	"verticalparagraph": "verticalParagraph",
	"samestyle": "sameStyle",
	"differentstyle": "differentStyle",
}


def nvda_quicknav_item_type(rotor_value: str) -> str:
	return _NVDA_QUICKNAV_ITEM_TYPES.get(rotor_value, rotor_value)


def browse_mode_script_attr(direction: str, rotor_id: RotorId | str) -> str:
	v = rotor_id.value if isinstance(rotor_id, RotorId) else str(rotor_id)
	item = nvda_quicknav_item_type(v)
	suffix = item[0].upper() + item[1:] if item else item
	return "script_%s%s" % (direction, suffix)


_bmti: Any = False  # False = unset, None = import failed, else BrowseModeTreeInterceptor class
_Movement_NEXT: Any = False  # False = unset, None = unavailable, else enum value


def _bmti_cls():
	global _bmti
	if _bmti is False:
		try:
			from browseMode import BrowseModeTreeInterceptor as B

			_bmti = B
		except ImportError:
			_bmti = None
	return _bmti


def _movement_next():
	global _Movement_NEXT
	if _Movement_NEXT is False:
		try:
			import documentBase

			_Movement_NEXT = documentBase._Movement.NEXT
		except Exception:
			_Movement_NEXT = None
	return _Movement_NEXT


def _probe_iter_text_style(ti, item: str, info):
	"""Advance one step like browseMode._quickNavScript for sameStyle / differentStyle.

	NVDA passes the string 'next' from _quickNavScript into _iterTextStyle (see browseMode.py).
	"""
	try:
		gen = ti._iterTextStyle(item, "next", info)
	except TypeError:
		mv = _movement_next()
		if mv is None:
			raise
		gen = ti._iterTextStyle(item, mv, info)
	return next(gen)


def _text_style_nav_notimplemented(ti, kind: str) -> bool:
	"""True when this tree interceptor rejects text-style quick nav (e.g. Word #16569).

	Must run even when browse mode is not active (``passThrough`` / not ``isReady``): otherwise the
	rotor would list same/different style while NVDA still reports *Not supported in this document*.
	"""
	cls = _bmti_cls()
	if not ti or not cls or not isinstance(ti, cls):
		return False
	try:
		info = ti.selection
	except (RuntimeError, AttributeError):
		info = None
	try:
		_probe_iter_text_style(ti, kind, info)
	except NotImplementedError:
		return True
	except Exception:
		return False
	return False


def _browse_probe_state(ti) -> tuple:
	"""Hashable browse state for cache keys. ``('a', ...)`` means iterator probes apply."""
	if ti is None:
		return ("0",)
	cls = _bmti_cls()
	if not cls or not isinstance(ti, cls):
		return ("n", id(ti))
	ready = bool(getattr(ti, "isReady", False))
	pt = bool(getattr(ti, "passThrough", False))
	if not ready or pt:
		return ("i", id(ti), ready, pt)
	return ("a", id(ti), ready, pt)


def resolve_document_tree_interceptor(obj):
	"""Resolve the browse/document tree interceptor NVDA would use for quick nav.

	Microsoft Word with UI Automation sets ``shouldCreateTreeInterceptor = False``; NVDA then
	relies on ``getTreeInterceptor`` / ``update(..., force=True)`` so a ``WordBrowseModeDocument``
	can exist while ``obj.treeInterceptor`` is still unset. Without this, rotor quick nav falls
	back to *Not available here* because ``getattr(ti, script_…)`` is never found.

	``update(..., force=True)`` is only used when the focus object disables automatic TI creation.
	Calling it for normal browsers (Firefox / Chromium) would bypass NVDA's
	``enableOnPageLoad`` / browse-mode guards and can load virtual buffers too early.
	"""
	if obj is None:
		return None
	ti = getattr(obj, "treeInterceptor", None)
	if ti is not None:
		return ti
	try:
		ti = treeInterceptorHandler.getTreeInterceptor(obj)
	except AttributeError:
		ti = None
	if ti is not None:
		return ti
	ti = treeInterceptorHandler.update(obj)
	if ti is not None:
		return ti
	if not getattr(obj, "shouldCreateTreeInterceptor", True):
		return treeInterceptorHandler.update(obj, force=True)
	return None


def _tree_interceptor_for_quicknav_probe():
	return resolve_document_tree_interceptor(api.getFocusObject())


def _iter_probe_quick_nav(ti, rotor_id_str: str) -> bool:
	"""Run one NVDA quick-nav iterator step; False only on NotImplementedError."""
	item = nvda_quicknav_item_type(rotor_id_str)
	try:
		info = ti.selection
	except (RuntimeError, AttributeError):
		return True
	try:
		if item == "notLinkBlock":
			next(ti._iterNotLinkBlock("next", info))
		elif item in ("sameStyle", "differentStyle"):
			_probe_iter_text_style(ti, item, info)
		else:
			next(ti._iterNodesByType(item, "next", info))
	except NotImplementedError:
		return False
	except StopIteration:
		return True
	except Exception:
		return True
	return True


_support_state: Optional[tuple] = None
_support_map: Dict[str, bool] = {}


def _support_reset_if_state_changed(st: tuple) -> None:
	global _support_state, _support_map
	if st != _support_state:
		_support_state = st
		_support_map.clear()


def _doc_support_for_rotor(ti, st: tuple, rotor_id_str: str) -> bool:
	if rotor_id_str in _NO_DOC_ITER_PROBE_IDS:
		return True
	_support_reset_if_state_changed(st)
	if rotor_id_str not in _support_map:
		_support_map[rotor_id_str] = _iter_probe_quick_nav(ti, rotor_id_str)
	return _support_map[rotor_id_str]


def quick_nav_supported_in_document(ti, rotor_id_str: str) -> bool:
	"""False when NVDA browse mode would report this quick nav as unsupported (e.g. same-style in Word)."""
	if rotor_id_str in _NO_DOC_ITER_PROBE_IDS:
		return True
	if ti is None:
		return True
	item = nvda_quicknav_item_type(rotor_id_str)
	st = _browse_probe_state(ti)
	# sameStyle / differentStyle: Word rejects in _iterTextStyle even when passThrough is on;
	# NVDA's _quickNavScript always hits _iterTextStyle, so probe whenever we have a browse TI.
	if item in ("sameStyle", "differentStyle"):
		if st[0] == "a":
			return _doc_support_for_rotor(ti, st, rotor_id_str)
		return not _text_style_nav_notimplemented(ti, item)
	if st[0] != "a":
		return True
	return _doc_support_for_rotor(ti, st, rotor_id_str)


rotorItem = 0
rotorRange = 0
lastRotorItemIdInVD: Optional[str] = None
lastRotorItemInVDSaved = True
_active_sequence: List[Tuple[str, str]] = []
_seq_cache_key: Optional[tuple] = None


def clear_rotor_sequence_caches() -> None:
	"""Drop cached active sequence / probe map (e.g. after rotor config reload)."""
	global _seq_cache_key, _support_state, _support_map
	_seq_cache_key = None
	_support_state = None
	_support_map.clear()


def _rotor_conf():
	return config.conf["brailleExtender"]["rotor"]


def _parse_csv(s: str) -> List[str]:
	if not s or not str(s).strip():
		return []
	return [x.strip() for x in str(s).replace(", ", ",").split(",") if x.strip()]


def _merge_order_with_catalog(saved: Sequence[str]) -> List[str]:
	known = set(ROTOR_IDS)
	out = [x for x in saved if x in known]
	for id_ in ROTOR_IDS:
		if id_ not in out:
			out.append(id_)
	return out


def _order_list_from_raw(order_raw: str) -> List[str]:
	s = str(order_raw).strip() if order_raw is not None else ""
	parsed = _parse_csv(s) if s else []
	if not parsed:
		return _merge_order_with_catalog(list(DEFAULT_MASTER_ORDER))
	return _merge_order_with_catalog(parsed)


def _enabled_set_from_raw(enabled_raw: str) -> frozenset[str]:
	s = str(enabled_raw).strip() if enabled_raw is not None else ""
	parsed = _parse_csv(s) if s else []
	if not parsed:
		return DEFAULT_ENABLED_ROTOR_IDS
	known = set(ROTOR_IDS)
	return frozenset(x for x in parsed if x in known)


def master_order_from_config() -> List[str]:
	return _order_list_from_raw(str(_rotor_conf().get("itemOrder", "") or ""))


def enabled_ids_from_config() -> frozenset[str]:
	return _enabled_set_from_raw(str(_rotor_conf().get("itemEnabled", "") or ""))


def refresh_active_sequence() -> None:
	global _active_sequence, _seq_cache_key
	conf = _rotor_conf()
	ors = str(conf.get("itemOrder", "") or "")
	ens = str(conf.get("itemEnabled", "") or "")
	ti = _tree_interceptor_for_quicknav_probe()
	st = _browse_probe_state(ti)
	full_key = (ors, ens, st)
	if full_key == _seq_cache_key and _active_sequence:
		return
	_seq_cache_key = full_key
	order = _order_list_from_raw(ors)
	enabled = _enabled_set_from_raw(ens)
	seq: List[Tuple[str, str]] = []
	for id_ in order:
		if id_ not in enabled:
			continue
		if ti is not None and not quick_nav_supported_in_document(ti, id_):
			continue
		seq.append((id_, ROTOR_LABELS[id_]))
	if not seq:
		log.warning("Rotor: no items active; forcing Default")
		dv = RotorId.default.value
		seq = [(dv, ROTOR_LABELS[dv])]
	_active_sequence = seq


def reload_from_config() -> None:
	clear_rotor_sequence_caches()
	refresh_active_sequence()


def apply_focus_context(is_virtual_buffer: bool, plugin) -> None:
	global rotorItem, lastRotorItemIdInVD, lastRotorItemInVDSaved, _seq_cache_key
	# Read sequence before busting caches (active_sequence() skips refresh if list non-empty).
	if not lastRotorItemInVDSaved and not is_virtual_buffer:
		seq = active_sequence()
		if seq and 0 <= rotorItem < len(seq):
			lastRotorItemIdInVD = seq[rotorItem][0]
		lastRotorItemInVDSaved = True
		rotorItem = 0
	_seq_cache_key = None
	will_restore = False
	restore_vd: Optional[str] = None
	if lastRotorItemInVDSaved and is_virtual_buffer:
		will_restore = True
		restore_vd = lastRotorItemIdInVD
		lastRotorItemInVDSaved = False
	refresh_active_sequence()
	if will_restore:
		if restore_vd:
			ids = [p[0] for p in _active_sequence]
			rotorItem = ids.index(restore_vd) if restore_vd in ids else 0
		else:
			rotorItem = 0
	clamp_rotor_index()
	plugin.bindRotorGES()


def active_sequence() -> List[Tuple[str, str]]:
	if not _active_sequence:
		refresh_active_sequence()
	return _active_sequence


def current_rotor_id() -> RotorId:
	seq = active_sequence()
	if not seq:
		return RotorId.default
	raw = seq[min(rotorItem, len(seq) - 1)][0]
	try:
		return RotorId(raw)
	except ValueError:
		log.warning("Rotor: unknown id %r, falling back to default", raw)
		return RotorId.default


def current_rotor_label() -> str:
	seq = active_sequence()
	if not seq:
		return ROTOR_LABELS[RotorId.default.value]
	return seq[min(rotorItem, len(seq) - 1)][1]


def clamp_rotor_index() -> None:
	global rotorItem
	seq = active_sequence()
	if not seq:
		rotorItem = 0
		return
	if rotorItem >= len(seq):
		rotorItem = 0
	elif rotorItem < 0:
		rotorItem = len(seq) - 1


def advance_rotor(delta: int) -> str:
	global rotorItem
	preserve_id: Optional[str] = None
	if _active_sequence and 0 <= rotorItem < len(_active_sequence):
		preserve_id = _active_sequence[rotorItem][0]
	refresh_active_sequence()
	seq = _active_sequence if _active_sequence else active_sequence()
	if not seq:
		return ROTOR_LABELS[RotorId.default.value]
	if preserve_id:
		ids = [p[0] for p in seq]
		if preserve_id in ids:
			rotorItem = ids.index(preserve_id)
		else:
			clamp_rotor_index()
	else:
		clamp_rotor_index()
	n = len(seq)
	rotorItem = (rotorItem + delta) % n
	return seq[rotorItem][1]


def should_bind_full_rotor_gestures(rotor_id: RotorId | str) -> bool:
	s = rotor_id.value if isinstance(rotor_id, RotorId) else str(rotor_id)
	return s in FULL_ROTOR_GESTURE_IDS


def format_config_order_and_enabled(order_ids: Sequence[str], checked: Sequence[bool]) -> Tuple[str, str]:
	order_ids = list(order_ids)
	checked = list(checked)
	dv = RotorId.default.value
	if dv in order_ids:
		i = order_ids.index(dv)
		while len(checked) <= i:
			checked.append(False)
		checked[i] = True
	enabled_in_order = [oid for oid, ok in zip(order_ids, checked) if ok]
	if not enabled_in_order:
		enabled_in_order = [RotorId.default.value]
	enabled_set = frozenset(enabled_in_order)
	order_str = ",".join(order_ids)
	enabled_str = ",".join(oid for oid in order_ids if oid in enabled_set)
	if not enabled_str:
		enabled_str = RotorId.default.value
	return order_str, enabled_str
