# Design: Edit Existing Logbook Entries & Sub-Entries

Date: 2026-07-02
Status: Approved

## Problem

Menu 3 ("Add New Logbook Entry") and menu 4 ("Add New Sub-Entry") skip checking existing entries and jump straight to add. User cannot edit existing entries/sub-entries from the CLI; must open SIMASTER web manually.

Additionally, the JOK (Jam Orang Kegiatan) auto-computed field formula in `prompt.py:132` is wrong:

```python
jok = 2 * int(audience) * 20_000  # WRONG: phantom 2x, ignores duration
```

Per SIMASTER form spec, JOK = `(Jumlah Masyarakat x Durasi dalam Jam x Rp.20.000)` where Durasi field is in minutes (divide by 60).

## Goals

1. Menu 3 & 4 show existing entries first, let user click a row to choose edit or add.
2. Edit mode fetches the SIMASTER edit form, parses existing values, prefills prompt defaults so user edits only what needs changing.
3. Fix JOK formula: `jok = audience * (durasi_menit / 60) * 20000`.
4. Unify add+edit into single code path (one function, branch by `edit_url` param) — DRY.

## Non-Goals

- Editing assisted (bantu) program entries/sub-entries (only main program for now).
- Bulk edit.
- Editing fields not exposed in current add form.

## Architecture

Extend existing add flow with edit mode. Single code path per function, branching by `edit_url` param. No separate edit functions.

```
User selects menu 3/4
    ↓
Show textual DataTable of existing entries/sub-entries
    ↓
User clicks row (Enter) → prompt (e)dit / (a)dd / (c)ancel
    ↓
e: fetch edit_url → parse form → prefill → prompt → POST edit
a: current add flow (cari 'Tambah' link)
c: abort
```

## Components

### 1. `src/datatypes.py` — add edit_url fields

```python
class SubEntryData(TypedDict, total=False):
    title: str
    date: str
    duration: str
    status: str
    is_attended: bool
    attendance_link: str | None
    edit_url: str | None          # NEW

class EntryData(TypedDict, total=False):
    entry_index: int
    activity_url: str
    edit_url: str | None          # NEW
    title: str
    date: str
    location: str
    sub_entries: list[SubEntryData]
    attendance_status: str
```

### 2. `src/utils/kkn.py` — parse edit URLs + unify add/edit

**Parse edit URLs during existing fetches:**

- In `get_logbook_entries_by_id` (entry parsing, ~line 228-241): after finding `kegiatan_url`, also search for `a[title='Ubah']` in the row → store as `EntryData["edit_url"]`.
- In sub-entry parsing (~line 244-269): search for `a[title='Ubah']` in `content_node` → store as `SubEntryData["edit_url"]`.
- Same for `_get_assisted_program` (out of scope for edit, but populate for consistency).

**Unify `add_logbook_entry`:**

```python
async def add_logbook_entry(
    self, program_id: str, data: LogEntryPayload, edit_url: str | None = None
):
    if not self.main_program or not (target := self.main_program.get(program_id)):
        return None

    try:
        if edit_url:
            # EDIT MODE: fetch edit form directly
            resp = await self.client.get(edit_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            form = tree.css_first("form#form-usulan-program")
            add_page_url = edit_url  # action URL parsed below
        else:
            # ADD MODE: current flow
            url = target["action"]
            resp = await self.client.get(url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            add_link_node = tree.css_first("a[title='Tambah']")
            # ... existing add flow ...
            add_page_url = add_link_node.attributes.get("href")
            resp = await self.client.get(add_page_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            form = tree.css_first("form#form-usulan-program")

        if not form:
            print_log("Could not find the form on the page.")
            return False

        action_url = form.attributes.get("action")
        form_data = {}
        for inp in form.css("input[type='hidden']"):
            name = inp.attributes.get("name")
            value = inp.attributes.get("value")
            if name:
                form_data[name] = value

        # Override with user data (prefilled existing values come from
        # the edit form's hidden inputs + visible inputs parsed separately)
        form_data["dParam[judul]"] = data["title"]
        form_data["dParam[pelaksanaan]"] = data["date"]
        form_data["dParam[lokasi]"] = f"{data['latitude']}, {data['longitude']}"

        resp = await self.client.post(action_url, data=form_data, follow_redirects=True)
        resp.raise_for_status()
        # ... existing response handling ...
```

**Unify `add_logbook_sub_entry`:**

