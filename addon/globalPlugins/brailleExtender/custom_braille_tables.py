# coding: utf-8
# custom_braille_tables.py - Part of BrailleExtender addon for NVDA
# Copyright 2016-2026 André-Abush CLAUSE, released under GPL.
"""Manage user-defined braille tables via NVDA's brailleTables API (NVDA 2024.3+)."""

from __future__ import annotations

import json
import os
import shutil
from typing import Any

import addonHandler
import braille
import brailleInput
import brailleTables
import config
import globalVars
from logHandler import log

from .common import (
	NVDA_HAS_AUTOMATIC_BRAILLE_TABLES,
	NVDA_HAS_CUSTOM_BRAILLE_TABLES,
	POST_TABLE_NONE,
	configDir,
	default_braille_table_file_for_cur_language,
	parse_braille_table_list,
)

ACTIVE_INPUT_TABLE_KEY = "activeInputTable"
ACTIVE_OUTPUT_TABLE_KEY = "activeOutputTable"
# Empty string in active* keys means no custom table for that direction.
ACTIVE_TABLE_NONE = ""

addonHandler.initTranslation()

SOURCE_ID = "brailleExtender"
CONFIG_FILE_NAME = "brailleExtenderCustomTables.json"
TABLES_SUBDIR = "customBrailleTables"
# Extensions for tables registered in NVDA brailleTables (__tables.py): .utb, .ctb, and .tbl (e.g. kmr.tbl).
# Liblouis also ships .cti / .dis / .uti / .dic as includes or auxiliary files; those are not NVDA tables.
PRIMARY_LOUIS_EXTENSIONS = frozenset({".utb", ".ctb", ".tbl"})
ALLOWED_LOUIS_EXTENSIONS = PRIMARY_LOUIS_EXTENSIONS

# Minimal valid Liblouis table used when creating a table from scratch.
SCRATCH_TABLE_TEMPLATE = (
	"# Custom braille table created by Braille Extender.\n"
	"# Add Liblouis rules below, or uncomment the next line to include another table as a starting point.\n"
	"# include en-us-comp8.utb\n"
	"\n"
	"space \\s 0020\n"
)


def is_allowed_louis_extension(file_name: str) -> bool:
	"""True if the file name has a Liblouis-related extension we accept."""
	return os.path.splitext(file_name)[1].lower() in ALLOWED_LOUIS_EXTENSIONS


def is_primary_translation_table(file_name: str) -> bool:
	"""True for extensions NVDA registers as braille tables (.utb, .ctb, .tbl)."""
	return os.path.splitext(file_name)[1].lower() in PRIMARY_LOUIS_EXTENSIONS


def scratch_table_file_name(*, contracted: bool) -> str:
	"""Default file name for a new empty table (.ctb if contracted, else .utb)."""
	extension = ".ctb" if contracted else ".utb"
	return f"custom{extension}"


_config_path = os.path.join(globalVars.appArgs.configPath, CONFIG_FILE_NAME)
_tables_dir = os.path.join(configDir, TABLES_SUBDIR)


def is_supported() -> bool:
	"""True when NVDA exposes custom braille table registration (2024.3+)."""
	return NVDA_HAS_CUSTOM_BRAILLE_TABLES and hasattr(brailleTables, "addTable")


def get_active_custom_input_table() -> str:
	"""File name of the active custom input table, or empty if none."""
	active = config.conf["brailleExtender"].get(ACTIVE_INPUT_TABLE_KEY, "")
	if active and is_custom_table_configured(active):
		return active
	return ACTIVE_TABLE_NONE


def get_active_custom_output_table() -> str:
	"""File name of the active custom output table, or empty if none."""
	active = config.conf["brailleExtender"].get(ACTIVE_OUTPUT_TABLE_KEY, "")
	if active and is_custom_table_configured(active):
		return active
	return ACTIVE_TABLE_NONE


def iter_tables_to_register() -> set[str]:
	"""Custom table file names that should be registered with NVDA (active selections only)."""
	registered: set[str] = set()
	active_input = get_active_custom_input_table()
	if active_input:
		meta = load_config().get("tables", {}).get(active_input, {})
		if meta.get("input", True):
			registered.add(active_input)
	active_output = get_active_custom_output_table()
	if active_output:
		meta = load_config().get("tables", {}).get(active_output, {})
		if meta.get("output", True):
			registered.add(active_output)
	return registered


