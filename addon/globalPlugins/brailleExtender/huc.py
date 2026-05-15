#!/usr/bin/env python3
# coding: utf-8
import re

_RE_CELL_DESC = re.compile(r"^[0-8]+$")
_RE_CELL_DESCS = re.compile(r"([0-8]+)\-?")
_RE_LAST_HUC6_CELL = re.compile(r"-([0-6]+)$")

HUC6_patterns = {
	"⠿": (0x000000, 0x1FFFF),
	"⠿…⠇": (0x020000, 0x02FFFF),
	"⠿…⠍": (0x030000, 0x03FFFF),
	"⠿…⠝": (0x040000, 0x04FFFF),
	"⠿…⠕": (0x050000, 0x05FFFF),
	"⠿…⠏": (0x060000, 0x06FFFF),
	"⠿…⠟": (0x070000, 0x07FFFF),
	"⠿…⠗": (0x080000, 0x08FFFF),
	"⠿…⠎": (0x090000, 0x09FFFF),
	"⠿…⠌": (0x0A0000, 0x0AFFFF),
	"⠿…⠜": (0x0B0000, 0x0BFFFF),
	"⠿…⠖": (0x0C0000, 0x0CFFFF),
	"⠿…⠆": (0x0D0000, 0x0DFFFF),
	"⠿…⠔": (0x0E0000, 0x0EFFFF),
	"⠿…⠄": (0x0F0000, 0x0FFFFF),
	"⠿…⠥": (0x100000, 0x10FFFF),
}

HUC8_patterns = {
	"⣥": (0x000000, 0x00FFFF),
	"⣭": (0x010000, 0x01FFFF),
	"⣽": (0x020000, 0x02FFFF),
	"⣵⠾": (0x030000, 0x03FFFF),
	"⣵⢾": (0x040000, 0x04FFFF),
	"⣵⢞": (0x050000, 0x05FFFF),
	"⣵⡾": (0x060000, 0x06FFFF),
	"⣵⣾": (0x070000, 0x07FFFF),
	"⣵⣞": (0x080000, 0x08FFFF),
	"⣵⡺": (0x090000, 0x09FFFF),
	"⣵⠺": (0x0A0000, 0x0AFFFF),
	"⣵⢺": (0x0B0000, 0x0BFFFF),
	"⣵⣚": (0x0C0000, 0x0CFFFF),
	"⣵⡚": (0x0D0000, 0x0DFFFF),
	"⣵⢚": (0x0E0000, 0x0EFFFF),
	"⣵⠚": (0x0F0000, 0x0FFFFF),
	"⣵⣡": (0x100000, 0x10FFFF),
}

hexVals = ["245", "1", "12", "14", "145", "15", "124", "1245", "125", "24", "4", "45", "25", "2", "5", "0"]

HUC_INPUT_INVALID = 0
HUC_INPUT_INCOMPLETE = 1
HUC_INPUT_COMPLETE = 2

_DOTS_BIT_TO_DIGIT = {1: 1, 2: 2, 4: 3, 8: 4, 16: 5, 32: 6, 64: 7, 128: 8}

print_ = print


def cellDescToChar(cell):
	if not _RE_CELL_DESC.match(cell):
		return "?"
	toAdd = 0
	for dot in cell:
		d = int(dot)
		if d > 0:
			toAdd += 1 << (d - 1)
	return chr(0x2800 + toAdd)


def charToCellDesc(ch):
	if len(ch) != 1:
		raise ValueError("Param size can only be one char (currently: %d)" % len(ch))
	p = ord(ch)
	if 0x2800 <= p <= 0x28FF:
		p -= 0x2800
	if p > 255:
		raise ValueError(r"It is not an unicode braille (%d)" % p)
	res = []
	i = 1
	while p:
		val = 128 // i
		if p >= val:
			res.append(str(_DOTS_BIT_TO_DIGIT[val]))
			p -= val
		i *= 2
	return "".join(reversed(res)) if res else "0"


def unicodeBrailleToDescription(t, sep="-"):
	parts = []
	for ch in t:
		if ch in "\n\r":
			parts.append(ch)
		else:
			cp = ord(ch)
			if 0x2800 <= cp <= 0x28FF:
				parts.append("-" + charToCellDesc(ch))
			else:
				parts.append(ch)
	return "".join(parts).strip(sep)


def cellDescriptionsToUnicodeBraille(t):
	return _RE_CELL_DESCS.sub(lambda m: cellDescToChar(m.group(1)), t)


def getPrefixAndSuffix(c, HUC6=False):
	ord_ = ord(c)
	patterns = HUC6_patterns if HUC6 else HUC8_patterns
	for key, (_, end) in patterns.items():
		if end >= ord_:
			return key
	return "?"


