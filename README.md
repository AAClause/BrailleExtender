# Braille Extender

NVDA add-on that extends braille output, input, scrolling, and display-specific gestures.

- **Authors:** André-Abush Clause and contributors
- **License:** GNU General Public License v2
- **Stable build:** [Download (stable channel)](https://andreabc.net/projects/NVDA_addons/BrailleExtender/latest)
- **Development build:** [Download (dev channel)](https://andreabc.net/projects/NVDA_addons/BrailleExtender/latest?channel=dev)
- **Source:** [GitHub — BrailleExtender](https://github.com/aaclause/BrailleExtender/)

**Minimum NVDA:** 2024.1

After you install the add-on, you can read this same guide from NVDA: use **User guide** under Braille Extender in the NVDA menu, or open **Help** from Add-ons Manager when Braille Extender is selected.

---

## Table of contents

1. [Documentation in NVDA](#documentation-in-nvda)
2. [Quick start](#quick-start)
3. [How Braille Extender relates to NVDA](#how-braille-extender-relates-to-nvda)
4. [Settings categories (overview)](#settings-categories-overview)
5. [Detailed topics](#detailed-topics)
6. [Feature highlights](#feature-highlights)
7. [Gestures and profiles](#gestures-and-profiles)
8. [Feedback and contributing](#feedback-and-contributing)
9. [Acknowledgements](#acknowledgements)

---

## Documentation in NVDA

| What | Where |
|------|--------|
| **This guide (as a web page)** | **NVDA menu → Braille Extender → User guide**, or **Add-ons Manager → Braille Extender → Help**. |
| **Gestures for your display** | **NVDA menu → Braille Extender → Gestures for this display…** — a list based on your current braille display profile and the add-on’s keyboard shortcuts. |
| **Custom braille tables** | **NVDA menu → Braille Extender → Custom braille tables…** (NVDA 2024.3+), or **Braille Extender settings → Braille tables → Manage custom braille tables…**. |
| **Table dictionaries** | **NVDA menu → Braille Extender → Table dictionaries** (Global, Table, Temporary—not a settings tab). |
| **Quick launches** | **NVDA menu → Braille Extender → Quick launches…** (not a settings tab). |
| **Advanced input mode dictionary** | **NVDA menu → Braille Extender → Advanced input mode dictionary…** (not a settings tab). |
| **On the web** | This page on GitHub or the project site, if you are reading online. |

---

## Quick start

These steps are enough for most users. You do not need custom braille tables unless you want your own table files.

1. **Install** the add-on (`.nvda-addon` file, or the NVDA Add-on Store when it is listed there).
2. **User guide:** **NVDA menu → Braille Extender → User guide** opens this document in a browser. Use it while you explore settings and gestures. The [Documentation in NVDA](#documentation-in-nvda) table above lists other menu entries.
3. **Settings:** **NVDA menu → Braille Extender → Settings…** — review the tabs you care about (for example **General**, **Braille tables**, **Document formatting**).
4. **Gestures:** **NVDA → Preferences → Input gestures → Category: Braille Extender** — assign the commands you will use. **NVDA menu → Braille Extender → Gestures for this display…** shows what your current braille display profile already defines.

**Optional features** (only when you need them): custom braille tables (NVDA 2024.3+), table dictionaries, quick launches, advanced input mode, and more. They are **not** part of the default setup — see [Documentation in NVDA](#documentation-in-nvda) for menu paths, or the detailed sections below.

---

## How Braille Extender relates to NVDA

Braille Extender used to cover a lot of ground that **NVDA did not do yet** in braille. The first public release was **August 2017**, the same week as **NVDA 2017.3**, which is the version that best matches that moment in time.

NVDA’s own **Settings → Braille** (and related panels) have since gained options many people once relied on the add-on for. Braille Extender still adds extra behavior; check NVDA’s **release notes** if you want the exact wording for each item below.

| From NVDA | Now in NVDA core (summary) |
|-----------|----------------------------|
| **2022.3** | **Interrupt speech** when scrolling the braille display. |
| **2024.2** | **`NVDA+Alt+t`** toggles **braille mode**; new **display speech output** mode (braille mirrors what NVDA speaks). |
| **2024.3** | **Unicode normalization** for speech and braille; **custom braille tables** from add-ons and NVDA’s scratchpad folder. Braille Extender can add its own tables and use tables from other add-ons, not only NVDA’s built-in list. |
| **2024.4** | **Speak character when routing** in text; more **formatting in braille** choices (e.g. tags); **paragraph start** in braille when reading by paragraph; routing fixes. |
| **2025.1** | **Input and output tables** can follow NVDA’s **interface language**; **speak line or paragraph** when using braille **navigation** keys. |

---

## Settings categories (overview)

These match the tabs in **Braille Extender settings**:

| Category | Summary |
|----------|---------|
| **General** | Update channel, speak current line while scrolling, skip blank lines, smart Caps Lock, modifier/volume feedback, two favorite displays and reload, right margin, reverse scroll, terminals (braille follows review), routing cursor behavior, announce character when routing (until NVDA handles it). |
| **Rotor** | Which rotor items exist and their order. |
| **Auto scroll** | Delays and behavior for automatic braille scrolling. |
| **Speech History Mode** | History length, numbering, optional speech while browsing history. |
| **Document formatting** | How formatting (bold, links, alignment, …) appears in braille, on top of NVDA’s document formatting (see [Detailed topics](#document-formatting)). |
| **Object Presentation** | Order of name, state, value, and other fields on the focus line; highlight selection with dots 7/8; progress bar messages on the display. |
| **Braille tables** | Preferred input/output table lists, optional automatic tables on NVDA 2025.1+, shortcut input table, second translation pass, tabs as spaces, **Manage custom braille tables…** (NVDA 2024.3+). |
| **Undefined character representation** | How characters missing from the table appear (dots, numbers, descriptions, HUC, …). |
| **Advanced input mode** | Escape sign and exit-after-one-character (abbreviation dictionary is a separate menu dialog—see [Documentation in NVDA](#documentation-in-nvda)). |
| **One-handed mode** | Enable and choose one of three one-hand input methods. |
| **Role labels** | Custom braille labels for roles, landmarks, and states. |
| **Advanced** | Variation-selector cursor fix; refresh braille when the foreground object’s name changes. |

---

## Detailed topics

### General

- **Updates:** stable or development channel; automatic or manual checks (see also the add-on’s update settings).
- **Say current line while scrolling:** speaks the line when you pan the braille display—**focus**, **review**, **both**, or **off**. On **NVDA 2025.1+**, NVDA can also speak the line when using braille navigation keys; if you hear **double** announcements, turn off NVDA **Braille → Speak when navigating by line or paragraph** or reduce overlap here.
- **Interrupt speech while scrolling:** the add-on’s **Speech interrupt when scrolling on same line** checkbox is **disabled on NVDA 2022.3 and later**; use NVDA **Braille → Interrupt speech while scrolling** instead. On **older NVDA** you can still change the add-on checkbox.
- **Skip blank lines:** when panning by line, empty lines can be skipped.
- **Smart Caps Lock:** when this option is **on** and **Windows Caps Lock** is **on**, letters produced from the **braille keyboard** in an ordinary **text field** are **sent with swapped case** (each **A–Z** becomes the opposite case; other characters are unchanged). This only applies to normal typing, not when you are holding **modifier keys** for shortcuts. Turn it **off** if you want the braille table’s output exactly as translated, regardless of Caps Lock.
- **Modifier / volume feedback:** optional **braille**, **speech**, **both**, or **none** when modifier locks or volume change gestures are used; optional **beeps** with modifiers.
- **Two favorite displays:** pick two saved display names and use the reload gestures to **switch the active braille display** quickly.
- **Right margin:** per active braille display, in cells (up to **80** in your profile; the settings spin control may allow a higher value).
- **Reverse scroll buttons:** swaps which physical key means “scroll back” vs “scroll forward”.
- **Terminals (braille follows review):** when **on**, in a **terminal** (Command Prompt, PowerShell, PuTTY, **Windows Terminal**, and similar) braille **follows the review cursor** and stays aligned with the text you are editing, even when NVDA would usually tie braille to the focused control. When you leave the terminal, normal NVDA behavior returns. Turn **off** if you prefer NVDA’s default. Not available on the secure sign-in screen, or when braille is set to follow **speech output** only.
- **Routing in edit fields:** **normal** passes the key to NVDA; **emulate arrows** sends Home/End or repeated Left/Right so the caret jumps to the braille cell under the router (optional **beeps**). This applies when you are on the usual braille view, the system caret has **focus**, and you are in a **terminal** or **editable text** field.
- **Announce character when routing braille cursor:** when enabled, after **routing** the add-on speaks the **character under the routing cursor** using NVDA’s speech-symbol rules. On **NVDA 2024.4+** this checkbox is **disabled** in favor of NVDA **Braille → Speak character when routing cursor in text** (same idea).
- **Speech interrupt for unknown gestures:** for **braille display** keys with **no assigned command**, controls whether NVDA **stops speech** when you press them. **Checked** (default): unassigned keys interrupt speech like most NVDA keys. **Unchecked**: unassigned keys do **not** cancel speech. Does not apply to braille **typing** (dots/enter), volume keys, modifier emulation, or line scroll when the scroll-interrupt rule above allows speech to continue.
- **Braille keyboard configuration:** shown only when your display profile defines **keyboard layouts** (not all displays).
- **Unicode tools** (assign in **Input gestures**): work on **selected text** on a web page when you have a selection; otherwise on the text at the **review cursor**. Convert plain text ↔ Unicode braille and Unicode braille ↔ dot numbers.
- **Character information** (assign in **Input gestures**): at the review cursor, reports Unicode name, speech symbol, braille cells, and numeric bases; double-press for a browseable block.

### Braille tables

- **Rotation lists:** your **input** and **output** table lists are **names in order, separated by commas**. The **next/previous table** commands move through that order (assign them in **Input gestures** if your display profile does not already). **Custom Braille Extender tables are not listed here**—choose them only in the custom braille tables dialog (see below).
- **Automatic table row:** On **NVDA 2025.1+**, you can include **automatic** entries; the add-on resolves them with NVDA’s language-based default tables. On older NVDA, **auto** is not supported the same way—use explicit table files.
- **Shortcut input table:** optional separate table used for certain shortcuts.
- **Additional Liblouis output pass:** optional **second output table** applied after the main one (tables from your preferred output list; not inactive custom tables).
- **Tabs as spaces:** show tab characters as a run of spaces; **tab width** is per active display (range **1–42**).
- **Manage custom braille tables…:** opens the custom-tables dialog (see below).

**Table dictionaries** (not in settings tabs)

Three layers work together: **Global** (applies to all tables), **Table** (for the current **output** table), and **Temporary** (short-lived overrides until you restart NVDA). If a dictionary file has errors, that layer is skipped until you fix it.

Open **NVDA menu → Braille Extender → Table dictionaries** → **Global dictionary**, **Table dictionary**, or **Temporary dictionary**.

#### Custom braille tables (NVDA 2024.3+)

Braille Extender can **store and use your own braille tables** when you select them in the manager. They apply to braille **input** and **output** through the add-on (not through **NVDA → Settings → Braille** or the add-on’s table rotation lists).

**Requirements**

- **NVDA 2024.3 or later**.
- Table files must be **`.utb`**, **`.ctb`**, or **`.tbl`** (not helper files such as `.cti` or `.dis`).

**Where to open the manager**

| Location | Use |
|----------|-----|
| **NVDA menu → Braille Extender → Custom braille tables…** | Dedicated dialog (list and all actions). |
| **Braille Extender settings → Braille tables → Manage custom braille tables…** | Opens the same dialog. |

**What you can do**

| Action | Description |
|--------|-------------|
| **Add…** | **Copy from an existing table** or **create an empty table** with a minimal starter rule file. The copy list includes built-in NVDA tables, other add-ons’ tables, and tables already stored by Braille Extender. Set display name, contracted, and input/output flags in the next dialog. |
| **Remove** | Deletes metadata and the stored `.utb` / `.ctb` / `.tbl` file after confirmation. |
| **Edit…** | Opens the table file in your default editor (under the user storage folder below). |
| **Properties…** | Change display name, contracted, and whether the table is used for **input** and/or **output**. |

To **clone a custom table you already manage**, use **Add… → Copy from an existing table** and pick it from the list (same display name as in the custom-tables list).

**Add dialog**

- Choose **Copy from an existing table** (built-in, other add-ons, or your own custom tables) or **Create an empty table**.
- **Copy** keeps the source file extension (`.utb`, `.ctb`, or `.tbl`).
- **Create empty** writes a minimal starter file as **`.utb`**, or **`.ctb`** if you mark the table **contracted** in the properties step.

**Choosing which custom table to use**

At the top of the custom braille tables dialog:

| Control | Effect |
|---------|--------|
| **Active custom input table** | **None** (default) uses your normal NVDA input table. Pick a custom table to use it for braille input. |
| **Active custom output table** | **None** uses your normal NVDA output table. Pick a custom table to use it for braille translation. |

Only the table(s) you select here are active. They **do not** appear in **NVDA → Settings → Braille** or in Braille Extender’s table rotation lists, so NVDA can still start normally if the add-on is not loaded.

Press **OK** to apply your choice. To stop using custom tables, set both lists to **None** (files are kept). To delete tables permanently, use **Remove** in the manager.

**Storage**

Table files and a small settings file are saved in your **NVDA user configuration folder** ( **NVDA menu → Preferences → General → Open NVDA user configuration directory** ), under **brailleExtender\customBrailleTables\**.

After you add, remove, or change tables, braille **updates immediately**.

**Using custom tables day to day**

1. Add the table (**Add… → Copy from an existing table**, or **create an empty table**).
2. In **Properties**, allow it for **input** and/or **output** (capabilities of the table file).
3. Set **Active custom input table** and/or **Active custom output table** to that table (or leave **None** for that direction).
4. Press **OK**. New tables are selected automatically for the directions you enabled when you add them.

**If you turn the add-on off**

Your custom table choice is kept in Braille Extender’s own settings so NVDA’s braille settings stay on a safe built-in table. When you enable the add-on again, your custom selection comes back.

**Tables from other add-ons (NVDA 2024.3+)**

You do **not** need to copy a table into Braille Extender’s folder. Tables from another add-on (for example **Experimental braille tables**) or NVDA’s scratchpad work like built-in tables: add them to your **rotation lists**, switch to them with the table commands, or use them as the **additional output pass**. On **NVDA 2024.1–2024.2**, only NVDA’s built-in tables are supported.

**If a table file is missing**

The add-on falls back to a safe table where it can and clears broken entries from your lists so braille keeps working.

### Document formatting

Braille Extender does **not** replace NVDA’s **Document formatting** dialog. The **Document formatting** settings tab adds a separate braille layer:

- **Per category:** each row is **Follow NVDA document formatting**, **enabled**, or **disabled** (see the panel description at the top of the tab).
- **Plain text mode** — disable all text formatting from this layer.
- **Process formatting line per line** — build braille one line at a time.
- **Report rows** — one combo per category (font attributes, emphasis, alignment, colors, links, headings, lists, tables, cell coordinates, spelling/grammar, and others listed on the tab).
- **Cell formula (Excel only for now)** — when enabled, move a cell’s formula into the description field for braille when applicable.
- **Level of items in a nested list** — show list nesting level in braille.
- **Methods…** — per-attribute display (nothing, hand over to the table, dots 7/8, tags, line padding for alignments, etc.).
- **Tags…** — start/end tag strings used by tag-style methods.

On **NVDA 2024.4+**, NVDA also has global braille formatting options; this tab remains the add-on’s row-by-row control.

### Object presentation

This tab changes what appears on the braille display when NVDA shows **one object at a time**—the summary line for the focused control (button, link, table cell, and similar). It does **not** change how NVDA **speaks** object information; use NVDA **Settings → Object presentation** for speech options.

#### Order properties…

Open **Object presentation → Order Properties…** to set **which parts come first**, reading left to right on the display. Parts with no content for the current object are skipped.

You can reorder these fields (labels match the dialog):

- **name**, **value**, **state**, **role text** (type of control, for example heading level)
- **description**, **keyboard shortcut**, **position info** (shown as `3/10` in braille, not “3 of 10”)
- **position info level** (outline level, `lv 2`)
- **current labels** (for example “current page” on the web)
- **place-holder**, **cell coordinates text**

**Reset to the default NVDA order** — same order as NVDA without this add-on (name, then value, state, role text, and so on).

**Reset to the default add-on order** — puts **state** and **cell coordinates** before **name** (default for new profiles).

**What still follows NVDA**

- **Description**, **keyboard shortcut**, and **position** only appear if the matching options are enabled in NVDA **Settings → Object presentation**.
- **Cell coordinates** also follow **Braille Extender → Document formatting → Cell coordinates**.

**Excel:** with **Document formatting → Cell formula (Excel only for now)** enabled, a cell’s formula may appear in the description area instead of crowding the state line.

Row and column headers from the application may still be added after the main summary when available.

#### Selected elements

**Selected elements** controls how a **selected** item is marked on that object summary line:

| Choice | Effect |
|--------|--------|
| **nothing** | No extra marking from this add-on |
| **dot 7**, **dot 8**, or **dots 7 and 8** | Adds dots 7 and/or 8 to the braille cells that spell the object’s **name** |
| **tags** | Does not draw tag characters on the name; only affects state text as below |

When the choice is not **nothing** and the object has a **name**, the words **selected** and **selectable** are omitted from the **state** text so you are not told “selected” twice. Highlighting **inside running text** still follows NVDA’s own **show selection** setting.

#### Progress bar output using braille messages

When a progress bar’s value changes, the add-on can show a **short message on the braille display** (speech is unchanged—use NVDA **Settings → Object presentation → Progress bar updates** for speech):

| Option | What you see |
|--------|----------------|
| **disabled (original behavior)** | No extra braille messages from this add-on |
| **enabled, show raw value** | The bar’s value text (default) |
| **enabled, show a progress bar using ⣿** | A row of filled cells across the display, length based on the percentage |

#### Report background progress bars

The three choices (**Follow NVDA document formatting**, **enabled**, **disabled**) use the same wording as on the Document formatting tab, but here they only decide **which windows’** progress bars can trigger the braille messages above:

| Choice | Effect |
|--------|--------|
| **Follow NVDA document formatting** | Follows NVDA **Report background progress bars**, or shows bars in the window you are working in |
| **enabled** | Progress bars in background and foreground windows |
| **disabled** | Only progress bars in the **foreground** window |

### Undefined character representation

Characters **not defined** in the active output table (including many **emoji**) use the chosen **method**: **use braille table behavior**, full **1–8** or **1–6** dot cell, **empty**, custom **dot pattern** (for example `6-123456`), **question mark**, custom **sign** (for example `??`), **hex** (table style, **HUC8**, **HUC6**), **decimal**, **octal**, **binary**.

**Descriptions:** optional character **description**, **extended** description, **full extended**, optional **size** line, optional **Unicode data** as a last resort, and an **exclude** list (character codes or ranges) so description is skipped for ranges you find noisy.

**Precedence:** table rules and **table dictionaries** take priority over descriptions; descriptions take priority over the generic undefined pattern.

More on **HUC**: [danielmayr.at/huc](https://danielmayr.at/huc/)

### Advanced input mode

**Settings tab:** escape sign for numeric/Unicode input and **exit after one character**.

**Menu dialog:** **NVDA menu → Braille Extender → Advanced input mode dictionary…** — abbreviation entries per input table (separate from table dictionaries).

Toggle **advanced input** (defaults include **NVDA+Windows+i** or **⡊+space**). While active:

- **HUC8:** type the **Unicode HUC8 braille pattern** for the character; the add-on waits until the sequence is **valid and complete**, then inserts the character (many symbols need **about four** cells; some need **more**—see the [HUC](https://danielmayr.at/huc/) site). Works for **emoji** and other supported code points.
- **Numeric bases:** after the **escape** sign, send **⠭** or **⠓** (hex), **⠙** (decimal), **⠕** (octal), **⠃** (binary), type digits, then **Space**.
- **Abbreviations:** stored in the **advanced input mode dictionary** (menu dialog above; one entry per abbreviation and table). If you add the same abbreviation twice, the new text **replaces** the old one. Expand with **abbreviation + Space**.

**HUC6 input** is not implemented.

| Character | HUC8 | Hex | Decimal | Octal | Binary |
|-----------|------|-----|---------|-------|--------|
| 👍 thumbs up | ⣭⢤⡙ | 1F44D | 128077 | 372115 | 11111010001001101 |
| 😀 grinning face | ⣭⡤⣺ | 1F600 | 128512 | 373000 | 11111011000000000 |
| 🍑 peach | ⣭⠤⠕ | 1F351 | 127825 | 371521 | 11111001101010001 |
| 🌊 water wave | ⣭⠤⠺ | 1F30A | 127754 | 371412 | 11111001100001010 |

### One-handed mode

Compose a cell in several steps—useful if you type with one hand. In **Braille Extender settings**, the three methods appear in this order: **Fill a cell in two stages using one side only**, **Fill a cell in two stages using both sides**, **Fill a cell dots by dots**. Toggle one-handed mode with **NVDA+Windows+h** (often **⡂+space** on supported displays). If the stored method is unknown, the add-on speaks **unsupported** and clears any partly typed cell.

#### One side only (two steps on one bank; Space = empty half)

First step: dots **1–2–3–7**. Second step: **4–5–6–8**. **Space** means “this half is empty”. **Space twice** gives a completely empty cell.

- **⠛:** **1–2** then **1–2**, or **4–5** then **4–5**
- **⠃:** **1–2** then **Space**, or **4–5** then **Space**
- **⠘:** **Space** then **1–2**, or **Space** then **4–5**

#### Both sides (left bank, then right bank)

Type **left** bank dots, then **right** bank. If one side is empty, press the **same** dots twice, or enter the non-empty side in **two** steps.

- **⠛:** dots **1–2**, then **4–5**
- **⠃:** **1–2** then **1–2**, or **1** then **2**
- **⠘:** **4–5** then **4–5**, or **4** then **5**

#### Dot by dot (toggle)

Each key press **flips** a dot. Press **Space** when the cell is the one you want.

**⠛** can be built as: **1–2** then **4–5** then Space; or **1–2–3**, dot **3** again to correct, then **4–5**, Space; or **1**, then **2–4–5**, Space; and other paths.

### Speech History Mode

**Do not confuse this with NVDA’s shortcut for toggling braille mode (`NVDA+Alt+t`).**

In current NVDA (see **Commands Quick Reference → Braille** and **Input help**):

- **`NVDA+Alt+t`** — **Toggle braille mode** (shortcut documented since **NVDA 2024.2**, which added **display speech output** mode: braille can mirror what NVDA speaks). NVDA cycles its braille modes, including **display** vs **speech output**. That is still **not** Braille Extender’s separate **speech history list** and **routing** workflow.

**What Braille Extender does instead**

While **Speech History Mode** is **on**, the add-on **records what NVDA speaks** as plain-text lines you can browse, uses **line scroll** on the display to move through that list, and **switches the braille line** to show those lines instead of the usual focus or review text. Turning the mode **off** returns braille to normal and refreshes the display.

- **Assign a gesture:** the add-on does **not** ship a mandatory desktop shortcut—use **Input gestures → Braille Extender →** *Turn Braille Extender speech history mode on or off…* Many display profiles use a **gesture** such as **⡞+space**; use **Gestures for this display…** to see yours.
- **Gesture conflict:** avoid mapping this add-on command to **`NVDA+Alt+t`** unless you mean to **replace** NVDA’s **toggle braille mode** command on that key.
- **While browsing history:** speech is captured as **text only** (no sounds or tones in the list); the **forward/back** line commands move through stored lines when you are in this mode.
- **Limit:** how many lines to keep (the settings panel allows a very high maximum).
- **Number entries:** each line is prefixed with **`#`** and the **entry number** (padded with leading zeros so all numbers use the same width), then **`:`** and the text—for example **`#3:`** or **`#0003:`** depending on your history limit.
- **Speak entries:** optionally read the line aloud when you move in the history.
- **Routing:** the **leftmost** routing key copies the current line; the **rightmost** opens **browseable** text; **middle keys** jump forward or backward in the list depending on which side of the display you press.

### Rotor

The rotor switches **active quick-nav / review category**. Categories include **text navigation**, **selection**, **object / review**, **links** (visited/unvisited), **landmarks**, **headings** (per level), lists, form controls, **tables**, **same/different formatting**, **input/output table lists**, and more.

- **Settings:** enable/disable each category and set **master order**. Only **enabled** items appear when cycling.
- **Which categories appear:** in **browse mode–style** views (many web pages, similar documents, and some app views with quick navigation), the add-on **asks NVDA** whether each rotor type is supported; types that would always fail (for example some **formatting** jumps in certain **Word** views) are **hidden** so you are not stuck on “not supported”.
- **Gestures:** assign **next/previous rotor item** and **next/previous rotor set** in **Input gestures**; display profiles may already bind them.

### Auto scroll

When **auto scroll** is on, the display **advances by itself** on a timer while you stay on the usual braille view. If you switch to another view (for example speech history), auto scroll **pauses** until you return.

- **Delay:** stored **per braille display model**, between about **0.2 and 42 seconds** between steps (default about **3 seconds**).
- **Faster / slower keys:** each press changes the delay by a configurable step (roughly **25 ms** up to **7 s** per step, depending on settings).
- **Adjust to content:** the delay can shorten or lengthen based on **how much of the current line fits** on your display.
- **Ignore blank lines:** optional skip of empty lines while auto scrolling.
- **Beeps** when turning auto scroll on or off.

### Role labels

When **Use custom role labels** is checked, you can edit **role**, **landmark**, and **positive / negative state** labels per language from this panel (stored with your other Braille Extender settings). When unchecked, NVDA’s default labels apply.

### Advanced

- **Avoid cursor positions issues with some characters such as variation selectors** — improves braille alignment when certain Unicode characters (variation selectors) are next to letters.
- **Force the refresh of braille region related to foreground object** — updates the display when the focused item’s **name** changes often (timers, live counters, changing window titles).

---

## Feature highlights

- Reload two **favorite braille displays** with shortcuts.
- **Terminals:** braille can follow the **review cursor** while you edit (PuTTY, PowerShell, cmd, bash, …).
- **Auto scroll** with timing and blank-line options.
- **Multiple input/output tables** and **automatic** selection on NVDA 2025.1+.
- **Custom braille tables** (add, copy, edit) on NVDA 2024.3+; activate only from the custom-tables dialog (**None** = off).
- **Dots 7/8**, **tags**, and line padding for structure and attributes (document formatting **Methods**).
- **Hide/show dots 7 and 8** — command in **Input gestures** (not an Advanced settings checkbox).
- **Second translation pass** (optional extra output table after the main one).
- **Tabs as spaces**; **reverse** scroll buttons.
- **Speak current line** while scrolling (coordinate with NVDA’s braille speech options).
- **Unicode braille** and **cell-description** tools for the selection.
- **Lock** braille keyboard; **lock modifiers** from braille.
- **Quick launches** and **table dictionaries** (NVDA menu → Braille Extender).
- **One-handed** input; **undefined characters** (including emoji); **advanced input** and abbreviations.
- **Speech History Mode**; extended **display gesture** maps where profiles exist.

---

## Gestures and profiles

- **Keyboard:** listed under **Input gestures → Category: Braille Extender**. **Gestures for this display…** shows bindings for your **current** braille display profile (including display-specific keys when a profile exists).
- **Braille display:** some displays ship with a predefined gesture map. If yours does not, assign commands in **Input gestures** like any other NVDA command.
- **Not in settings tabs** (menu or Input gestures only): hide/show dots 7–8, lock braille keyboard, lock modifier keys, quick launches, table dictionaries, advanced input dictionary, custom braille tables manager, table overview, Unicode tools, character information, and others—search **Braille Extender** in Input gestures to browse them.

---

## Feedback and contributing

Bug reports, suggestions, and pull requests are welcome on [GitHub — BrailleExtender](https://github.com/aaclause/BrailleExtender/). If you change user-visible text or behavior, please update this guide and any translations you maintain so everyone stays in sync.

If you work on the **source code**, build steps and developer tooling are described in the repository on GitHub (not in this user guide).

---

## Acknowledgements

- **Copyright:** © 2016-2026 André-Abush Clause and other contributors — see [addon page](https://github.com/aaclause/BrailleExtender/).

### Translators

- **Arabic:** Ikrami Ahmad  
- **Chinese (Taiwan):** 蔡宗豪 Victor Cai &lt;surfer0627@gmail.com&gt;  
- **Croatian:** Zvonimir Stanečić &lt;zvonimirek222@yandex.com&gt;  
- **Danish:** Daniel Gartmann &lt;dg@danielgartmann.dk&gt;  
- **English and French:** Sof &lt;hellosof@gmail.com&gt;, Joseph Lee, André-Abush Clause &lt;dev@andreabc.net&gt;, Oreonan &lt;corentin@progaccess.net&gt;  
- **German:** Adriani Botez, Karl Eick, Rene Linke, Jürgen Schwingshandl  
- **Hebrew:** Shmuel Naaman, Afik Sofer, David Rechtman, Pavel Kaplan  
- **Italian:** Simone Dal Maso, Fabrizio Marini  
- **Persian:** Mohammadreza Rashad  
- **Polish:** Zvonimir Stanečić, Dorota Krać  
- **Russian:** Zvonimir Stanečić, Pavel Kaplan, Artem Plaksin  
- **Spanish:** Eric Duarte Quintanilla  
- **Turkish:** Umut Korkmaz  
- **Ukrainian:** VovaMobile  

### Code and third-party

- **Speech History Mode feature:** Emil Hesmyr &lt;emilhe@viken.no&gt;  
- **Maintenance / cleanup:** Joseph Lee &lt;joseph.lee22590@gmail.com&gt;  
- **Attribra** (third-party): Copyright © 2017 Alberto Zanella — [attribra](https://github.com/albzan/attribra/)  

Thanks also to Daniel Cotto, Daniel Mayr, Dawid Pieper, Corentin, Louis, and everyone who reported feedback.
