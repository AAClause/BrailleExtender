# coding: utf-8
# regionhelper.py
# Part of BrailleExtender addon for NVDA
# Copyright 2016-2020 André-Abush CLAUSE, released under GPL.


class BrailleCellReplacement:

	def __init__(
		self, start: int, end: int=-1,
		replaceBy: str='', insertAfter: str='', insertBefore: str='',
		addDots: int=0
	):
		if start < 0: raise ValueError("start must be a value >= 0")
		self.start = start
		self.end = start if end < 0 else end
		self.replaceBy = replaceBy
		self.insertAfter = insertAfter
		self.insertBefore = insertBefore
		self.addDots = addDots

	def __repr__(self):
		return repr({
			"start": self.start,
			"end": self.end,
			"replaceBy": self.replaceBy,
			"insertAfter": self.insertAfter,
			"insertBefore": self.insertBefore,
			"addDots": self.addDots
		})


def getUnicodeBrailleFromRawPos(region, i):
	start, end = getBraillePosFromRawPos(region, i)
	return ''.join([chr(x+0x2800) for x in region.brailleCells[start:end+1]])

def getBrailleCellFromRawPos(region, i):
	start, end = getBraillePosFromRawPos(region, i)
	return region.brailleCells[start:end+1]

def getBraillePosFromRawPos(region, i):
	try:
		start = region.rawToBraillePos[i]
		end = start + region.brailleToRawPos.count(region.brailleToRawPos[start]) - 1
	except IndexError:
		start, end = 0, 0
	return start, end

def streamRegionFromRawText(region):
	if not region: return None
	for i, rawText in enumerate(region.rawText):
		startBraillePos, endBraillePos = getBraillePosFromRawPos(region, i)
		bc = getBrailleCellFromRawPos(region, i)
		uc = getUnicodeBrailleFromRawPos(region, i)
		yield i, rawText, startBraillePos, endBraillePos, bc, uc

def findBrailleCellsPattern(region, pattern):
	y = streamRegionFromRawText(region)
	for i, rawText, startBraillePos, endBraillePos, bc, uc in y:
		if uc == pattern: yield i

def replaceBrailleCells(region, replacements):
	if not replacements: return region
	replacements.sort(key=lambda r: (r.start, r.end))
	replacements = {e.start: e for e in replacements}
	y = streamRegionFromRawText(region)
	rawPosDone = []
	braillePosDone = []
	newBrailleCells = []
	newBrailleToRawPos = []
	newRawToBraillePos = []
	for i, rawText, startBraillePos, endBraillePos, bc, uc in y:
		if i in rawPosDone: continue
		szBefore = 0
		szRawText = 1
		addDots = 0
		if i in replacements:
			r = replacements[i]
			addDots = r.addDots
			szBefore = len(r.insertBefore)
			if r.replaceBy: uc = r.replaceBy
			uc = r.insertBefore + uc + r.insertAfter
			if r.start < r.end:
				newPosDone = [e for e in range(r.start, r.end+1)]
				szRawText = len(newPosDone)
				rawPosDone += newPosDone
		cursorPos = len(newBrailleCells) + szBefore
		if startBraillePos in braillePosDone:
			newRawToBraillePos += [newRawToBraillePos[-1]]
			continue
		newBrailleCells += [ord(c)-0x2800 for c in uc]
		if addDots: newBrailleCells = [d | addDots for d in newBrailleCells]
		newBrailleToRawPos += len(uc)*[i]
		newRawToBraillePos += [cursorPos] * szRawText
		newPosDone = [e for e in range(startBraillePos, endBraillePos+1)]
		braillePosDone += newPosDone
	region.brailleCells = newBrailleCells
	region.brailleToRawPos = newBrailleToRawPos
	region.rawToBraillePos = newRawToBraillePos
	if isinstance(region.cursorPos, int) and region.cursorPos >= 0: region.brailleCursorPos = region.rawToBraillePos[region.cursorPos]