```python
async def add_logbook_sub_entry(
    self, kegiatan_url: str, form_details: dict[str, str], edit_url: str | None = None
) -> bool:
    try:
        if edit_url:
            # EDIT MODE: fetch edit form directly
            resp = await self.client.get(edit_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            form = tree.css_first("form")
        else:
            # ADD MODE: current flow
            resp = await self.client.get(kegiatan_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            add_link_node = tree.css_first("a[title='Tambah']")
            add_form_url = add_link_node.attributes.get("href")
            resp = await self.client.get(add_form_url, follow_redirects=True)
            resp.raise_for_status()
            tree = HTMLParser(resp.content)
            form = tree.css_first("form")

        if not form:
            print_log("Could not find the form.", "ERROR")
            return False

        if not (action_url := form.attributes.get("action")):
            print_log("Couldn't find action url", "ERROR")
            return False

        form_data = {}
        for inp in form.css("input[type='hidden']"):
            name = inp.attributes.get("name")
            value = inp.attributes.get("value")
            if name:
                form_data[name] = value

        # In edit mode, also parse visible inputs to prefill (override-able
        # by form_details below)
        if edit_url:
            for inp in form.css("input[type='text'], input[type='number'], textarea"):
                name = inp.attributes.get("name")
                value = inp.attributes.get("value") or inp.text()
                if name:
                    form_data[name] = value

        form_data.update({
            "dParam[judul]": form_details.get("title", ""),
            "dParam[pelaksanaan]": form_details.get("datetime", ""),
            "dParam[durasi]": str(form_details.get("duration", "0")),
            "dParam[sasaran]": form_details.get("target", "-"),
            "dParam[jok]": form_details.get("jok", "0"),
            "dParam[jumPeserta]": form_details.get("audience", "0"),
            "dParam[deskripsi]": form_details.get("description", ""),
            "dParam[sumberDanaMulti][]": ["1"],
            "dParam[sumberDanaLainMulti][]": [""],
            "dParam[jumDanaMulti][]": [form_details.get("budget", "0")],
            "dParam[hasilKegiatan]": form_details.get("result", ""),
        })

        resp = await self.client.post(action_url, data=form_data, follow_redirects=True)
        resp.raise_for_status()
        # ... existing response handling ...
```

### 3. `src/ui/textual_table.py` — click row to select

Add Enter binding to return selected row data. The app needs a way to return the selection back to the caller (via `self.result` or similar).

```python
class ProgramTableApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("enter", "select", "Select"),
    ]

    def __init__(self, data: dict, title: str = "Program Utama", **kwargs):
        self._data = data or {}
        self._title = title
        self.result: dict | None = None  # set on select
        super().__init__(**kwargs)

    def action_select(self) -> None:
        table = self.query_one(DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        # look up row data by row_key (need to store mapping on populate)
        # set self.result and self.exit()
```

Need to store a mapping from row index → (entry/sub_entry dict) during `_populate_table` so `action_select` can return the right dict including `edit_url`.

Change `run_program_table` to return the selection:

```python
async def run_program_table(data: dict, title: str = "Program Utama") -> dict | None:
    if not data:
        print(f"No data found for {title}")
        return None
    app = ProgramTableApp(data=data, title=title)
    await app.run_async()
    return app.result
```

### 4. `src/ui/prompt.py` — prefill + fix JOK

**Fix JOK formula** (`prompt.py:132`):

```python
# BEFORE (wrong):
jok = 2 * int(audience) * 20_000

# AFTER (correct per SIMASTER spec):
jok = int(int(audience) * (int(duration) / 60) * 20_000)
```

**Add edit mode to `get_entry_details_from_user`:**

```python
def get_entry_details_from_user(
    data: RPPData, edit_mode: bool = False, existing: dict | None = None
) -> LogEntryPayload | None:
    # ...
    default_title = existing.get("title", "") if edit_mode else ""
    default_date = existing.get("date", datetime.now().strftime("%Y-%m-%d")) if edit_mode else datetime.now().strftime("%Y-%m-%d")
    entry_title = Prompt.ask("Enter the title for the logbook entry (Kegiatan)", default=default_title)
    activity_datetime = Prompt.ask("Enter date (YYYY-MM-DD)", default=default_date)
    # ... location handling, prefill from existing if available ...
```

**Add edit mode to `get_sub_entry_details_from_user`:**

