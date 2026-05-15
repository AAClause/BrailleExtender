# coding: utf-8
# updatecheck.py
# Part of BrailleExtender addon for NVDA
# Copyright 2021 André-Abush Clause, released under GPL.

import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request

import addonHandler
import braille
import config
import core
import globalVars
import gui
import languageHandler
import ui
import versionInfo
import wx
from logHandler import log

addonHandler.initTranslation()

baseDir = os.path.dirname(__file__)
_addonDir = os.path.join(baseDir, "..", "..")
addonInfos = addonHandler.Addon(_addonDir).manifest
sectionName = "brailleExtender"
checkInProgress = False


def paramsDL():
	return {
		"protocoleVersion": "3",
		"addonVersion": addonInfos["version"],
		"NVDAVersion": versionInfo.version,
		"channel": config.conf[sectionName]["updateChannel"],
		"language": languageHandler.getLanguage(),
		"brailledisplay": braille.handler.display.name,
	}


urlencode = urllib.parse.urlencode
urlopen = urllib.request.urlopen


def checkUpdates(sil=False):

	global checkInProgress

	def availableUpdateDialog(version="", msg=""):
		global checkInProgress
		checkInProgress = True
		res = gui.messageBox(
			(
				_("{addonName} version {version} is available. Do you want to download it now?").format(
					addonName=addonInfos["summary"],
					version=data["lastVersions"][config.conf[sectionName]["updateChannel"]],
				)
				+ "\n"
				+ data["msg"]
			),
			title,
			wx.YES | wx.NO | wx.ICON_INFORMATION,
		)
		if res == wx.YES:
			processUpdate(data["lastVersions"][config.conf[sectionName]["updateChannel"] + "_SHA256Sum"])
		checkInProgress = False

	def upToDateDialog(msg=""):
		global checkInProgress
		checkInProgress = True
		res = gui.messageBox(
			(
				_("You are up-to-date. %s is the latest version.") % addonInfos["version"] + "\n%s" % msg
			).strip(),
			title,
			wx.OK | wx.ICON_INFORMATION,
		)
		if res:
			checkInProgress = False

	def errorUpdateDialog(details=None):
		global checkInProgress
		checkInProgress = True
		msg = (
			_(
				"Oops! There was a problem downloading Braille Extender update. Please retry later or download and install manually from %s. Do you want to open this URL in your browser?"
			)
			% addonInfos["url"]
		)
		if details:
			msg += "\n" + _("Details:") + " " + repr(details)
		res = gui.messageBox(msg, title, wx.YES | wx.NO | wx.ICON_ERROR)
		if res == wx.YES:
			os.startfile(addonInfos["url"])
		checkInProgress = False

	def processUpdate(expectedSHA256Sum):
		url = addonInfos["url"]
		if url.endswith("/"):
			url = url[0:-1]
		url = "%s.nvda-addon?%s" % (url, urlencode(paramsDL()))
		fp = os.path.join(globalVars.appArgs.configPath, "%s.nvda-addon" % sectionName)
		try:
			with urllib.request.urlopen(url) as res:
				with open(fp, "wb") as out:
					out.write(res.read())
			actualSHA256Sum = SHA256Sum(fp)
			if expectedSHA256Sum != actualSHA256Sum:
				log.info(
					"Invalid hash for %s. Actual: %s, expected: %s" % (fp, actualSHA256Sum, expectedSHA256Sum)
				)
				msg = _(
					"Hashes do not match! Actual value is '{actualHash}'. Expected is '{expectedHash}'."
				).format(actualHash=actualSHA256Sum, expectedHash=expectedSHA256Sum)
				wx.CallAfter(errorUpdateDialog, msg)
				return
			curAddons = []
			for addon in addonHandler.getAvailableAddons():
				curAddons.append(addon)
			bundle = addonHandler.AddonBundle(fp)
			prevAddon = None
			bundleName = bundle.manifest["name"]
			for addon in curAddons:
				if not addon.isPendingRemove and bundleName == addon.manifest["name"]:
					prevAddon = addon
					break
			if prevAddon:
				prevAddon.requestRemove()
			addonHandler.installAddonBundle(bundle)
			core.restart()
		except BaseException as e:
			log.error(e)
			return wx.CallAfter(errorUpdateDialog, e)

	if checkInProgress:
		return ui.message(_("An update check dialog is already running!"))
	title = _("Braille Extender update")
	newUpdate = False
	url = addonInfos["url"]
	if url.endswith("/"):
		url = url[0:-1]
	url = "%s.json?%s" % (url, urlencode(paramsDL()))
	try:
		page = urlopen(url)
		if page.code == 200:
			data = json.load(page)
			if not data["success"]:
				raise ValueError("Invalid JSON response")
			if not data["upToDate"]:
				newUpdate = True
			if not newUpdate and sil:
				return log.debug("No update")
			if newUpdate:
				wx.CallAfter(availableUpdateDialog, data)
			else:
				wx.CallAfter(upToDateDialog, data["msg"])
		else:
			raise ValueError("Invalid server code response: %s" % page.code)
	except BaseException as err:
		log.warning(err)
		if not newUpdate and sil:
			return
		wx.CallAfter(errorUpdateDialog)


def SHA256Sum(fp):
	# Borrowed from
	# <https://www.quickprogrammingtips.com/python/how-to-calculate-sha256-hash-of-a-file-in-python.html>
	sha256_hash = hashlib.sha256()
	with open(fp, "rb") as f:
		for byte_block in iter(lambda: f.read(4096), b""):
			sha256_hash.update(byte_block)
	return sha256_hash.hexdigest()


class UpdateCheck(threading.Thread):
	shouldStop = False

	def run(self):
		if globalVars.appArgs.secure or config.isAppX or globalVars.appArgs.launcher:
			return self.stop()
		checkingForced = False
		delayChecking = 86400 if config.conf[sectionName]["updateChannel"] != "stable" else 604800
		while not self.shouldStop:
			if not checkInProgress and config.conf[sectionName]["autoCheckUpdate"]:
				if config.conf[sectionName]["lastNVDAVersion"] != versionInfo.version:
					config.conf[sectionName]["lastNVDAVersion"] = versionInfo.version
					checkingForced = True
				if (
					checkingForced
					or (time.time() - config.conf[sectionName]["lastCheckUpdate"]) > delayChecking
				):
					log.info("Checking update... Forced: %s" % ("yes" if checkingForced else "no"))
					checkUpdates(True)
					config.conf[sectionName]["lastCheckUpdate"] = time.time()
				checkingForced = False
			time.sleep(0.2)

	def stop(self):
		self.shouldStop = True
