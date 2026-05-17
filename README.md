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

1. Install the add-on package (or from the NVDA Add-on Store when it is listed there).
2. Open settings: **NVDA menu → Braille Extender → Settings…**.
3. Assign commands: **NVDA → Preferences → Input gestures → Braille Extender** for global shortcuts, and use **Gestures for this display…** when you want to see what your braille profile defines.
4. On **NVDA 2024.3+**, open **Custom braille tables…** from the Braille Extender submenu if you want your own Liblouis tables (copy an existing table or start from an empty file).
5. Open **User guide** once from the menu if you want the same information in a separate window while you use NVDA.

---

## How Braille Extender relates to NVDA

Braille Extender used to cover a lot of ground that **NVDA did not do yet** in braille. The first public release was **August 2017**, the same week as **NVDA 2017.3**, which is the version that best matches that moment in time.

NVDA’s own **Settings → Braille** (and related panels) have since gained options many people once relied on the add-on for. Braille Extender still adds extra behavior; check NVDA’s **release notes** if you want the exact wording for each item below.

| From NVDA | Now in NVDA core (summary) |
|-----------|----------------------------|
| **2022.3** | **Interrupt speech** when scrolling the braille display. |
| **2024.2** | **`NVDA+Alt+t`** toggles **braille mode**; new **display speech output** mode (braille mirrors what NVDA speaks). |
| **2024.3** | **Unicode normalization** for speech and braille; **custom braille tables** (add-on and scratchpad directories, `brailleTables.addTable`). Braille Extender registers its own tables here and resolves paths for any NVDA-registered table—not only built-in `louis/tables`. |
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
| **Document formatting** | Braille mirrors/overrides for NVDA document formatting (see [Detailed topics](#document-formatting)). |
| **Object Presentation** | **Order properties** (name, state, value, role text, description, shortcuts, position, table coords, …), **selected** marking (dots 7/8 or tags), **progress bar** style, **background** progress rules. |
| **Braille tables** | Preferred input/output table lists, optional automatic tables on NVDA 2025.1+, shortcut input table, **Additional Liblouis output pass**, tabs as spaces, **Manage custom braille tables…** (opens the custom-tables dialog; NVDA 2024.3+). |
| **Undefined character representation** | How characters missing from the table appear (HUC8, numeric bases, custom patterns, descriptions). |
| **Advanced input mode** | Escape sign and exit-after-one-character (abbreviation dictionary is a separate menu dialog—see [Documentation in NVDA](#documentation-in-nvda)). |
| **One-handed mode** | Enable and choose one of three one-hand input methods. |
| **Role labels** | Custom braille labels for roles, landmarks, and states. |
| **Advanced** | Compatibility toggles (cursor fixes, hide dots 7–8, foreground refresh on name changes). |

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
- **Terminals (braille follows review):** when **on**, entering a **terminal** (classic console role, or **Windows Terminal**’s window) makes **braille follow the review cursor**, keeps the **review cursor aligned with the text caret**, and refreshes braille when the **caret moves**, even when NVDA would usually switch braille back to the focused control—so line-based keys act on the terminal text. When you **leave** the terminal, the add-on stops this behavior and returns to your normal NVDA braille settings. **Off** if you prefer stock NVDA behavior. **Does not apply** on the secure desktop when NVDA blocks the check, or when **braille mode** is set to follow speech output only.
- **Routing in edit fields:** **normal** passes the key to NVDA; **emulate arrows** sends Home/End or repeated Left/Right so the caret jumps to the braille cell under the router (optional **beeps**). This applies when you are on the usual braille view, the system caret has **focus**, and you are in a **terminal** or **editable text** field.
- **Announce character when routing braille cursor:** when enabled, after **routing** the add-on speaks the **character under the routing cursor** using NVDA’s speech-symbol rules. On **NVDA 2024.4+** this checkbox is **disabled** in favor of NVDA **Braille → Speak character when routing cursor in text** (same idea).
- **Speech interrupt for unknown gestures:** checkbox that is saved in your profile; the current add-on code **does not read** this setting, so changing it has **no effect** (reserved for a possible future use).
- **Unicode tools:** commands (assign in **Input gestures**) work on **selected text** in a **browse mode** document when a selection exists; if there is no selection, they use the **navigator object’s name** (the same object the **review cursor** is on—select text or move the review cursor first). They convert between **plain text and Unicode braille** (e.g. **z** ↔ **⠵** depending on table) and between **Unicode braille and dot numbers**.

### Braille tables

- **Rotation lists:** your **input** and **output** table lists are **names in order, separated by commas**. The **next/previous table** commands move through that order (assign them in **Input gestures** if your display profile does not already). **Custom Braille Extender tables are not listed here**—choose them only in the custom braille tables dialog (see below).
- **Automatic table row:** On **NVDA 2025.1+**, you can include **automatic** entries; the add-on resolves them with NVDA’s language-based default tables. On older NVDA, **auto** is not supported the same way—use explicit table files.
- **Shortcut input table:** optional separate table used for certain shortcuts.
- **Additional Liblouis output pass:** optional second output table applied after the main translation (same list as output tables, including custom tables when registered). This is the same option as **postTable** in your profile (sometimes called a post-output pass in older descriptions).
- **Tabs as spaces:** show tab characters as a run of spaces; **tab width** is per active display (range **1–42**).
- **Manage custom braille tables…:** opens the custom-tables dialog (see below).

**Table dictionaries** (not in settings tabs)

Three layers are combined when the add-on loads: **Global** (`default`, all tables), **Table** (for the current **output** table file), and **Temporary** (`tmp`, short-lived overrides). If a dictionary file has errors, that layer is skipped until you fix it.

Open **NVDA menu → Braille Extender → Table dictionaries** → **Global dictionary**, **Table dictionary**, or **Temporary dictionary**.

#### Custom braille tables (NVDA 2024.3+)

Braille Extender can **register your own Liblouis tables** with NVDA and use them everywhere the add-on builds a table chain: braille output, input, **rotation lists**, the **additional output pass**, and **table dictionaries**.

**Requirements**

- **NVDA 2024.3 or later** (same baseline as NVDA’s custom braille table API).
- Table files use a primary Liblouis extension: **`.utb`**, **`.ctb`**, or **`.tbl`** (not auxiliary `.cti` / `.dis` files).

**Where to open the manager**

| Location | Use |
|----------|-----|
| **NVDA menu → Braille Extender → Custom braille tables…** | Dedicated dialog (list and all actions). |
| **Braille Extender settings → Braille tables → Manage custom braille tables…** | Opens the same dialog. |

**What you can do**

| Action | Description |
|--------|-------------|
| **Add…** | **Copy from an existing table** or **create an empty table** with a minimal starter rule file. The copy list includes built-in NVDA tables, tables from other add-ons, and **your Braille Extender custom tables** (after they are registered). Set display name, contracted, and input/output flags in the next dialog. |
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

Only the table(s) you select here are registered with NVDA. They **do not** appear in **NVDA → Settings → Braille** or in Braille Extender’s preferred rotation lists, so NVDA can restart safely if the add-on is not loaded.

Press **OK** to apply your choice. To stop using custom tables, set both lists to **None** (files are kept). To delete tables permanently, use **Remove** in the manager.

**Storage**

- **Table files:** `%NVDA_USER_CONFIG%\brailleExtender\customBrailleTables\`
- **Metadata (names and flags):** `%NVDA_USER_CONFIG%\brailleExtenderCustomTables.json`

After you add, remove, or change tables, the add-on **reloads the Liblouis chain** so braille updates immediately.

**Using custom tables day to day**

1. Add the table (**Add… → Copy from an existing table**, or **create an empty table**).
2. In **Properties**, allow it for **input** and/or **output** (capabilities of the table file).
3. Set **Active custom input table** and/or **Active custom output table** to that table (or leave **None** for that direction).
4. Press **OK**. New tables are selected automatically for the directions you enabled when you add them.

**NVDA settings when the add-on is disabled**

Custom tables registered only by Braille Extender are **not** written into NVDA’s core `braille.inputTable` / `braille.translationTable` keys (which would break if the add-on were unloaded). The add-on keeps your real choice in **`brailleExtender.activeInputTable`** and **`brailleExtender.activeOutputTable`**, while NVDA’s config stays on **automatic** or a built-in table. When you load Braille Extender again, your custom selection is restored.

**Tables from other add-ons (NVDA 2024.3+)**

You do **not** need to copy a table into Braille Extender’s folder to use it. If another add-on (or the scratchpad) registers tables with NVDA—such as **Experimental braille tables**—Braille Extender resolves them through NVDA’s registry and `_tablesDirs`, the same as built-in tables. Use them in rotation lists, as the active NVDA table, or as the **additional output pass**. On **NVDA 2024.1–2024.2**, only built-in tables under `louis/tables` are supported.

**If a table file is missing**

The add-on logs a warning, falls back to a safe default where needed, and can reset references (preferred lists, additional output pass, shortcuts) so NVDA does not stay pointed at a broken file.

### Document formatting

Braille Extender does **not** replace NVDA’s **Document formatting** dialog. It adds a **separate braille presentation** step on top of NVDA’s choices:

- **Per-row mode:** for each report row, typically **Follow NVDA** (same toggles as NVDA Document formatting—speech **and** braille, not speech alone), **Always in braille** (force on the display, with **Methods** / **Tags** where applicable), or **Off** for that row in this layer.
- **Plain text:** show content without the usual structure chrome from this layer.
- **Line by line:** braille is built **line-at-a-time** for the reading unit.
- **Alignments:** for **left / center / right / justified**, choose **none**, **line padding** (leading blanks on the physical line), **dot 7/8/78**, **tags**, or legacy **spacing** (treated like line padding where relevant).
- **Methods:** for font-like attributes (**bold**, **italic**, **underline**, **strikethrough**, **strong**, **emphasised**, **marked**, sub/superscript, spelling/grammar flags) choose **none**, **dots 7/8**, **tags**, etc. NVDA’s own spelling/grammar attributes can still be driven by NVDA when you use **Follow NVDA** on those rows.
- **Lists:** options such as **show level** for list items.
- **Tags:** configurable **start/end** strings (defaults often `[` / `]`) for tag-style markers.
- **Report options:** a long list of choices (alignment names, colors, links, tables, line numbers, spelling, …) aligned with NVDA’s document-formatting categories—each can follow NVDA, always show in braille, or stay off.
- **Excel cell formulas:** when **on**, if a cell reports **has formula** and a formula string exists, the **formula** can be moved into the **description** field for braille so the state line is not overloaded (states are adjusted accordingly).

On **NVDA 2024.4+**, NVDA adds its own global braille formatting choices; Braille Extender still offers this row-by-row layout, tags, padding, and methods.

### Object presentation

**Order properties**

Controls the **left-to-right sequence** of pieces on the braille line when NVDA shows a **single object’s summary** (focus/context): **state**, **table cell coordinates**, **value**, **name**, **role text**, **description**, **keyboard shortcut**, **position** (e.g. `3/10`), **outline level** (`lv n`), **current** markers (for example “current page” on the web), **placeholder**, and similar fields.

- Open **Object presentation → Order Properties…** to move lines up/down. Buttons reset to **NVDA’s default order** or the **add-on default** (add-on default puts **states** and **cell coordinates** ahead of **name** for quicker scanning).
- Only properties that **exist** for the current object are shown; empty pieces are skipped.
- **Description**, **shortcut**, **position**, and **cell coordinates** still respect NVDA’s own presentation toggles (e.g. “report descriptions”) or the add-on’s document-formatting **report** for table cell coordinates—if NVDA omits them, they are not magically recreated here.
- **Math:** if the object is **math** and NVDA can provide math braille, that content can be **added after** the usual summary.
- **Visited links:** visited state may be folded into shorter **role text** (e.g. “vlnk”) so the state list stays compact.

**Selected element marking**

How to **highlight the current selection** in braille: **none**, **dot 7**, **dot 8**, **dots 7 and 8**, or **tags**. When this is **not none** and a **name** is present, **selected** / **selectable** states are dropped from the **state** text so you do not hear redundant “selected” next to dots 7–8 marking.

**Progress bar output**

Matches the choices in **Object presentation** settings:

- **Disabled:** same idea as NVDA’s usual progress reporting.
- **Enabled, raw value:** shows the underlying value as a **temporary braille message** while the bar updates. NVDA may still **speak** progress according to its own **Progress bar updates** settings; this add-on option does not drive speech by itself.
- **Enabled, bar:** a row of **⣿** cells whose length reflects the percentage across your **display width** (very long percentage text is shortened).

**Background progress windows**

These choices work together with NVDA’s **Report background progress bars** setting: you can match NVDA, always allow background bars, or **foreground only** so braille is not filled by progress bars for windows you are not working in.

### Undefined character representation

Characters **not defined** in the active output table (including many **emoji**) use the chosen **method**: table default, full **1–8** or **1–6** dot cell, **empty**, custom **dot pattern** (`6-123456` style), **question mark**, custom **sign** (`??` style), **hex** (Liblouis, **HUC8**, **HUC6**), **decimal**, **octal**, **binary**.

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

### Current character information

Uses the character at the **review cursor** (navigator). The **braille cells** in the report are produced with your **current output translation table** (the same Liblouis chain used for on-screen braille, including table dictionaries when they apply)—not the separate **input** table. One press: short summary; double press: **browseable** block.

**Example** (“.”):

```text
.: 0x2e, 46, 0o56, 0b101110
dot (FULL STOP [Po])
⠲ (256)
⣥⣺⢃, ⠿⠺⠏⠔
```

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
- **Routing:** key **0** copies the current line; key **`displaySize − 1`** opens **browseable** text; **middle keys** jump by a distance that depends on **left vs right of center** on the display.

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

- **Fix cursor positions:** helps in awkward controls by cleaning up **combining Unicode symbols** next to letters so braille and the routing cursor line up more reliably.
- **Hide dots 7–8:** toggle (assign **Input gestures → Braille Extender** if you want a shortcut) that **clears dots 7 and 8** from braille cells when NVDA is **not** showing an in-line **text selection** on that line—useful for a flatter view with **contracted** braille (NVDA describes this command as hiding dots 7–8 in contracted output).
- **Refresh when object name changes:** when enabled, a **name-change** event causes the add-on to **refresh braille for the foreground window**—useful when **titles or labels** update often (timers, live counters) so the display does not look stuck.

---

## Feature highlights

- Reload two **favorite braille displays** with shortcuts.
- **Terminals:** braille can follow the **review cursor** while you edit (PuTTY, PowerShell, cmd, bash, …).
- **Auto scroll** with timing and blank-line options.
- **Multiple input/output tables** and **automatic** selection on NVDA 2025.1+.
- **Custom braille tables** (add, copy, edit) on NVDA 2024.3+; full use in rotation lists and the additional output pass.
- **Dots 7/8**, **tags**, and spacing / line padding for structure and attributes.
- **Additional Liblouis output pass** (second translation table after the main output table).
- **Tabs as spaces**; **reverse** scroll buttons.
- **Speak current line** while scrolling (coordinate with NVDA’s braille speech options).
- **Unicode braille** and **cell-description** tools for the selection.
- **Lock** braille keyboard; **lock modifiers** from braille.
- **Quick launches** and **table dictionaries** (NVDA menu → Braille Extender).
- **One-handed** input; **undefined characters** (including emoji); **advanced input** and abbreviations.
- **Speech History Mode**; extended **display gesture** maps where profiles exist.

---

## Gestures and profiles

- **Keyboard:** listed under **Input gestures → Braille Extender**. **Gestures for this display…** shows a live list for your **current** braille profile and add-on keyboard bindings.
- **Braille display:** some displays ship with a predefined map for this add-on. If yours does not, assign the commands you need in **Input gestures** like any other NVDA command.

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