def build_active_table_choice_lists(*, for_input: bool) -> tuple[list[str], list[str]]:
	"""Return (file names, labels) for the active-table combo; first entry is None."""
	# Translators: no custom braille table selected for input or output.
	none_label = _("None")
	file_names = [ACTIVE_TABLE_NONE]
	labels = [none_label]
	for file_name, meta in list_entries():
		if for_input and not meta.get("input", True):
			continue
		if not for_input and not meta.get("output", True):
			continue
		file_names.append(file_name)
		display = str(meta.get("displayName", file_name))
		labels.append(f"{display} ({file_name})")
	return file_names, labels


def set_active_custom_input_table(file_name: str) -> None:
	"""Select the custom input table (empty string clears custom input)."""
	if file_name and not is_custom_table_configured(file_name):
		raise ValueError(file_name)
	config.conf["brailleExtender"][ACTIVE_INPUT_TABLE_KEY] = file_name or ACTIVE_TABLE_NONE
	config.conf["braille"]["inputTable"] = nvda_persisted_table_value(
		file_name or "auto",
		is_input=True,
	)


def set_active_custom_output_table(file_name: str) -> None:
	"""Select the custom output table (empty string clears custom output)."""
	if file_name and not is_custom_table_configured(file_name):
		raise ValueError(file_name)
	config.conf["brailleExtender"][ACTIVE_OUTPUT_TABLE_KEY] = file_name or ACTIVE_TABLE_NONE
	config.conf["braille"]["translationTable"] = nvda_persisted_table_value(
		file_name or "auto",
		is_input=False,
	)


def _apply_active_table_handlers() -> None:
	"""Apply the current active custom or NVDA table selection to braille handlers."""
	from .utils import apply_braille_input_table, apply_braille_output_table

	active_input = get_active_custom_input_table()
	active_output = get_active_custom_output_table()
	if active_input:
		apply_braille_input_table(active_input)
	else:
		nvda_input = config.conf["braille"]["inputTable"]
		apply_braille_input_table(nvda_input if nvda_input else "auto")
	if active_output:
		apply_braille_output_table(active_output)
	else:
		nvda_output = config.conf["braille"]["translationTable"]
		apply_braille_output_table(nvda_output if nvda_output else "auto")


def _migrate_legacy_custom_table_settings() -> None:
	"""Drop deprecated master toggle; clear active keys when it was off."""
	if not config.conf["brailleExtender"].get("useCustomBrailleTables", True):
		for key in (ACTIVE_INPUT_TABLE_KEY, ACTIVE_OUTPUT_TABLE_KEY):
			if is_custom_table_configured(config.conf["brailleExtender"].get(key, "")):
				config.conf["brailleExtender"][key] = ACTIVE_TABLE_NONE


def get_config_path() -> str:
	return _config_path


def get_tables_directory() -> str:
	return _tables_dir


def _ensure_storage() -> None:
	"""Create add-on config directories (does not write the JSON config file)."""
	os.makedirs(configDir, exist_ok=True)
	os.makedirs(_tables_dir, exist_ok=True)


def _empty_config() -> dict[str, Any]:
	return {"tables": {}}


def load_config() -> dict[str, Any]:
	"""Load custom table metadata; return an empty registry if the JSON file does not exist yet."""
	_ensure_storage()
	if not os.path.isfile(_config_path):
		return _empty_config()
	try:
		with open(_config_path, "r", encoding="utf-8") as config_file:
			data = json.load(config_file)
	except json.JSONDecodeError:
		log.warning("resetting invalid custom braille tables config", exc_info=True)
		data = _empty_config()
		save_config(data)
	except OSError:
		log.warning("could not read custom braille tables config", exc_info=True)
		data = _empty_config()
	if not isinstance(data.get("tables"), dict):
		data["tables"] = {}
	return data


def save_config(data: dict[str, Any]) -> None:
	_ensure_storage()
	with open(_config_path, "w", encoding="utf-8") as config_file:
		json.dump(data, config_file, indent=2, ensure_ascii=False)
		config_file.write("\n")


