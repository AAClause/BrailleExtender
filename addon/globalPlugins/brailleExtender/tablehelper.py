# tablehelper.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2022 André-Abush Clause, released under GPL.
import config
from brailleTables import listTables
from typing import List

conf = config.conf["brailleExtender"]["tables"]

def get_tables(tables=None, contracted=None, output=None, input=None):
	if not tables:
		tables = listTables()
	if isinstance(contracted, bool):
		tables = filter(lambda e: e.contracted == contracted, tables)
	if isinstance(input, bool):
		tables = filter(lambda e: e.input == input, tables)
	if isinstance(output, bool):
		tables = filter(lambda e: e.output == output, tables)
	return list(tables)


def get_file_names(tables=None):
	if not tables:
		tables = listTables()
	if not isinstance(tables, list):
		raise TypeError(f"tables: wrong type. {tables}")
	return [table.fileName for table in tables]


def get_file_names_by_display_names(l):
	file_names = get_file_names()
	o = []
	for e in l:
		if e in file_names:
			o.append(file_names.index(e))
	return [listTables()[e].displayName for e in o]


def get_display_names(tables=None):
	if not tables:
		tables = listTables()
	return [table.displayName for table in tables]


def get_indexes(l, tables=None):
	if not tables:
		tables = listTables()
	if not l:
		raise ValueError("l: empty list")
	return [tables.index(e) for e in l if e in tables]


def get_table_by_file_name(fileName, tables=None):
	if not tables:
		tables = listTables()
	for table in tables:
		if table.fileName == fileName:
			return table
	return None

def get_table_by_file_names(l, tables=None):
	if not tables:
		tables = listTables()
	return [get_table_by_file_name(e, tables) for e in l]

def get_tables_file_name_by_id(l: List[int], tables=None) -> List[int]:
	file_names = get_file_names(tables or listTables())
	o = []
	size = len(file_names)
	for i in l:
		if i < size:
			o.append(file_names[i])
	return o


def getPreferredTables():
	preferredTables = (
		[e for e in conf["preferredInput"].split('|') if e],
		[e for e in conf["preferredOutput"].split('|') if e]
	)
	return preferredTables


def getPreferredTablesIndexes():
	preferredInputTables, preferredOutputTables = getPreferredTables()
	preferredInputTables = get_table_by_file_names(preferredInputTables)
	preferredOutputTables = get_table_by_file_names(preferredOutputTables)
	inputTables = get_tables(input=True)
	outputTables = get_tables(output=True)
	return (
		get_indexes(preferredInputTables, inputTables),
		get_indexes(preferredOutputTables, outputTables)
	)


