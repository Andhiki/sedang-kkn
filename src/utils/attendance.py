import os
import random
import time
from typing import Callable, Literal

import httpx
import requests
from rich import box
from rich.prompt import Confirm, Prompt
from rich.table import Table

from datatypes import CheckInPayload, RequestHeader
from ui.tui import console, print_log
from utils.common import generate_random_points
from utils.oauth import OAuthClient

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"
BASE_URL = "https://api.simaster.ugm.ac.id/vnext/v1/checkpoint"


def check_in(username: str, data: CheckInPayload):
  header: RequestHeader = {
    "Content-type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {data.access_token}",
  }

  client = httpx.Client()
  with console.status(
    f"[blue]Checking in for [#89dceb]{username}[/]...", spinner="dots", spinner_style="#89dceb"
  ) as status:
    random_lat, random_long = generate_random_points(data.latitude, data.longitude, data.radius)
    time.sleep(0.4)
    status.update(f"[blue]Generated random point: [yellow]([#fab387]{random_lat}[#89dceb],[/] {random_long}[/])[/]")
    time.sleep(0.4)

    params = {"lat": random_lat, "long": random_long}
    full_url = f"{BASE_URL}/checkin/{username}/{data.qr_value}"

    try:
      status.update("[blue]Hitting the endpoint....")
      resp = client.post(full_url, params=params, headers=header)
    except Exception as e:
      print_log(f"Request Error: {e}", "ERROR")

  if resp.status_code == 200:
    print_log(f"Succesfully checked-in as [bold #89dceb]{username}[/]!", "SUCCESS")
    return True
  else:
    print_log(f"Status Code {resp.status_code}", "ERROR")
    return False


def check_active_session(username: str, access_token: str):
  header: RequestHeader = {
    "Content-type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {access_token}",
  }

  url = f"{BASE_URL}/get_active_session/{username}"
  resp = requests.get(url, headers=header)

  if resp.status_code == 200:
    data = resp.json()
    return {
      "id": data["check_point_log_id"],
      "location": data["check_point_nama"],
      "time": data["check_point_log_check_in"],
    }

  return None


def _handle_attendance_env(data: CheckInPayload, func: Callable):
  throttle = Confirm.ask("Throttle in between check-in?", default=False)
  shuffle = Confirm.ask("Shuffle the check-in order?", default=True)

  usernames = os.getenv("USERNAMES", "").split(",")
  if shuffle:
    random.shuffle(usernames)

  length = len(usernames)
  for id, user in enumerate(usernames, 1):
    print(f"Checking in for {user}")
    # Retry until successful, idrc
    while not check_in(user, data):
      pass

    if throttle and id < length:
      time.sleep(random.uniform(0.0, 5.0))


def _handle_attendance_manual(data: CheckInPayload, func: Callable):
  while True:
    table = Table(box=box.ROUNDED, show_header=False)
    table.add_row("1", "Latitude", str(data.latitude), "Latitude of your KKN location")
    table.add_row("2", "Longitude", str(data.longitude), "Longitude of your KKN location")
    table.add_row("3", "Radius", str(data.radius), "Radius of the randomly generated location")
    table.add_row("4", "QR Value", str(data.qr_value), "QR Value of the checkpoint")
    console.print(table)

    change = Confirm.ask("Do you want to change the location?", default=False)

    if change:
      data.latitude = float(Prompt.ask("Enter new latitude value", default=data.latitude))
      data.longitude = float(Prompt.ask("Enter new longitude value", default=data.longitude))
      data.radius = int(Prompt.ask("Enter new radius value", default=data.radius))
      data.qr_value = int(Prompt.ask("Enter new QR code value", default=data.qr_value))

    username = Prompt.ask("Enter username to check in")
    while not check_in(username, data):
      pass

    if not Confirm.ask("Input another username?", default=False):
      break


def handle_attendance(username: str, password: str, type: Literal["check_in", "check_out"] = "check_in"):
  try:
    latitude = float(os.getenv("KKN_LOCATION_LATITUDE", ""))
    longitude = float(os.getenv("KKN_LOCATION_LONGITUDE", ""))
    radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", "100"))
    qr_value = int(os.getenv("QR_CODE_VALUE", ""))
  except (TypeError, ValueError):
    print_log(
      "Either one of the following is not set correctly in .env file:"
      "\n[#fab387]1[/][#89dceb].[white] KKN_LOCATION_LATITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]2[/][#89dceb].[white] KKN_LOCATION_LONGITUDE[/]:[/] [yellow]float[/]"
      "\n[#fab387]3[/][#89dceb].[white] QR_CODE_VALUE[/]:[/] [yellow]int[/]"
    )
    return

  oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
  login_result = oauth_client.complete_oauth_flow(username, password)

  if not login_result["success"]:
    print_log(f"({login_result['step']}) {login_result['error']}", "ERROR")
    return

  if not (access_token := login_result["access_token"]):
    print_log("No access token found!", "ERROR")
    return

  print_log("Successfully logged in via [#89dceb]oauth.ugm.ac.id[/]!", "SUCCESS")

  data = CheckInPayload(
    access_token=access_token,
    qr_value=qr_value,
    latitude=latitude,
    longitude=longitude,
    radius=radius,
  )

  func = check_in if type == "check_in" else check_out

  is_manual = Confirm.ask("Do you want to input usernames manually?", default=False)

  if is_manual:
    _handle_attendance_manual(data, func)
  else:
    _handle_attendance_env(data, func)


def handle_check_status(username: str, password: str):
  oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
  login_result = oauth_client.complete_oauth_flow(username, password)

  if not login_result["success"]:
    print_log(f"({login_result['step']})[/]: {login_result['error']}", "ERROR")
    return

  access_token = login_result["access_token"]
  print("Login successful!")
  assert type(access_token) is str

  usernames = os.getenv("USERNAMES", "").split(",")
  for username in usernames:
    print(f"Checking status for {username}")
    data = check_active_session(username, access_token)

    if not data:
      print(f"User {username} haven't checked-in")
      continue

    print(f"ID: {data['id']}\nLocation: {data['location']}\nCheck-in time: {data['time']}")