def list_entries() -> list[tuple[str, dict[str, Any]]]:
	"""Return (fileName, metadata) pairs in display-name order."""
	tables = load_config().get("tables", {})
	return sorted(
		tables.items(),
		key=lambda item: str(item[1].get("displayName", item[0])).lower(),
	)


def get_table_path(file_name: str) -> str:
	return os.path.join(_tables_dir, file_name)


def _unique_file_name(base_name: str) -> str:
	name, ext = os.path.splitext(base_name)
	if not ext:
		ext = ".utb"
	elif ext.lower() not in ALLOWED_LOUIS_EXTENSIONS:
		raise ValueError("unsupported table extension")
	candidate = f"{name}{ext}"
	counter = 1
	while os.path.exists(get_table_path(candidate)):
		candidate = f"{name}-{counter}{ext}"
		counter += 1
	return candidate


def _sanitize_file_name(file_name: str) -> str:
	file_name = os.path.basename(file_name)
	if not is_allowed_louis_extension(file_name):
		raise ValueError("unsupported table extension (use .utb, .ctb, or .tbl)")
	return file_name


def is_custom_table_configured(file_name: str) -> bool:
	"""True if the file name is listed in Braille Extender custom table metadata (JSON)."""
	return file_name in load_config().get("tables", {})


def nvda_persisted_table_value(table_id: str, *, is_input: bool) -> str:
	"""Return a table id safe for NVDA ``braille`` config without this add-on loaded."""
	if table_id == "auto":
		return "auto"
	if is_custom_table_configured(table_id):
		if NVDA_HAS_AUTOMATIC_BRAILLE_TABLES:
			return "auto"
		return default_braille_table_file_for_cur_language(is_input=is_input)
	return table_id


def get_effective_input_table_id() -> str:
	"""Logical input table for switching and UI (may be a custom table)."""
	active_custom = get_active_custom_input_table()
	if active_custom:
		return active_custom
	active = config.conf["brailleExtender"].get(ACTIVE_INPUT_TABLE_KEY, "")
	if active and not is_custom_table_configured(active):
		return active
	configured = config.conf["braille"]["inputTable"]
	return "auto" if configured == "auto" else configured


def get_effective_output_table_id() -> str:
	"""Logical output table for switching and UI (may be a custom table)."""
	active_custom = get_active_custom_output_table()
	if active_custom:
		return active_custom
	active = config.conf["brailleExtender"].get(ACTIVE_OUTPUT_TABLE_KEY, "")
	if active and not is_custom_table_configured(active):
		return active
	configured = config.conf["braille"]["translationTable"]
	return "auto" if configured == "auto" else configured


def persist_input_table_selection(table_id: str) -> None:
	"""Store the selected input table; keep NVDA config on a built-in or automatic table."""
	if is_custom_table_configured(table_id):
		set_active_custom_input_table(table_id)
		return
	config.conf["brailleExtender"][ACTIVE_INPUT_TABLE_KEY] = table_id
	config.conf["braille"]["inputTable"] = nvda_persisted_table_value(table_id, is_input=True)


def persist_output_table_selection(table_id: str) -> None:
	"""Store the selected output table; keep NVDA config on a built-in or automatic table."""
	if is_custom_table_configured(table_id):
		set_active_custom_output_table(table_id)
		return
	config.conf["brailleExtender"][ACTIVE_OUTPUT_TABLE_KEY] = table_id
	config.conf["braille"]["translationTable"] = nvda_persisted_table_value(table_id, is_input=False)


def ensure_nvda_braille_config_valid() -> None:
	"""Ensure NVDA ``braille`` settings never reference custom-only table file names."""
	for conf_key, active_key, is_input in (
		("inputTable", ACTIVE_INPUT_TABLE_KEY, True),
		("translationTable", ACTIVE_OUTPUT_TABLE_KEY, False),
	):
		configured = config.conf["braille"][conf_key]
		if configured == "auto":
			continue
		if is_custom_table_configured(configured):
			if not config.conf["brailleExtender"].get(active_key):
				config.conf["brailleExtender"][active_key] = configured
			config.conf["braille"][conf_key] = nvda_persisted_table_value(
				config.conf["brailleExtender"][active_key],
				is_input=is_input,
			)
			log.debug(
				"moved custom %s table %r from NVDA config to brailleExtender.%s",
				"input" if is_input else "output",
				configured,
				active_key,
			)
		elif not is_registered_table(configured):
			log.warning(
				"%s table %r is not registered; resetting NVDA config to automatic",
				"Input" if is_input else "Output",
				configured,
			)
			config.conf["braille"][conf_key] = nvda_persisted_table_value("auto", is_input=is_input)


