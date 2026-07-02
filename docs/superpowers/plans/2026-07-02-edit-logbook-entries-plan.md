# Edit Logbook Entries & Sub-Entries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users inspect existing logbook entries/sub-entries via TUI table, choose edit or add, and edit them with prefilled values; also fix the JOK auto-calculation formula.

**Architecture:** Reuse existing add functions by adding an `edit_url` parameter that switches the form-fetching path. Capture edit URLs from SIMASTER HTML. Add row selection to the textual DataTable. Prompt functions gain an edit mode that prefills existing values.

**Tech Stack:** Python 3.12, httpx, selectolax, textual, rich

---

## File map

- `src/datatypes.py` — add `edit_url` fields to `EntryData` and `SubEntryData`.
- `src/utils/kkn.py` — parse edit URLs; modify `add_logbook_entry` and `add_logbook_sub_entry` to handle `edit_url`.
- `src/ui/textual_table.py` — add row selection and return the selected row data.
- `src/ui/tables.py` — ensure `print_program_entries` / `print_program_sub_entries` are still called where needed.
- `src/ui/prompt.py` — add edit mode + prefill; fix JOK formula.
- `src/actions.py` — rename/replace `add_new_entry` / `add_new_sub_entry` with `manage_entry` / `manage_sub_entry`.
- `src/main.py` — dispatch menu 3/4 to the new manage functions.
- `src/ui/tui.py` — rename menu labels to "Manage...".
- `docs/superpowers/specs/2026-07-02-edit-logbook-entries-design.md` — source spec.

---

## Task 1: Add edit_url to data types

**Files:**
- Modify: `src/datatypes.py`

- [ ] **Step 1: Add `edit_url` to `EntryData` and `SubEntryData`**

```python
class SubEntryData(TypedDict, total=False):
    title: str
    date: str
    duration: str
    status: str
    is_attended: bool
    attendance_link: str | None
    edit_url: str | None


class EntryData(TypedDict, total=False):
    entry_index: int
    activity_url: str
    edit_url: str | None
    title: str
    date: str
    location: str
    sub_entries: list[SubEntryData]
    attendance_status: str
```

- [ ] **Step 2: Verify no syntax errors**

Run:

```bash
uv run python -c "from src.datatypes import EntryData, SubEntryData; print('OK')"
```

Expected: prints `OK`.

---

## Task 2: Parse edit URLs from SIMASTER HTML

**Files:**
- Modify: `src/utils/kkn.py`

- [ ] **Step 1: Parse entry edit URL in `get_logbook_entries_by_id`**

Locate the entry-row block (~line 228-241). Add edit URL lookup:

```python
if len(cols) == 5 and first_col_text:
    kegiatan_url = None
    if link_node := cols[4].css_first("a[href*='logbook_kegiatan']"):
        kegiatan_url = link_node.attributes.get("href")

    edit_url = None
    if edit_node := cols[4].css_first("a[title='Ubah'], a[title='Edit']"):
        edit_url = edit_node.attributes.get("href")

    current_entry: EntryData = {
        "entry_index": int(cols[0].text(strip=True)),
        "activity_url": str(kegiatan_url),
        "edit_url": str(edit_url) if edit_url else None,
        "title": cols[1].text(strip=True),
        "date": cols[2].text(strip=True),
        "location": cols[3].text(strip=True),
        "sub_entries": [],
        "attendance_status": "Belum Presensi",
    }
```

- [ ] **Step 2: Parse sub-entry edit URL**

In the sub-entry block (~line 244-269), add:

```python
sub_edit_url = None
if sub_edit_node := content_node.css_first("a[title='Ubah'], a[title='Edit']"):
    sub_edit_url = sub_edit_node.attributes.get("href")

sub_data: SubEntryData = {
    "title": match.group("title").strip() if match else full_text,
    "date": match.group("datetime").strip() if match else "N/A",
    "duration": match.group("duration").strip() if match else "N/A",
    "status": status_text,
    "is_attended": is_attended,
    "attendance_link": attendance_link,
    "edit_url": str(sub_edit_url) if sub_edit_url else None,
}
```

Also add the same to assisted sub-entry parsing for consistency (optional).