def translateHUC6(dots, debug=False):
	ref1 = "1237"
	ref2 = "4568"
	data = dots.split("-")
	offset = 0
	linedCells1 = []
	linedCells2 = []
	for cell in data:
		for dot in "12345678":
			if dot not in cell:
				if dot in ref1:
					linedCells1.append("0")
				if dot in ref2:
					linedCells2.append("0")
			else:
				dotTemp = "0"
				if dot in ref1:
					dotIndexTemp = (ref1.index(dot) + offset) % 3
					dotTemp = ref1[dotIndexTemp]
					linedCells1.append(dotTemp)
				elif dot in ref2:
					dotIndexTemp = (ref2.index(dot) + offset) % 3
					dotTemp = ref2[dotIndexTemp]
					linedCells2.append(dotTemp)
		offset = (offset + 1) % 3
	out = []
	i = 0
	for l1, l2 in zip(linedCells1, linedCells2):
		if i % 3 == 0:
			out.append("")
		cellTemp = (l1 if l1 != "0" else "") + (l2 if l2 != "0" else "")
		cellTemp = "".join(sorted(cellTemp))
		out[-1] += cellTemp if cellTemp else "0"
		out[-1] = "".join(sorted([dot for dot in out[-1] if dot != "0"]))
		if not out[-1]:
			out[-1] = "0"
		i += 1
	if debug:
		print_(":translateHUC6:", dots, "->", repr(out))
	out = "-".join(out)
	return out


def translateHUC8(dots, debug=False):
	newDots = "037168425"
	out = "".join(newDots[int(d)] for d in dots)
	out = "".join(sorted(out))
	if debug:
		print_(":translateHUC8:", dots, "->", out)
	return out


def translate(t, HUC6=False, unicodeBraille=True, debug=False):
	out = ""
	for c in t:
		pattern = getPrefixAndSuffix(c, HUC6)
		if not unicodeBraille:
			pattern = unicodeBrailleToDescription(pattern)
		if "…" not in pattern:
			pattern += "…"
		if not unicodeBraille:
			pattern = pattern.replace("…", "-…")
		ord_ = ord(c)
		hexVal = hex(ord_)[2:][-4:].upper()
		if len(hexVal) < 4:
			hexVal = ("%4s" % hexVal).replace(" ", "0")
		if debug:
			print_(":hexVal:", c, hexVal)
		out_ = ""
		beg = ""
		for i, hex_digit in enumerate(hexVal):
			j = int(hex_digit, 16)
			if i % 2:
				end = translateHUC8(hexVals[j], debug)
				cleanCell = "".join(sorted(beg + end)).replace("0", "")
				if not cleanCell:
					cleanCell = "0"
				if debug:
					print_(":cell %d:" % ((i + 1) // 2), cleanCell)
				out_ += cleanCell
			else:
				if i != 0:
					out_ += "-"
				beg = hexVals[j]
		if HUC6:
			out_ = translateHUC6(out_, debug)
			if ord_ <= 0xFFFF:
				toAdd = "3"
			elif ord_ <= 0x1FFFF:
				toAdd = "6"
			else:
				toAdd = "36"
			lastCellMatch = _RE_LAST_HUC6_CELL.search(out_)
			lastCell = lastCellMatch.group(1) if lastCellMatch else ""
			newLastCell = "".join(sorted(toAdd + lastCell)).replace("0", "")
			out_ = _RE_LAST_HUC6_CELL.sub("-" + newLastCell, out_)
		if unicodeBraille:
			out_ = cellDescriptionsToUnicodeBraille(out_)
		out_ = pattern.replace("…", out_.strip("-"))
		if out and not unicodeBraille:
			out += "-"
		out += out_
	return out


def splitInTwoCells(dotPattern):
	c1 = ""
	c2 = ""
	for dot in dotPattern:
		if dot in ["3", "6", "7", "8"]:
			c2 += dot
		elif dot in ["1", "2", "4", "5"]:
			c1 += dot
	if c2:
		c2 = translateHUC8(c2)
	if not c1:
		c1 = "0"
	if not c2:
		c2 = "0"
	return [c1, c2]


def isValidHUCInput(s):
	if not s:
		return HUC_INPUT_INCOMPLETE
	if len(s) == 1:
		if any(k.startswith(s) for k in HUC8_patterns):
			return HUC_INPUT_INCOMPLETE
		return HUC_INPUT_INVALID
	prefix = s[0:2] if len(s) == 4 else s[0]
	s = s[2:] if len(s) == 4 else s[1:]
	size = len(s)
	if prefix not in HUC8_patterns:
		if s and (prefix + s[0]) in HUC8_patterns:
			return HUC_INPUT_INCOMPLETE
		return HUC_INPUT_INVALID
	if size < 2:
		return HUC_INPUT_INCOMPLETE
	if size == 2:
		return HUC_INPUT_COMPLETE
	return HUC_INPUT_INVALID


def backTranslateHUC8(s, debug=False):
	if len(s) not in (3, 4):
		raise ValueError("Invalid size")
	prefix = s[0:2] if len(s) == 4 else s[0]
	s = s[2:] if len(s) == 4 else s[1:]
	if prefix not in HUC8_patterns:
		raise ValueError("Invalid prefix")
	out = []
	s = unicodeBrailleToDescription(s)
	for c in s.split("-"):
		out += splitInTwoCells(c)
	return chr(HUC8_patterns[prefix][0] + int("".join(["%x" % hexVals.index(out) for out in out]), 16))


def backTranslateHUC6(s, debug=False):
	return "⠃"


def backTranslate(s, HUC6=False, debug=False):
	func = backTranslateHUC6 if HUC6 else backTranslateHUC8
	return func(s, debug=debug)


if __name__ == "__main__":
	t = input("Text to translate: ")
	print("HUC8:\n- %s\n- %s" % (translate(t), translate(t, unicodeBraille=False)))
	print("HUC6:\n- %s\n- %s" % (translate(t, HUC6=True), translate(t, HUC6=True, unicodeBraille=False)))
