# brailleapi.py - Part of BrailleExtender addon for NVDA
# Copyright 2026 André-Abush CLAUSE, released under GPL.
"""NVDA braille API resolved once, for NVDA 2024.1 to 2027.x.

NVDA 2026.3 split ``braille.py`` into a package and ``brailleInput`` into ``braille.input``.
The old names still work through module ``__getattr__`` hooks, but each access logs a warning
with a stack trace, which is far too costly on braille hot paths. Module-level functions also
moved: region code now imports ``getFormatFieldBraille``/``getPropertiesBraille`` directly from
``braille.regions.properties``, so assigning them on the ``braille`` facade no longer changes
NVDA's behaviour.

Import symbols from here instead of ``braille.X`` / ``brailleInput.X``, and use
:func:`patch_module_function` to replace a braille module-level function wherever NVDA looks it
up. ``braille.handler`` is still a real attribute of ``braille`` and can be used directly.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

import braille
from logHandler import log


def resolve_symbol(name: str, *modules: str, fallback: Any = None, legacy: Any = braille) -> Any:
	"""Return ``name`` from the first of ``modules`` defining it, else from ``legacy``."""
	for moduleName in modules:
		try:
			module = importlib.import_module(moduleName)
		except ImportError:
			continue
		if name in vars(module):
			return vars(module)[name]
	if legacy is not None:
		value = getattr(legacy, name, None)
		if value is not None:
			return value
	return fallback


# Regions and buffers
Region = resolve_symbol("Region", "braille.regions.base")
TextRegion = resolve_symbol("TextRegion", "braille.regions.base")
TextInfoRegion = resolve_symbol("TextInfoRegion", "braille.regions.textInfo")
CursorManagerRegion = resolve_symbol("CursorManagerRegion", "braille.regions.textInfo")
NVDAObjectRegion = resolve_symbol("NVDAObjectRegion", "braille.regions.NVDAObject")
NVDAObjectHasUsefulText = resolve_symbol("NVDAObjectHasUsefulText", "braille.regions.NVDAObject")
getFocusRegions = resolve_symbol("getFocusRegions", "braille.regions.focus")
getFocusContextRegions = resolve_symbol("getFocusContextRegions", "braille.regions.focus")
BrailleBuffer = resolve_symbol("BrailleBuffer", "braille.buffers")
BrailleHandler = resolve_symbol("BrailleHandler", "braille.brailleHandler")

# Field/property presentation (originals; see patch_module_function to replace them)
getControlFieldBraille = resolve_symbol("getControlFieldBraille", "braille.regions.properties")
getFormatFieldBraille = resolve_symbol("getFormatFieldBraille", "braille.regions.properties")
getPropertiesBraille = resolve_symbol("getPropertiesBraille", "braille.regions.properties")

# Labels: the very dict objects NVDA uses, so in-place edits apply to NVDA too.
roleLabels = resolve_symbol("roleLabels", "braille.labels")
positiveStateLabels = resolve_symbol("positiveStateLabels", "braille.labels")
negativeStateLabels = resolve_symbol("negativeStateLabels", "braille.labels")
landmarkLabels = resolve_symbol("landmarkLabels", "braille.labels")

# Formatting markers (NVDA 2025.1+; ``None`` before)
fontAttributeFormattingMarkers = resolve_symbol("fontAttributeFormattingMarkers", "braille.formatting")
FormatTagDelimiter = resolve_symbol("FormatTagDelimiter", "braille.formatting")
getParagraphStartMarker = resolve_symbol("getParagraphStartMarker", "braille.formatting")
#: Private NVDA helper; not covered by NVDA's deprecation aliases, so ``braille`` lacks it in 2026.3+.
appendFormattingMarker = resolve_symbol("_appendFormattingMarker", "braille.formatting")

# Constants
TEXT_SEPARATOR = resolve_symbol("TEXT_SEPARATOR", "braille.constants", fallback=" ")
SELECTION_SHAPE = resolve_symbol("SELECTION_SHAPE", "braille.constants", fallback=0xC0)
INPUT_START_IND = resolve_symbol("INPUT_START_IND", "braille.constants", fallback="⣏")
INPUT_END_IND = resolve_symbol("INPUT_END_IND", "braille.constants", fallback=" ⣹")

# Displays
getDisplayList = resolve_symbol("getDisplayList", "braille.display")
#: Extension points: ``filter_displayDimensions`` exists from NVDA 2025.1 (``None`` before).
filter_displayDimensions = resolve_symbol("filter_displayDimensions", "braille.extensions")
filter_displaySize = resolve_symbol("filter_displaySize", "braille.extensions")


def _legacyBrailleInput():
	try:
		return importlib.import_module("brailleInput")
	except ImportError:
		return None


# Braille input (``braille.input`` since NVDA 2026.3, ``brailleInput`` before)
BrailleInputHandler = resolve_symbol(
	"BrailleInputHandler",
	"braille.input.inputHandler",
	legacy=_legacyBrailleInput(),
)
#: liblouis dotsIO marker for back-translation input; removed from ``brailleInput`` in 2026.3.
LOUIS_DOTS_IO_START = 0x8000

try:
	_brailleInputModule = importlib.import_module("braille.input")
except ImportError:
	_brailleInputModule = _legacyBrailleInput()


def get_braille_input_handler():
	"""The braille input handler (created by NVDA at start-up, so looked up on each call)."""
	return getattr(_brailleInputModule, "handler", None)


# Module-level function patching

_PATCH_MODULE_PREFIX = "braille"
#: name -> list of (module, previous value) replaced by :func:`patch_module_function`.
_functionPatches: dict[str, list[tuple[Any, Any]]] = {}


def _brailleModules() -> list[Any]:
	modules = []
	for moduleName, module in list(sys.modules.items()):
		if module is None:
			continue
		if moduleName == _PATCH_MODULE_PREFIX or moduleName.startswith(_PATCH_MODULE_PREFIX + "."):
			modules.append(module)
	return modules


def patch_module_function(name: str, replacement: Any) -> Any:
	"""Replace braille module-level function ``name`` everywhere NVDA references it.

	Every loaded ``braille`` (sub)module whose namespace holds the original function (defined or
	imported there) gets ``replacement``. On NVDA before 2026.3 that is the ``braille`` module
	itself. Returns the original function.
	"""
	original = globals().get(name)
	if original is None:
		raise AttributeError(f"unknown braille function {name!r}")
	if name in _functionPatches:
		return original
	replaced: list[tuple[Any, Any]] = []
	for module in _brailleModules():
		namespace = vars(module)
		if namespace.get(name) is original:
			replaced.append((module, original))
			setattr(module, name, replacement)
	if not replaced:
		log.warning("braille function %s not found in any braille module; not patched", name)
	_functionPatches[name] = replaced
	return original


def restore_module_function(name: str) -> None:
	"""Undo :func:`patch_module_function` for ``name``."""
	for module, original in _functionPatches.pop(name, []):
		setattr(module, name, original)