def apply_persisted_active_tables() -> None:
	"""Apply Braille Extender active table selection to handlers when the add-on loads."""
	_apply_active_table_handlers()


def is_registered_table(table_file_name: str) -> bool:
	"""True if NVDA has a braille table registered under this file name."""
	try:
		brailleTables.getTable(table_file_name)
		return True
	except LookupError:
		return False


def is_custom_table_file_missing(table_file_name: str) -> bool:
	"""True if the table is from this add-on and its Liblouis file is absent."""
	try:
		table = brailleTables.getTable(table_file_name)
	except LookupError:
		return True
	if getattr(table, "source", None) != SOURCE_ID:
		return False
	return not os.path.isfile(get_table_path(table.fileName))


def is_table_usable(table_file_name: str) -> bool:
	"""True if the table can be used for braille input, output, or Liblouis (``auto`` is always usable)."""
	if table_file_name == "auto":
		return True
	if not is_registered_table(table_file_name):
		return False
	return not is_custom_table_file_missing(table_file_name)


def ensure_usable_table_file_name(table_file_name: str, *, is_input: bool) -> str:
	"""Return a registered table file name, falling back to the language default if needed."""
	from .common import default_braille_table_file_for_cur_language

	if table_file_name == "auto":
		return default_braille_table_file_for_cur_language(is_input=is_input)
	if is_table_usable(table_file_name):
		return table_file_name
	log.warning(
		"braille table %r is unavailable; using default for %s",
		table_file_name,
		"input" if is_input else "output",
	)
	return default_braille_table_file_for_cur_language(is_input=is_input)


def sanitize_active_braille_tables(*, apply_handlers: bool = True) -> None:
	"""Reset active settings that reference unregistered or missing custom tables."""
	from .utils import apply_braille_input_table, apply_braille_output_table

	ensure_nvda_braille_config_valid()
	configured_input = get_effective_input_table_id()
	if configured_input != "auto" and not is_table_usable(configured_input):
		log.warning(
			"input table %r is unavailable; switching to automatic",
			configured_input,
		)
		if apply_handlers:
			apply_braille_input_table("auto")
		else:
			persist_input_table_selection("auto")

	configured_output = get_effective_output_table_id()
	if configured_output != "auto" and not is_table_usable(configured_output):
		log.warning(
			"output table %r is unavailable; switching to automatic",
			configured_output,
		)
		if apply_handlers:
			apply_braille_output_table("auto")
		else:
			persist_output_table_selection("auto")

	post_table = config.conf["brailleExtender"].get("postTable")
	if post_table and post_table != POST_TABLE_NONE and not is_table_usable(post_table):
		log.warning(
			"additional output table %r is unavailable; disabling it",
			post_table,
		)
		config.conf["brailleExtender"]["postTable"] = POST_TABLE_NONE

	shortcuts_table = config.conf["brailleExtender"].get("inputTableShortcuts")
	if shortcuts_table and shortcuts_table != "?" and not is_table_usable(shortcuts_table):
		log.warning(
			"input shortcut table %r is unavailable; clearing it",
			shortcuts_table,
		)
		config.conf["brailleExtender"]["inputTableShortcuts"] = "?"


def resolve_registered_table_path(table_file_name: str) -> str:
	"""Return the on-disk path for a table registered with NVDA (delegates to the Liblouis chain)."""
	from . import braille_table_chain

	if is_custom_table_configured(table_file_name):
		path = get_table_path(table_file_name)
		if os.path.isfile(path):
			return path
		raise FileNotFoundError(table_file_name)
	if not is_table_usable(table_file_name):
		raise FileNotFoundError(table_file_name)
	return braille_table_chain.resolve_table_path(table_file_name)


