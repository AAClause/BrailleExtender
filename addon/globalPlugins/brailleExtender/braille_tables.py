# coding: utf-8
# braille_tables.py - Part of BrailleExtender addon for NVDA
# Copyright 2016-2026 André-Abush CLAUSE, released under GPL.
"""Orchestrate custom tables, preferred lists, dictionaries, and the Liblouis chain."""

from __future__ import annotations


def refresh_table_system(*, apply_handlers: bool = False) -> None:
	"""Refresh the full braille table stack in a fixed order (one registration pass).

	1. Register custom tables and validate configuration
	2. Refresh cached NVDA table lists
	3. Sync preferred input/output table lists
	4. Reload per-table dictionary paths
	5. Rebuild the additional Liblouis output-pass cache
	6. Optionally apply persisted active tables to braille handlers
	"""
	from . import addoncfg
	from . import braille_table_chain
	from . import custom_braille_tables
	from . import tabledictionaries

	custom_braille_tables.sync_nvda_registry(apply_handlers=False)
	addoncfg.refresh_braille_tables_cache()
	addoncfg.sync_preferred_table_lists()
	tabledictionaries.refresh_dictionary_paths()
	braille_table_chain.rebuild_additional_output_cache()
	if apply_handlers:
		custom_braille_tables.apply_persisted_active_tables()


def reload_liblouis_chain(*, apply_handlers: bool = False) -> None:
	"""Free Liblouis state and rebuild the table system (no braille display refresh)."""
	from . import patches

	patches.louis.liblouis.lou_free()
	refresh_table_system(apply_handlers=apply_handlers)
