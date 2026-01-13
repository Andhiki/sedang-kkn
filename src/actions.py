import asyncio
import getpass

import httpx
from rich import inspect

from ui.prompt import get_entry_details_from_user, get_sub_entry_details_from_user
from ui.tables import print_assisted_program, print_program_details, print_program_title
from ui.tui import console
from utils.common import async_input, filter_unattended_program, load_background
from utils.kkn import KKN
from utils.simaster import Simaster


async def show_all_program(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)
    print_program_details(kkn.main_program)
    print_assisted_program(kkn.assisted_program)


async def add_new_entry(kkn: KKN):
    """Option 3: Add a new logbook entry."""
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())

    choice = await async_input(
        f"Enter your choice [cyan]([#fab387]1[cyan]-[/]{len(p_ids)}[/])[/]",
        int,
        choices=[str(i + 1) for i in range(len(p_ids))],
    )

    p_id = p_ids[choice - 1]
    if data := get_entry_details_from_user(kkn.main_program[p_id]):
        await kkn.add_logbook_entry(p_id, data)
        kkn.loader = asyncio.create_task(kkn.update_logbook_entries(p_id))


async def add_new_sub_entry(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    print_program_title(kkn.main_program)
    p_ids = list(kkn.main_program.keys())

    choice = await async_input(
        f"Enter your choice [cyan]([#fab387]1[cyan]-[/]{len(p_ids)}[/])[/]",
        int,
        choices=[str(i + 1) for i in range(len(p_ids))],
    )

    p_id = p_ids[choice - 1]
    if result := get_sub_entry_details_from_user(kkn.main_program[p_id]):
        await kkn.add_logbook_sub_entry(result[0], result[1])
        kkn.loader = asyncio.create_task(kkn.update_logbook_entries(p_id))


async def handle_unattended_entries(kkn: KKN):
    await load_background("[blue]Background fetch in progress...[/]", kkn.loader)

    unattended_main = filter_unattended_program(kkn.main_program)
    unattended_assisted = filter_unattended_program(kkn.assisted_program)
    unattended = [*unattended_main, *unattended_assisted]

    if not unattended:
        console.print("[green]No unattended programs found![/]")
        return

    # TODO: Add logic to actually post attendance here
    inspect(unattended)


async def change_account() -> tuple[Simaster, httpx.AsyncClient, KKN] | None:
    new_username = input("Username: ")
    new_password = getpass.getpass()

    new_simaster = Simaster(new_username, new_password)
    if new_session := await new_simaster.login(verbose=True):
        new_kkn = KKN(new_session, new_simaster)
        return new_simaster, new_session, new_kkn

    return None
