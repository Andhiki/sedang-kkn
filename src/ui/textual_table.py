from rich import box
from rich.prompt import Prompt
from rich.table import Table
from textual import events
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Static
from ui.tui import console, print_log


class ClickSelectDataTable(DataTable):
  """DataTable that selects a row on single click (not just double-click/Enter)."""

  async def _on_click(self, event: events.Click) -> None:
    await super()._on_click(event)
    if self.cursor_type != "row":
      return
    meta = event.style.meta
    if "row" not in meta or "column" not in meta:
      return
    row_index = meta["row"]
    if row_index is None or row_index < 0 or row_index >= len(self._data):
      return
    row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
    self.post_message(DataTable.RowSelected(self, row_index, row_key))


def _build_row_map(data: dict) -> dict[int, dict]:
  """Flatten program entries/sub-entries into a 1-based row map."""
  row_map: dict[int, dict] = {}
  counter = 1
  is_assisted = False

  for key, value in data.items():
    program_label = key if is_assisted else value.get("title", "N/A")
    entries = value if is_assisted else (value.get("entries") or [])

    first_row = True
    for entry in entries:
      entry_title = entry.get("title", "N/A")
      for sub in entry.get("sub_entries", []):
        status = "Sudah Presensi" if sub.get("is_attended") else sub.get("status", "Belum Presensi")
        row_map[counter] = {
          **sub,
          "_entry": entry,
          "_type": "sub_entry",
          "_no": counter,
          "_program": program_label if first_row else "",
          "_entry_title": entry_title if first_row else "",
          "_status": status,
        }
        counter += 1
        first_row = False
        entry_title = ""

      if not entry.get("sub_entries"):
        row_map[counter] = {
          **entry,
          "_type": "entry",
          "_no": counter,
          "_program": program_label if first_row else "",
          "_entry_title": entry_title if first_row else "",
          "_status": "—",
        }
        counter += 1
        first_row = False

  return row_map


def _prompt_select_row(data: dict, title: str = "Program Utama") -> dict | None:
  """Fallback row selection using a simple numbered Rich list."""
  row_map = _build_row_map(data)
  if not row_map:
    print(f"No data found for {title}")
    return None

  table = Table(box=box.ROUNDED, title=title, expand=True)
  table.add_column("No", justify="center", style="#fab387", width=3)
  table.add_column("Program", style="#89b4fa")
  table.add_column("Entry", style="#cdd6f4")
  table.add_column("Sub-entry", style="#cdd6f4")
  table.add_column("Date", justify="center", style="#89b4fa")
  table.add_column("Duration", justify="center", style="#89b4fa")
  table.add_column("Status", justify="center")

  for row in row_map.values():
    table.add_row(
      str(row["_no"]),
      row.get("_program", ""),
      row.get("_entry_title", ""),
      row.get("title", "—"),
      row.get("date", "—"),
      row.get("duration", "—"),
      row.get("_status", "—"),
    )

  console.print(table)

  while True:
    raw = Prompt.ask("Select row number (or 'b' to go back)")
    if raw.lower().strip() == "b":
      return None
    try:
      choice = int(raw.strip())
    except ValueError:
      print_log("Invalid input. Enter a number or 'b'.", "ERROR")
      continue

    if choice not in row_map:
      print_log("Row number out of range.", "ERROR")
      continue

    return row_map[choice]


class ProgramTableApp(App):
  """Textual app for displaying scrollable KKN program tables with row selection."""

  CSS = """
  ClickSelectDataTable {
    height: 1fr;
    width: 1fr;
    scrollbar-size-vertical: 2;
    scrollbar-size-horizontal: 2;
  }
  .title {
    text-align: center;
    text-style: bold;
    padding: 1 2;
    color: #89dceb;
  }
  .hint {
    text-align: center;
    padding: 0 2;
    color: #cdd6f4;
  }
  """

  BINDINGS = [
    ("q", "quit", "Quit"),
    ("r", "refresh", "Refresh"),
    ("enter", "select", "Select row"),
    ("b", "back", "Back"),
  ]

  def __init__(self, data: dict, title: str = "Program Utama", **kwargs):
    self._data = data or {}
    self._title = title
    self.result: dict | None = None
    self.cancelled: bool = False
    self._row_map: dict[int, dict] = {}
    super().__init__(**kwargs)

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(self._title, classes="title")
    yield Static("↑↓ navigate  •  Enter/click to select  •  b back  •  q quit", classes="hint")
    yield ClickSelectDataTable(cursor_type="row")
    yield Footer()

  def on_mount(self) -> None:
    table = self.query_one(ClickSelectDataTable)
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
      entries = value if is_assisted else (value.get("entries") or [])

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

  def action_refresh(self) -> None:
    table = self.query_one(ClickSelectDataTable)
    table.clear()
    self._populate_table(table)

  def action_select(self) -> None:
    table = self.query_one(ClickSelectDataTable)
    row_index = table.cursor_row
    if row_index is None:
      return
    data = self._row_map.get(row_index + 1)
    if not data:
      return
    self.result = data
    self.exit()

  def action_back(self) -> None:
    self.cancelled = True
    self.result = None
    self.exit()

  def action_quit(self) -> None:
    self.cancelled = True
    self.result = None
    return super().action_quit()

  def on_click_select_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    """Handle Enter or single-click row selection."""
    row_index = event.cursor_row
    data = self._row_map.get(row_index + 1)
    if not data:
      return
    self.result = data
    self.exit()


async def run_program_table(data: dict, title: str = "Program Utama") -> dict | None:
  """Launch textual DataTable app, or fall back to a simple numbered list if TUI fails."""
  if not data:
    print(f"No data found for {title}")
    return None

  try:
    app = ProgramTableApp(data=data, title=title)
    await app.run_async()
    if app.cancelled:
      return None
    if app.result is not None:
      return app.result
  except Exception as e:
    print_log(f"TUI table failed, falling back to list mode: {e}", "WARN")

  return _prompt_select_row(data, title=title)