- [ ] **Step 3: Verify import/lint**

Run:

```bash
uv run ruff check src/utils/kkn.py
```

Expected: no new errors beyond pre-existing import-resolution false positives.

---

## Task 3: Unify add/edit in `add_logbook_entry`

**Files:**
- Modify: `src/utils/kkn.py`

- [ ] **Step 1: Change signature**

```python
async def add_logbook_entry(self, program_id: str, data: LogEntryPayload, edit_url: str | None = None):
```

- [ ] **Step 2: Add edit branch at start**

Replace the first part of the function so it fetches the edit URL when provided, otherwise keeps the existing add flow.

```python
    if not self.main_program or not (target := self.main_program.get(program_id)):
        return None

    try:
        if edit_url:
            resp = await self.client.get(edit_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            form = tree.css_first("form#form-usulan-program")
            if not form:
                print_log("Could not find the edit form on the page.")
                return False
        else:
            url = target["action"]
            resp = await self.client.get(url, follow_redirects=True)
            resp.raise_for_status()

            tree = HTMLParser(resp.content)
            if not (add_link_node := tree.css_first("a[title='Tambah']")):
                print_log("Could not find 'Tambah' link on the RPP page.")
                return False

            add_page_url = add_link_node.attributes.get("href")
            assert add_page_url is not None
            resp = await self.client.get(add_page_url, follow_redirects=True)
            resp.raise_for_status()

            tree = HTMLParser(resp.content)
            if not (form := tree.css_first("form#form-usulan-program")):
                print_log("Could not find the add form on the page.")
                return False

        action_url = form.attributes.get("action")
        # ... rest unchanged ...
```

- [ ] **Step 3: Verify ruff**

```bash
uv run ruff check src/utils/kkn.py
```

---

## Task 4: Unify add/edit in `add_logbook_sub_entry`

**Files:**
- Modify: `src/utils/kkn.py`

- [ ] **Step 1: Change signature**

```python
async def add_logbook_sub_entry(self, kegiatan_url: str, form_details: dict[str, str], edit_url: str | None = None) -> bool:
```

- [ ] **Step 2: Add edit branch and prefill visible inputs**

```python
    try:
        if edit_url:
            resp = await self.client.get(edit_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            if not (form := tree.css_first("form")):
                print_log("Could not find the edit form.", "ERROR")
                return False
        else:
            resp = await self.client.get(kegiatan_url, follow_redirects=True)
            resp.raise_for_status()

            tree = HTMLParser(resp.content)
            if not (add_link_node := tree.css_first("a[title='Tambah']")):
                print_log("Couldn't find 'Tambah' link on the Kegiatan page.", "ERROR")
                return False

            if not (add_form_url := add_link_node.attributes.get("href")):
                print_log("Couldn't find form url in the Node", "ERROR")
                return False

            resp = await self.client.get(add_form_url, follow_redirects=True)
            resp.raise_for_status()

            tree = HTMLParser(resp.content)
            if not (form := tree.css_first("form")):
                print_log("Could not find the sub-entry form.", "ERROR")
                return False

        if not (action_url := form.attributes.get("action")):
            print_log("Couldn't find action url in the Node", "ERROR")
            return False

        form_data = {}
        for inp in form.css("input[type='hidden']"):
            name = inp.attributes.get("name")
            value = inp.attributes.get("value")
            if name:
                form_data[name] = value

        # In edit mode, also capture visible text/number/textarea defaults
        if edit_url:
            for inp in form.css("input[type='text'], input[type='number'], input[type='datetime-local'], textarea"):
                name = inp.attributes.get("name")
                if name:
                    form_data[name] = inp.attributes.get("value") or inp.text(strip=True)

        # ... keep the rest of form_data.update ...
```

- [ ] **Step 3: Verify ruff**

```bash
uv run ruff check src/utils/kkn.py
```

---

## Task 5: Fix JOK formula

**Files:**
- Modify: `src/ui/prompt.py`

- [ ] **Step 1: Replace incorrect formula**

Find line `jok = 2 * int(audience) * 20_000` and replace with:

```python
jok = int(int(audience) * (int(duration) / 60) * 20_000)
```

- [ ] **Step 2: Verify**

