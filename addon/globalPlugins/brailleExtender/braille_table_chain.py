# coding: utf-8
# braille_table_chain.py - Part of BrailleExtender addon for NVDA
# Copyright 2016-2026 André-Abush CLAUSE, released under GPL.
"""Build and cache the Liblouis table chain (dictionaries, main table, additional output pass)."""

from __future__ import annotations

import os
from typing import Optional

import api
import appModuleHandler
import brailleInput
import brailleTables
import config
from logHandler import log

from .common import baseDir, default_braille_table_file_for_cur_language
from . import addoncfg
from . import tabledictionaries

POST_TABLE_NONE = "None"
BRAILLE_PATTERNS = "braille-patterns.cti"


def get_translation_table_file() -> str:
	"""Resolve NVDA output table config (including ``auto``) to a table file name."""
	translation_table = config.conf["braille"]["translationTable"]
	if translation_table == "auto":
		return default_braille_table_file_for_cur_language(is_input=False)
	return translation_table


def liblouis_paths_for_table(table_file: str) -> list[str]:
	"""Main table and ``braille-patterns.cti`` as absolute paths."""
	tables_dir = brailleTables.TABLES_DIR
	return [
		os.path.join(tables_dir, table_file),
		os.path.join(tables_dir, BRAILLE_PATTERNS),
	]


def get_configured_additional_output_file() -> Optional[str]:
	"""Configured additional output pass table file name, or ``None`` if disabled."""
	configured = config.conf["brailleExtender"]["postTable"]
	if not configured or configured == POST_TABLE_NONE:
		return None
	if addoncfg.noUnicodeTable or configured not in addoncfg.tablesFN:
		log.warning("Braille Extender: invalid additional output table %r", configured)
		return None
	return configured


class _TableChainCache:
	"""Runtime cache of Liblouis table paths; refreshed when settings or dictionaries change."""

	def __init__(self) -> None:
		self._additional_output_path: Optional[str] = None
		self._additional_output_disabled_for_session = False

	def refresh(self) -> None:
		"""Reload preferred table lists, dictionary paths, and additional output pass."""
		addoncfg.loadPreferredTables()
		tabledictionaries.refresh_dictionary_paths()
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
		path = os.path.join(brailleTables.TABLES_DIR, table_file)
		log.debug("Braille Extender: additional Liblouis output pass enabled: %s", table_file)
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
			tables.extend(tabledictionaries.dictTables)

		if for_input:
			table_file = brailleInput.handler._table.fileName
		else:
			table_file = get_translation_table_file()
		tables.extend(liblouis_paths_for_table(table_file))

		if not for_input and self.has_additional_output() and self._additional_output_path:
			tables.append(self._additional_output_path)
		return tables


def _should_include_dictionary_tables() -> bool:
	try:
		app = appModuleHandler.getAppModuleForNVDAObject(api.getNavigatorObject())
	except OSError:
		return False
	return bool(app and app.appName != "nvda")


_cache = _TableChainCache()


def refresh() -> None:
	"""Refresh all cached table paths (call after settings or dictionary changes)."""
	_cache.refresh()


def get_liblouis_table_chain(*, for_input: bool = False, brf: bool = False) -> list[str]:
	return _cache.build(for_input=for_input, brf=brf)


def disable_additional_output_for_session() -> None:
	_cache.disable_additional_output_for_session()


def has_additional_output() -> bool:
	return _cache.has_additional_output()


def list_output_table_file_names() -> list[str]:
	"""Output table file names valid for the additional Liblouis pass setting."""
	return [table[0] for table in addoncfg.tables if table.output]
