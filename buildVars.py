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
				"BrailleExtender is a NVDA add-on that provides various features at braille level. Currently, the following features are implemented"
			),
			":",
			"\n* ",
			_("reload two favorite braille display with shortcuts"),
			".",
			"\n* ",
			_("automatic review cursor tethering in terminal role like in PuTTY, Powershell, bash, cmd"),
			".",
			"\n* ",
			_("auto scroll"),
			".",
			"\n* ",
			_("switch between several input/output braille tables"),
			".",
			"\n* ",
			_("mark the text with special attributes through dot 7, dot 8 or both"),
			".",
			"\n* ",
			_("use two output braille tables simultaneously"),
			".",
			"\n* ",
			_("display tab signs as spaces"),
			".",
			"\n* ",
			_("reverse forward scroll and back scroll buttons"),
			".",
			"\n* ",
			_("say the current line during text scrolling either in review mode, or in focus mode or both"),
			".",
			"\n* ",
			_("translate text easily in Unicode braille and vice versa. E.g.: z <--> ⠵"),
			".",
			"\n* ",
			_("convert cell description to Unicode braille and vice versa. E.g.: 123 <--> ⠇"),
			".",
			"\n* ",
			_("lock braille keyboard"),
			".",
			"\n* ",
			_("launch an application/URL with gesture"),
			".",
			"\n* ",
			_("braille dictionaries"),
			".",
			"\n* ",
			_("type with one-hand from braille keyboard"),
			".",
			"\n* ",
			_(
				"display undefined characters from braille tables (including emojis) using altenative representations"
			),
			".",
			"\n* ",
			_("enter any character from braille keyboard (including emojis)"),
			".",
			"\n* ",
			_("skip blank lines during text scrolling"),
			".",
			"\n* ",
			_("Speech History Mode"),
			".",
			"\n* ",
			_("and much more!"),
			"\n\n",
			_("For some braille displays, it extends the braille display commands to provide"),
			":",
			"\n* ",
			_("offer complete gesture maps including function keys, multimedia keys, quick navigation, etc."),
			";",
			"\n* ",
			_("emulate modifier keys, and thus any keyboard shortcut"),
			";",
			"\n* ",
			_(
				"offer several keyboard configurations concerning the possibility to input dots 7 and 8, enter and backspace"
			),
			";",
			"\n* ",
			_("add actions and quick navigation through a rotor"),
			".",
		]
	),
	# version
	"addon_version": time.strftime("%y.%m.%d"),
	# Brief changelog for this version
	# Translators: what's new content for the add-on version to be shown in the add-on store
	"addon_changelog": _(
		"See readme.html bundled with the add-on and the project repository for detailed release notes."
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