Run:

```bash
uv run python -c "print(int(5 * (60 / 60) * 20000))"
```

Expected: `100000`.

---

## Task 6: Add edit mode to prompt functions

**Files:**
- Modify: `src/ui/prompt.py`

- [ ] **Step 1: Update `get_entry_details_from_user` signature**

```python
def get_entry_details_from_user(
    data: RPPData, edit_mode: bool = False, existing: dict | None = None
) -> LogEntryPayload | None:
```

- [ ] **Step 2: Prefill entry fields from existing**

```python
    default_title = existing.get("title", "") if (edit_mode and existing) else ""
    default_date = (
        existing.get("date", datetime.now().strftime("%Y-%m-%d"))
        if (edit_mode and existing)
        else datetime.now().strftime("%Y-%m-%d")
    )
    entry_title = Prompt.ask("Enter the title for the logbook entry (Kegiatan)", default=default_title)
    activity_datetime = Prompt.ask("Enter date (YYYY-MM-DD)", default=default_date)

    # location prefill
    lat = default_lat
    long = default_long
    if edit_mode and existing and (loc := existing.get("location")):
        parts = loc.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                long = float(parts[1].strip())
            except ValueError:
                pass

    console.print(f"[blue]Current/default point: [yellow]([#fab387]{lat}[#89dceb],[/] {long}[/])[/]")
    use_coord = Confirm.ask("Use this location?", default=True)

    latitude = lat
    longitude = long
    if not use_coord:
        try:
            latitude = float(input("Enter new latitude: "))
            longitude = float(input("Enter new longitude: "))
        except ValueError:
            print_log("Invalid input for location. Using defaults...", "ERROR")
            latitude = float(default_lat)
            longitude = float(default_long)
```

- [ ] **Step 3: Update `get_sub_entry_details_from_user` signature**

```python
def get_sub_entry_details_from_user(
    data: RPPData, edit_mode: bool = False, entry: EntryData | None = None
):
```

- [ ] **Step 4: Skip entry selection when editing a known entry**

When `edit_mode` is True and `entry` is given, use that entry directly; otherwise keep the existing prompt to pick entry and sub-entry.

```python
    if edit_mode and entry:
        sub_entry = entry
        # when editing sub-entry, the caller also passes the target sub entry via existing_sub
    else:
        # existing selection logic
```

- [ ] **Step 5: Add `existing_sub` param for sub-entry prefill**

Add to signature:

```python
def get_sub_entry_details_from_user(
    data: RPPData,
    edit_mode: bool = False,
    entry: EntryData | None = None,
    existing_sub: SubEntryData | None = None,
):
```

Prefill all visible fields from `existing_sub`:

```python
    defaults = {}
    if edit_mode and existing_sub:
        defaults = {
            "title": existing_sub.get("title", ""),
            "duration": str(existing_sub.get("duration", "60")),
            "date": existing_sub.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")),
            "target": "-",
            "audience": "0",
            "budget": "0",
            "description": "",
            "result": "",
        }
        # datetime split from existing_sub["date"] if it contains space
        # ... handle gracefully ...

    sub_entry_title = Prompt.ask("Enter the title for the new logbook sub-entry (Kegiatan)", default=defaults.get("title", ""))
    duration = Prompt.ask("Enter the duration in minutes", default=defaults.get("duration", "60"))
    # ... etc with defaults
```

Because parsing the full sub-entry form is preferred for accurate prefill, keep `defaults` simple as fallback and let `kkn.py` override with actual edit-form values.

- [ ] **Step 6: Verify ruff**

```bash
uv run ruff check src/ui/prompt.py
```

---

## Task 7: Make textual table row-selectable

**Files:**
- Modify: `src/ui/textual_table.py`

- [ ] **Step 1: Store row index → data mapping and add selection**