def list_registered_tables_for_copy() -> list[brailleTables.BrailleTable]:
	"""Tables that can be used as a template when adding a custom table (.utb / .ctb / .tbl)."""
	return [table for table in brailleTables.listTables() if is_primary_translation_table(table.fileName)]


def _write_table_metadata(
	file_name: str,
	display_name: str,
	*,
	contracted: bool = False,
	input_table: bool = True,
	output_table: bool = True,
) -> str:
	if not input_table and not output_table:
		raise ValueError("input and output cannot both be false")
	data = load_config()
	data["tables"][file_name] = {
		"displayName": display_name.strip() or file_name,
		"contracted": bool(contracted),
		"input": bool(input_table),
		"output": bool(output_table),
	}
	save_config(data)
	return file_name


def add_table_from_path(
	source_path: str,
	display_name: str,
	*,
	contracted: bool = False,
	input_table: bool = True,
	output_table: bool = True,
) -> str:
	"""Copy a Liblouis table into storage and append metadata. Returns the stored file name."""
	if not is_supported():
		raise RuntimeError("custom braille tables require NVDA 2024.3 or later")
	_ensure_storage()
	file_name = _unique_file_name(_sanitize_file_name(source_path))
	shutil.copy2(source_path, get_table_path(file_name))
	return _write_table_metadata(
		file_name,
		display_name,
		contracted=contracted,
		input_table=input_table,
		output_table=output_table,
	)


def add_table_from_registered(
	table_file_name: str,
	display_name: str,
	*,
	contracted: bool | None = None,
	input_table: bool | None = None,
	output_table: bool | None = None,
) -> str:
	"""Copy a registered NVDA table into custom storage. Returns the stored file name."""
	source = brailleTables.getTable(table_file_name)
	return add_table_from_path(
		resolve_registered_table_path(table_file_name),
		display_name,
		contracted=source.contracted if contracted is None else contracted,
		input_table=source.input if input_table is None else input_table,
		output_table=source.output if output_table is None else output_table,
	)


def add_table_from_scratch(
	display_name: str,
	*,
	contracted: bool = False,
	input_table: bool = True,
	output_table: bool = True,
) -> str:
	"""Create a new minimal Liblouis table file. Returns the stored file name."""
	if not is_supported():
		raise RuntimeError("custom braille tables require NVDA 2024.3 or later")
	_ensure_storage()
	file_name = _unique_file_name(scratch_table_file_name(contracted=contracted))
	with open(get_table_path(file_name), "w", encoding="utf-8") as table_file:
		table_file.write(SCRATCH_TABLE_TEMPLATE)
	return _write_table_metadata(
		file_name,
		display_name,
		contracted=contracted,
		input_table=input_table,
		output_table=output_table,
	)


def update_table_metadata(
	file_name: str,
	*,
	display_name: str,
	contracted: bool,
	input_table: bool,
	output_table: bool,
) -> None:
	if not input_table and not output_table:
		raise ValueError("input and output cannot both be false")
	data = load_config()
	if file_name not in data["tables"]:
		raise KeyError(file_name)
	data["tables"][file_name] = {
		"displayName": display_name.strip() or file_name,
		"contracted": bool(contracted),
		"input": bool(input_table),
		"output": bool(output_table),
	}
	save_config(data)


def _remove_from_braille_extender_table_list(config_key: str, file_name: str) -> None:
	raw = config.conf["brailleExtender"].get(config_key)
	if not raw:
		return
	tables = parse_braille_table_list(raw)
	if file_name not in tables:
		return
	config.conf["brailleExtender"][config_key] = ",".join(t for t in tables if t != file_name)


def _input_uses_table(file_name: str) -> bool:
	if get_effective_input_table_id() == file_name:
		return True
	handler = brailleInput.handler
	return bool(handler and handler.table.fileName == file_name)


def _output_uses_table(file_name: str) -> bool:
	if get_effective_output_table_id() == file_name:
		return True
	handler = braille.handler
	return bool(handler and handler.table.fileName == file_name)


