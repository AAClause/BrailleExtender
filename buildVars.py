# -*- coding: UTF-8 -*-
import subprocess
import time

# Build customizations
# Change this file instead of sconstruct or manifest files, whenever possible.

from site_scons.site_tools.NVDATool.typings import AddonInfo, BrailleTables, SymbolDictionaries
from site_scons.site_tools.NVDATool.utils import _


updateChannel = None
hashCommit = None
outBranchName = subprocess.check_output(["git", "branch", "--show-current"]).strip().decode()
out = subprocess.check_output(["git", "status", "--porcelain"]).strip().decode()
if not out.strip():
	label = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode()
	if label and len(label) == 7:
		hashCommit = label
if outBranchName.strip():
	updateChannel = "stable" if outBranchName in ["stable", "master"] else "dev"

# Add-on information variables
addon_info: AddonInfo = {
	# add-on Name/identifier, internal for NVDA
	"addon_name": "BrailleExtender",
	# Add-on summary, usually the user visible name of the addon.
	# Translators: Summary for this add-on
	# to be shown on installation and add-on information found in Add-ons Manager.
	"addon_summary": _("Braille Extender"),
	# Add-on description
	# Translators: Long description to be shown for this add-on on add-on information from add-ons manager
	"addon_description": "".join(
		[
			_(
				"Braille Extender is an NVDA add-on that extends braille output, braille input, scrolling, and display-specific gestures. It requires NVDA 2024.1 or later. For full documentation, open the User guide from the NVDA menu under Braille Extender."
			),
			"\n\n",
			_("Main features include:"),
			"\n* ",
			_("Reload two favorite braille displays with shortcuts"),
			"\n* ",
			_(
				"Terminals: braille can follow the review cursor while you edit (PuTTY, PowerShell, cmd, bash, and similar)"
			),
			"\n* ",
			_("Auto scroll with timing and blank-line options"),
			"\n* ",
			_(
				"Multiple input and output braille tables, with automatic table selection on NVDA 2025.1 and later"
			),
			"\n* ",
			_("Dots 7 and 8, tags, and spacing or line padding for structure and attributes"),
			"\n* ",
			_("Optional second Liblouis pass after the main output table"),
			"\n* ",
			_("Display tab characters as spaces; swap forward and back scroll buttons"),
			"\n* ",
			_("Speak the current line while scrolling (coordinate with NVDA braille speech settings)"),
			"\n* ",
			_(
				"Convert text to Unicode braille and back, and between Unicode braille and dot-number descriptions"
			),
			"\n* ",
			_("Lock the braille keyboard; lock modifier keys from the braille display"),
			"\n* ",
			_("Quick launches to applications or web addresses; table dictionaries"),
			"\n* ",
			_(
				"One-handed braille input; rules for undefined characters including emoji; advanced input mode and abbreviations"
			),
			"\n* ",
			_(
				"Speech History Mode; configurable rotor; object and document presentation options for braille; role labels; routing in edit fields; margins; updates; and other settings"
			),
			"\n\n",
			_(
				"Where a display profile exists, the add-on can add extended gesture maps (function keys, multimedia keys, rotor actions, emulated modifiers, and more). Assign commands in NVDA Input gestures for Braille Extender, or open Gestures for this display from the Braille Extender submenu."
			),
		]
	),
	# version
	"addon_version": time.strftime("%y.%m.%d"),
	# Brief changelog for this version
	# Translators: what's new content for the add-on version to be shown in the add-on store
	"addon_changelog": _(
		"See the User guide bundled with the add-on and the project repository for detailed release notes."
	),
	# Author(s)
	"addon_author": "André-Abush Clause <dev@andreabc.net> " + _("and other contributors"),
	# URL for the add-on documentation support
	"addon_url": "https://andreabc.net/projects/NVDA_addons/BrailleExtender",
	# URL for the add-on repository where the source code can be found
	"addon_sourceURL": "https://github.com/aaclause/brailleExtender/",
	# Documentation file name
	"addon_docFileName": "readme.html",
	# Minimum NVDA version supported (e.g. "2018.3.0", minor version is optional)
	"addon_minimumNVDAVersion": "2024.1",
	# Last NVDA version supported/tested (e.g. "2018.4.0", ideally more recent than minimum version)
	"addon_lastTestedNVDAVersion": "2026.1",
	# Add-on update channel (default is None, denoting stable releases,
	# and for development releases, use "dev".)
	# Do not change unless you know what you are doing!
	"addon_updateChannel": updateChannel,
	# Add-on license such as GPL 2
	"addon_license": "GPL v2",
	# URL for the license document the ad-on is licensed under
	"addon_licenseURL": "https://www.gnu.org/licenses/gpl-2.0.html",
}
if hashCommit:
	addon_info["addon_version"] += "-" + hashCommit

# Define the python files that are the sources of your add-on.
# You can either list every file (using "/" as a path separator),
# or use glob expressions.
# For example to include all files with a ".py" extension from the "globalPlugins" dir of your add-on
# the list can be written as follows:
# pythonSources = ["addon/globalPlugins/*.py"]
# For more information on SCons Glob expressions please take a look at:
# https://scons.org/doc/production/HTML/scons-user/apd.html
pythonSources: list[str] = ["addon/globalPlugins/brailleExtender/*.py"]

# Files that contain strings for translation. Usually your python sources
i18nSources: list[str] = pythonSources + ["buildVars.py"]

# Files that will be ignored when building the nvda-addon file
# Paths are relative to the addon directory, not to the root directory of your addon sources.
# You can either list every file (using "/" as a path separator),
# or use glob expressions.
excludedFiles: list[str] = []

# Base language for the NVDA add-on
# If your add-on is written in a language other than english, modify this variable.
# For example, set baseLanguage to "es" if your add-on is primarily written in spanish.
# You must also edit .gitignore file to specify base language files to be ignored.
baseLanguage: str = "en"

# Markdown extensions for add-on documentation
# Most add-ons do not require additional Markdown extensions.
# If you need to add support for markup such as tables, fill out the below list.
# Extensions string must be of the form "markdown.extensions.extensionName"
# e.g. "markdown.extensions.tables" to add tables.
markdownExtensions: list[str] = ["markdown.extensions.tables"]

# Custom braille translation tables
# If your add-on includes custom braille tables (most will not), fill out this dictionary.
# Each key is a dictionary named according to braille table file name,
# with keys inside recording the following attributes:
# displayName (name of the table shown to users and translatable),
# contracted (contracted (True) or uncontracted (False) braille code),
# output (shown in output table list),
# input (shown in input table list).
brailleTables: BrailleTables = {}

# Custom speech symbol dictionaries
# Symbol dictionary files reside in the locale folder, e.g. `locale\en`, and are named `symbols-<name>.dic`.
# If your add-on includes custom speech symbol dictionaries (most will not), fill out this dictionary.
# Each key is the name of the dictionary,
# with keys inside recording the following attributes:
# displayName (name of the speech dictionary shown to users and translatable),
# mandatory (True when always enabled, False when not.
symbolDictionaries: SymbolDictionaries = {}