```python
from datatypes import AssistedProgram, EntryData, RPPData
from ui.tui import print_log

class ProgramTableApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("enter", "select", "Select"),
    ]

    def __init__(self, data: dict, title: str = "Program Utama", **kwargs):
        self._data = data or {}
        self._title = title
        self.result: dict | None = None
        self._row_map: dict[int, dict] = {}
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        is_assisted = self._title.lower().startswith("program bantu")
        table.add_columns(
            "No",
            "PIC" if is_assisted else "Program",
            "Entry",
            "Sub-entry",
            "Date",
            "Duration",
            "Status",
        )
        self._populate_table(table)

    def _populate_table(self, table: DataTable) -> None:
        counter = 1
        is_assisted = self._title.lower().startswith("program bantu")

        for key, value in self._data.items():
            program_label = key if is_assisted else value.get("title", "N/A")
            entries = value if is_assisted else value.get("entries", [])

            first_row = True
            for entry in entries:
                entry_title = entry.get("title", "N/A")
                for sub in entry.get("sub_entries", []):
                    status = "Sudah Presensi" if sub.get("is_attended") else sub.get("status", "Belum Presensi")
                    table.add_row(
                        str(counter),
                        program_label if first_row else "",
                        entry_title if first_row else "",
                        sub.get("title", "N/A"),
                        sub.get("date", "N/A"),
                        sub.get("duration", "N/A"),
                        status,
                    )
                    self._row_map[counter] = {**sub, "_entry": entry, "_type": "sub_entry"}
                    counter += 1
                    first_row = False
                    entry_title = ""

                if not entry.get("sub_entries"):
                    table.add_row(
                        str(counter),
                        program_label if first_row else "",
                        entry_title if first_row else "",
                        "—",
                        entry.get("date", "N/A"),
                        "—",
                        "—",
                    )
                    self._row_map[counter] = {**entry, "_type": "entry"}
                    counter += 1
                    first_row = False

    def action_select(self) -> None:
        table = self.query_one(DataTable)
        coord = table.cursor_coordinate
        row_idx = table.cursor_row
        # row_map stores by 1-based counter; convert from row index
        data = self._row_map.get(row_idx + 1)
        if data:
            self.result = data
        self.exit()
```

- [ ] **Step 2: Update `run_program_table` to return result**

```python
async def run_program_table(data: dict, title: str = "Program Utama") -> dict | None:
    if not data:
        print(f"No data found for {title}")
        return None
    app = ProgramTableApp(data=data, title=title)
    await app.run_async()
    return app.result
```

- [ ] **Step 3: Verify ruff**

```bash
uv run ruff check src/ui/textual_table.py
```

---

## Task 8: Add manage_entry / manage_sub_entry actions

**Files:**
- Modify: `src/actions.py`

- [ ] **Step 1: Replace `add_new_entry` with `manage_entry`**

```python
async def manage_entry(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    await print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())

    choice = await async_input(
        HTML(
            f'Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(p_ids)}</num>) '
            f'<choice fg="ansimagenta">[{"/".join(str(i + 1) for i in range(len(p_ids)))}]</choice>: </delim>'
        ),
        int,
    )

    p_id = p_ids[choice - 1]

    selection = await run_program_table({p_id: kkn.main_program[p_id]}, title="Program Utama")
    if not selection:
        return

    if selection.get("_type") == "sub_entry":
        print_log("Please select a top-level entry row (not a sub-entry) for this menu.", "WARN")
        return

    mode = Prompt.ask("Mode", choices=["e", "a", "c"], default="a")
    if mode == "c":
        return

    edit_url = None
    if mode == "e":
        edit_url = selection.get("edit_url")
        if not edit_url:
            print_log("No edit URL available for this entry (may be locked).", "ERROR")
            return

    data = get_entry_details_from_user(
        kkn.main_program[p_id],
        edit_mode=(mode == "e"),
        existing=selection,
    )
    if data:
        await kkn.add_logbook_entry(p_id, data, edit_url=edit_url)
        kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id]))
```

- [ ] **Step 2: Replace `add_new_sub_entry` with `manage_sub_entry`**