```python
def get_sub_entry_details_from_user(
    data: RPPData, edit_mode: bool = False, existing: SubEntryData | None = None
):
    # ... existing list display ...
    if edit_mode and existing:
        sub_entry_title = Prompt.ask("Enter title", default=existing.get("title", ""))
        duration = Prompt.ask("Enter duration in minutes", default=str(existing.get("duration", "60")))
        # prefill datetime, target, audience, budget, description, result from existing
    else:
        # current add flow
    # JOK now auto-computed from audience + duration (fixed formula)
    jok = int(int(audience) * (int(duration) / 60) * 20_000)
```

Note: in edit mode, skip the sub-entry list selection step (the entry is already known from the clicked row). The function signature may need to accept the target entry directly instead of asking user to pick.

### 5. `src/actions.py` — manage flow

Replace `add_new_entry` and `add_new_sub_entry` with `manage_entry` and `manage_sub_entry`:

```python
async def manage_entry(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)
    await print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())
    # user picks program (existing)
    choice = await async_input(...)  # 1-N
    p_id = p_ids[choice - 1]

    # show entries table, user clicks row
    selection = await run_program_table({p_id: kkn.main_program[p_id]}, title="Program Utama")
    if not selection:
        return

    # prompt e/a/c
    mode = Prompt.ask("Edit existing or add new?", choices=["e", "a", "c"], default="a")
    if mode == "c":
        return

    if mode == "e":
        edit_url = selection.get("edit_url")
        if not edit_url:
            print_log("No edit URL available for this entry (may be locked).", "ERROR")
            return
        # prefill from selection (title, date, location)
        data = get_entry_details_from_user(kkn.main_program[p_id], edit_mode=True, existing=selection)
        if data:
            await kkn.add_logbook_entry(p_id, data, edit_url=edit_url)
            kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id]))
    else:  # add
        data = get_entry_details_from_user(kkn.main_program[p_id])
        if data:
            await kkn.add_logbook_entry(p_id, data)
            kkn.loader = asyncio.create_task(kkn.update_logbook_entries(programs=[p_id]))


async def manage_sub_entry(kkn: KKN):
    # similar: show entries → click row → e/a/c
    # e: fetch edit_url, prefill, call add_logbook_sub_entry(edit_url=...)
    # a: current add flow
```

### 6. `src/main.py` — dispatch

Update menu choices 3 & 4 to call `manage_entry` / `manage_sub_entry` (rename in `tui.py:print_choice`).

### 7. `src/ui/tui.py` — rename labels

```python
options = [
    "Post Daily Attendance",
    "Show Programs",
    "Manage Logbook Entry (My Program)",   # was "Add New Logbook Entry (My Program)"
    "Manage Sub-Entry (My Program)",        # was "Add New Sub-Entry (My Program)"
    "Post Attendance for Unattended Entries",
    "Generate Activity Timeline",
    "Change Account",
    "Refresh",
    "Exit",
]
```

## Data Flow

### Edit mode
1. User selects menu 3 or 4 → show program picker → show entries table
2. User presses Enter on a row → prompt `e/a/c`
3. `e` → read `edit_url` from selected entry/sub-entry dict
4. `get_entry_details_from_user(edit_mode=True, existing=selection)` → prefill defaults → user edits
5. `kkn.add_logbook_entry(p_id, data, edit_url=edit_url)` → fetch edit form → parse hidden + visible inputs → override with user data → POST
6. Background refresh entries

### Add mode (unchanged)
1. Same menu → show table → Enter on row → `a`
2. Current add flow (cari `a[title='Tambah']`)

## Error Handling

- **Edit URL missing** (`edit_url` is None on selection): log "No edit URL available (entry may be locked/attended)", abort.
- **Form not found** on edit page: log "Could not find edit form", abort.
- **Action URL missing**: log error, abort.
- **POST fails / non-success status**: log server response, return False (same as current add).
- **Network error**: catch `httpx.RequestError`, log, return False (same as current).

## Testing

Manual testing (no test framework in project):
1. Login, select menu 3, pick program, click row on existing entry, choose `e`, edit judul, submit, verify in SIMASTER web that judul changed.
2. Same for menu 4 sub-entry: edit judul + audience, verify JOK auto-recomputed, verify in SIMASTER.
3. Add mode still works: choose `a`, add new entry/sub-entry.
4. Cancel (`c`) returns to menu without action.
5. Row with no `edit_url` (already attended): show error, abort gracefully.

## Out of Scope

- Editing assisted (bantu) program entries — only main program.
- Bulk edit.
- Editing fields beyond what current add form exposes.
- Visual companion (terminal-only).