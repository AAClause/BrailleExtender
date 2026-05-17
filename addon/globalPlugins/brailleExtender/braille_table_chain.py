# coding: utf-8
# braille_table_chain.py - Part of BrailleExtender addon for NVDA
# Copyright 2016-2026 André-Abush CLAUSE, released under GPL.
"""Build and cache the Liblouis table chain (dictionaries, main table, additional output pass)."""

from __future__ import annotations

import os
from typing import Optional

import api
import appModuleHandler
import braille
import brailleInput
import brailleTables
import config
from logHandler import log

from .common import (
	NVDA_HAS_CUSTOM_BRAILLE_TABLES,
	POST_TABLE_NONE,
	baseDir,
	default_braille_table_file_for_cur_language,
)
from . import addoncfg

BRAILLE_PATTERNS = "braille-patterns.cti"


def get_translation_table_file() -> str:
	"""Resolve the active output table file name (built-in, add-on, scratchpad, or Braille Extender custom)."""
	from .custom_braille_tables import ensure_usable_table_file_name, get_effective_output_table_id

	table_id = get_effective_output_table_id()
	if table_id == "auto":
		return default_braille_table_file_for_cur_language(is_input=False)
	return ensure_usable_table_file_name(table_id, is_input=False)


def resolve_table_path(table_file: str) -> str:
	"""Absolute path to a Liblouis table file registered with NVDA.

	On NVDA 2024.3+, uses ``brailleTables._tablesDirs`` for scratchpad and add-on tables.
	On older releases, only the built-in ``TABLES_DIR`` is searched.
	See https://github.com/AAClause/BrailleExtender/issues/138
	"""
	try:
		table = brailleTables.getTable(table_file)
	except LookupError:
		table = None
	directories: list[str] = []
	if table is not None and NVDA_HAS_CUSTOM_BRAILLE_TABLES and hasattr(brailleTables, "_tablesDirs"):
		source_dir = brailleTables._tablesDirs.get(getattr(table, "source", None))
		if source_dir:
			directories.append(source_dir)
	if brailleTables.TABLES_DIR not in directories:
		directories.append(brailleTables.TABLES_DIR)
	file_name = table.fileName if table is not None else table_file
	for directory in directories:
		path = os.path.join(directory, file_name)
		if os.path.isfile(path):
			return path
	if NVDA_HAS_CUSTOM_BRAILLE_TABLES and hasattr(brailleTables, "_tablesDirs"):
		for directory in brailleTables._tablesDirs.values():
			if directory in directories:
				continue
			path = os.path.join(directory, table_file)
			if os.path.isfile(path):
				return path
	raise FileNotFoundError(table_file)


def liblouis_paths_for_table(table_file: str, *, is_input: bool = False) -> list[str]:
	"""Main table and ``braille-patterns.cti`` as absolute paths (never raises)."""
	from .custom_braille_tables import ensure_usable_table_file_name

	patterns = os.path.join(brailleTables.TABLES_DIR, BRAILLE_PATTERNS)
	table_file = ensure_usable_table_file_name(table_file, is_input=is_input)
	try:
		primary = resolve_table_path(table_file)
	except FileNotFoundError:
		fallback = default_braille_table_file_for_cur_language(is_input=is_input)
		log.warning(
			"could not resolve Liblouis table %r; using %s",
			table_file,
			fallback,
			exc_info=True,
		)
		try:
			primary = resolve_table_path(fallback)
		except FileNotFoundError:
			primary = os.path.join(brailleTables.TABLES_DIR, brailleTables.DEFAULT_TABLE)
	if not os.path.isfile(patterns):
		log.error("Liblouis patterns table missing: %s", patterns)
	return [primary, patterns]