```python
async def manage_sub_entry(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    await print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())

    choice = await async_input(
        HTML(
            f'Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>{len(p_ids)}</num>) '
            f'<choice fg="ansimagenta">[{"/".join(str(i + 1) for i in range(len(p_ids)))}]</choice>: </delim>'
        ),
        int,
    )

    p_id = p_ids[choice - 1]

    selection = await run_program_table({p_id: kkn.main_program[p_id]}, title="Program Utama")
    if not selection:
        return

    if selection.get("_type") != "sub_entry":
        print_log("Please select a sub-entry row for this menu.", "WARN")
        return

    mode = Prompt.ask("Mode", choices=["e", "a", "c"], default="a")
    if mode == "c":
        return

    entry = selection.get("_entry")
    edit_url = selection.get("edit_url") if mode == "e" else None

    if mode == "e" and not edit_url:
        print_log("No edit URL available for this sub-entry (may be locked).", "ERROR")
        return

    result = get_sub_entry_details_from_user(
        kkn.main_program[p_id],
        edit_mode=(mode == "e"),
        entry=entry,
        existing_sub=selection,
    )
    if result:
        await kkn.add_logbook_sub_entry(result[0], result[1], edit_url=edit_url)
        kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id], pool_size=2))
```

- [ ] **Step 3: Update imports**

```python
from prompt_toolkit import HTML
from rich.prompt import Prompt

from ui.prompt import get_entry_details_from_user, get_sub_entry_details_from_user, parse_selection
from ui.tables import print_assisted_program, print_program_details, print_program_title, print_unattended_program
from ui.textual_table import run_program_table
from ui.tui import console, print_log
```

- [ ] **Step 4: Verify ruff**

```bash
uv run ruff check src/actions.py
```

---

## Task 9: Update menu labels and dispatch

**Files:**
- Modify: `src/ui/tui.py`
- Modify: `src/main.py`

- [ ] **Step 1: Rename menu labels in `src/ui/tui.py`**

```python
options = [
    "Post Daily Attendance",
    "Show Programs",
    "Manage Logbook Entry (My Program)",
    "Manage Sub-Entry (My Program)",
    "Post Attendance for Unattended Entries",
    "Generate Activity Timeline",
    "Change Account",
    "Refresh",
    "Exit",
]
```

- [ ] **Step 2: Update dispatch in `src/main.py`**

```python
elif choice == "3":
    await actions.manage_entry(kkn_manager)
elif choice == "4":
    await actions.manage_sub_entry(kkn_manager)
```

- [ ] **Step 3: Verify syntax**

```bash
uv run python -c "from src import actions, main, ui.tui"
```

Expected: no errors.

---

## Task 10: Manual verification

**Files:**
- None (manual testing)

- [ ] **Step 1: Set up valid SIMASTER credentials**

Ensure `.env` has `SIMASTER_USERNAME` and `SIMASTER_PASSWORD`.

- [ ] **Step 2: Run the CLI and test edit entry**

```bash
uv run python -m src.main
```

1. Select menu 3.
2. Pick a program.
3. Navigate to an existing entry row and press Enter.
4. Choose `e`.
5. Edit the title, submit.
6. Log in to SIMASTER web and verify the title changed.

- [ ] **Step 3: Test edit sub-entry**

1. Select menu 4.
2. Pick a program.
3. Navigate to a sub-entry row and press Enter.
4. Choose `e`.
5. Change participants count or duration.
6. Verify JOK recomputed correctly in the summary table.
7. Verify in SIMASTER web.

- [ ] **Step 4: Test add mode still works**

Repeat menus 3 and 4, choose `a`, add a new entry/sub-entry, verify in SIMASTER.

- [ ] **Step 5: Test cancel**

Choose `c`; confirm no network request is sent.

- [ ] **Step 6: Run ruff on all modified files**

```bash
uv run ruff check src/datatypes.py src/utils/kkn.py src/ui/prompt.py src/ui/textual_table.py src/actions.py src/main.py src/ui/tui.py
```

Expected: no new errors beyond pre-existing import-resolution false positives.

---

## Spec coverage self-check

| Spec requirement | Task(s) |
|---|---|
| Add `edit_url` to datatypes | 1 |
| Parse edit URLs from SIMASTER HTML | 2 |
| Unify add/edit functions with `edit_url` param | 3, 4 |
| Fix JOK formula | 5 |
| Prefill edit prompts with existing values | 6 |
| TUI table row selection | 7 |
| Replace actions with manage flow | 8 |
| Rename menu labels + dispatch | 9 |
| Manual verification | 10 |

No placeholders remain.