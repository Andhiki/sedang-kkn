import asyncio
import os

from dotenv import load_dotenv
from prompt_toolkit import HTML
from tap import Tap

import actions
from ui.tui import console, print_choice, print_log, print_title, prompt_session
from utils.attendance import handle_attendance, handle_check_status
from utils.common import async_input
from utils.kkn import KKN
from utils.simaster import Simaster

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"


class Parser(Tap):
  submit: bool = False  # Submit your attendance
  check: bool = False  # Check whether if you have logged in or not

  def configure(self):
    self.add_argument("-s", "--submit")
    self.add_argument("-c", "--check")


async def main_async(username: str, password: str):
  simaster_acc = Simaster(username, password)

  if not (session := await simaster_acc.login(verbose=True)):
    return

  kkn_manager = KKN(session, simaster_acc)

  first = True
  while True:
    print_title() if not first else print()
    first = False

    print_choice()
    choice = await async_input(
      HTML('Enter your choice <delim fg="#89dceb">(<num fg="#fab387">1<dash fg="#89dceb">-</dash>9</num>): </delim>')
    )
    print()

    try:
      if choice == "1":
        handle_attendance(username, password, "check_in")
      elif choice == "2":
        await actions.show_all_program(kkn_manager)
      elif choice == "3":
        await actions.add_new_entry(kkn_manager)
      elif choice == "4":
        await actions.add_new_sub_entry(kkn_manager)
      elif choice == "5":
        await actions.handle_unattended_entries(kkn_manager)
        pass
      elif choice == "6":
        # await load_background("[blue]Background fetch in progress...[/]", kkn_manager.loader)
        # TODO: handle report generation
        console.print("[#181825 on #89dceb] TODO [/] Report generation")
        pass
      elif choice == "7":
        if result := await actions.change_account():
          simaster_acc, session, kkn_manager = result
          username = simaster_acc.username
          password = simaster_acc.password
      elif choice == "8":
        kkn_manager.loader = asyncio.create_task(kkn_manager._load_all(kkn_manager.simaster_account))
        console.print("[blue]Data refresh started in background...")
      elif choice == "9":
        console.print("[yellow]Exiting...[/]")
        if not kkn_manager.loader.done():
          kkn_manager.loader.cancel()
        break
      else:
        print_log(f"Invalid Choice ({choice}). Please try again")

      with console.status("Press Enter to return to the main menu...", spinner="dots"):
        await async_input()

      # HACK: we need to remove the spinner somehow since it doesn't work with input()...
      print("\033[A\033[K")
    except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
      print()
      print_log("Action interrupted! returning to Main Menu[#89dceb]...")
      print()


def signal_handler(_sig, _frame):
  print()
  print_log("Program interrupted by user, exiting...")
  os._exit(0)


def main():
  args = Parser().parse_args()

  print_title()
  username = os.getenv("SIMASTER_USERNAME") or prompt_session.prompt(HTML('Username<delim fg="#89dceb">:</delim> '))
  password = os.getenv("SIMASTER_PASSWORD") or prompt_session.prompt(
    HTML('Password<delim fg="#89dceb">:</delim> '), is_password=True
  )

  if args.submit:
    handle_attendance(username, password, "check_in")
  elif args.check:
    handle_check_status(username, password)
  else:
    try:
      asyncio.run(main_async(username, password))
    except KeyboardInterrupt:
      print()
      print_log("Program interrupted! Exiting[#89dceb]...")


if __name__ == "__main__":
  load_dotenv()
  main()