def get_configured_additional_output_file() -> Optional[str]:
	"""Configured additional output pass table file name, or ``None`` if disabled."""
	configured = config.conf["brailleExtender"]["postTable"]
	if not configured or configured == POST_TABLE_NONE:
		return None
	if addoncfg.noUnicodeTable or configured not in addoncfg.tablesFN:
		log.warning("invalid additional output table %r", configured)
		return None
	return configured


class _TableChainCache:
	"""Runtime cache of Liblouis table paths; refreshed when settings or dictionaries change."""

	def __init__(self) -> None:
		self._additional_output_path: Optional[str] = None
		self._additional_output_disabled_for_session = False

	def rebuild_additional_output_cache(self) -> None:
		"""Re-resolve the optional second Liblouis output pass from current settings."""
		self._additional_output_disabled_for_session = False
		self._additional_output_path = self._resolve_additional_output_path()

	def disable_additional_output_for_session(self) -> None:
		self._additional_output_disabled_for_session = True

	def has_additional_output(self) -> bool:
		return self._additional_output_path is not None and not self._additional_output_disabled_for_session

	def _resolve_additional_output_path(self) -> Optional[str]:
		table_file = get_configured_additional_output_file()
		if not table_file:
			return None
		try:
			path = resolve_table_path(table_file)
		except FileNotFoundError:
			log.warning(
				"additional output table file not found: %s",
				table_file,
			)
			return None
		log.debug("additional Liblouis output pass enabled: %s", table_file)
		return path

	def build(self, *, for_input: bool = False, brf: bool = False) -> list[str]:
		"""Return the ordered Liblouis table path list for translation or compileString."""
		if brf:
			return [
				os.path.join(baseDir, "res", "brf.ctb"),
				os.path.join(brailleTables.TABLES_DIR, BRAILLE_PATTERNS),
			]

		tables: list[str] = []
		if _should_include_dictionary_tables():
			from . import tabledictionaries

			tables.extend(tabledictionaries.dictTables)

		try:
			if for_input:
				if brailleInput.handler:
					table_file = brailleInput.handler._table.fileName
				else:
					table_file = default_braille_table_file_for_cur_language(is_input=True)
			else:
				if braille.handler and getattr(braille.handler, "_table", None):
					table_file = braille.handler._table.fileName
				else:
					table_file = get_translation_table_file()
			tables.extend(liblouis_paths_for_table(table_file, is_input=for_input))
		except Exception:
			log.exception("building Liblouis table chain failed; using defaults")
			tables.extend(
				liblouis_paths_for_table(
					default_braille_table_file_for_cur_language(is_input=for_input),
					is_input=for_input,
				)
			)

		if not for_input and self.has_additional_output() and self._additional_output_path:
			if os.path.isfile(self._additional_output_path):
				tables.append(self._additional_output_path)
			else:
				log.warning(
					"additional output table path missing: %s",
					self._additional_output_path,
				)
				self._additional_output_disabled_for_session = True
		return tables


def _should_include_dictionary_tables() -> bool:
	try:
		app = appModuleHandler.getAppModuleForNVDAObject(api.getNavigatorObject())
	except OSError:
		return False
	return bool(app and app.appName != "nvda")


_cache = _TableChainCache()


def rebuild_additional_output_cache() -> None:
	"""Rebuild cached paths for the additional Liblouis output pass."""
	_cache.rebuild_additional_output_cache()


def refresh() -> None:
	"""Refresh the full table system (prefer :func:`braille_tables.refresh_table_system`)."""
	from . import braille_tables

	braille_tables.refresh_table_system(apply_handlers=False)


def get_liblouis_table_chain(*, for_input: bool = False, brf: bool = False) -> list[str]:
	return _cache.build(for_input=for_input, brf=brf)


def disable_additional_output_for_session() -> None:
	_cache.disable_additional_output_for_session()


def has_additional_output() -> bool:
	return _cache.has_additional_output()


def list_output_table_file_names() -> list[str]:
	"""Output table file names valid for the additional Liblouis pass setting."""
	return [table.fileName for table in addoncfg.tables if table.output]