def release_table_references(file_name: str, *, apply_handlers: bool = True) -> None:
	"""Clear NVDA and Braille Extender settings that point at a removed custom table.

	When the table is active for input or output, switches to automatic selection when
	NVDA supports it (2025.1+), otherwise to the default table for the current language.
	"""
	from .utils import apply_braille_input_table, apply_braille_output_table

	_remove_from_braille_extender_table_list("inputTables", file_name)
	_remove_from_braille_extender_table_list("outputTables", file_name)

	if config.conf["brailleExtender"].get("postTable") == file_name:
		config.conf["brailleExtender"]["postTable"] = POST_TABLE_NONE

	if config.conf["brailleExtender"].get("inputTableShortcuts") == file_name:
		config.conf["brailleExtender"]["inputTableShortcuts"] = "?"

	if get_active_custom_input_table() == file_name:
		set_active_custom_input_table(ACTIVE_TABLE_NONE)
		if apply_handlers:
			nvda_input = config.conf["braille"]["inputTable"]
			apply_braille_input_table(nvda_input if nvda_input else "auto")

	if get_active_custom_output_table() == file_name:
		set_active_custom_output_table(ACTIVE_TABLE_NONE)
		if apply_handlers:
			nvda_output = config.conf["braille"]["translationTable"]
			apply_braille_output_table(nvda_output if nvda_output else "auto")


def remove_table(file_name: str, *, delete_file: bool = True) -> None:
	release_table_references(file_name)
	data = load_config()
	data["tables"].pop(file_name, None)
	save_config(data)
	if delete_file:
		path = get_table_path(file_name)
		if os.path.isfile(path):
			os.remove(path)


def open_table_file(file_name: str) -> None:
	path = get_table_path(file_name)
	if not os.path.isfile(path):
		raise FileNotFoundError(path)
	os.startfile(path)


def open_config_file() -> None:
	_ensure_storage()
	if not os.path.isfile(_config_path):
		save_config(_empty_config())
	os.startfile(_config_path)


def _strip_custom_tables_from_braille_extender_lists() -> None:
	for file_name in load_config().get("tables", {}):
		_remove_from_braille_extender_table_list("inputTables", file_name)
		_remove_from_braille_extender_table_list("outputTables", file_name)
		if config.conf["brailleExtender"].get("postTable") == file_name:
			config.conf["brailleExtender"]["postTable"] = POST_TABLE_NONE
		if config.conf["brailleExtender"].get("inputTableShortcuts") == file_name:
			config.conf["brailleExtender"]["inputTableShortcuts"] = "?"


def unregister_tables() -> None:
	if not is_supported():
		return
	to_remove = [
		file_name
		for file_name, table in brailleTables._tables.items()
		if getattr(table, "source", None) == SOURCE_ID
	]
	for file_name in to_remove:
		try:
			del brailleTables._tables[file_name]
		except KeyError:
			pass
	if SOURCE_ID in brailleTables._tablesDirs:
		del brailleTables._tablesDirs[SOURCE_ID]


def sync_nvda_registry(*, apply_handlers: bool = False) -> None:
	"""Register only the active custom table(s) with NVDA and fix configuration."""
	if not is_supported():
		sanitize_active_braille_tables(apply_handlers=apply_handlers)
		return
	_migrate_legacy_custom_table_settings()
	_ensure_storage()
	_strip_custom_tables_from_braille_extender_lists()
	unregister_tables()
	brailleTables._tablesDirs[SOURCE_ID] = _tables_dir
	for file_name in iter_tables_to_register():
		meta = load_config().get("tables", {}).get(file_name, {})
		table_path = get_table_path(file_name)
		if not os.path.isfile(table_path):
			log.warning("custom table file missing: %s", table_path)
			release_table_references(file_name, apply_handlers=False)
			continue
		try:
			brailleTables.addTable(
				fileName=file_name,
				displayName=str(meta.get("displayName", file_name)),
				contracted=bool(meta.get("contracted", False)),
				input=bool(meta.get("input", True)),
				output=bool(meta.get("output", True)),
				source=SOURCE_ID,
			)
		except Exception:
			log.exception("could not register custom table %s", file_name)
	ensure_nvda_braille_config_valid()
	sanitize_active_braille_tables(apply_handlers=apply_handlers)
	if apply_handlers:
		_apply_active_table_handlers()


def register_tables() -> None:
	"""Register custom tables and apply active selections (legacy entry point)."""
	sync_nvda_registry(apply_handlers=True)
