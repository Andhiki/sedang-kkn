import getpass
import os

import httpx
from dotenv import load_dotenv

from oauth import OAuthClient
from utils import generate_random_points

load_dotenv()

CLIENT_ID = "e6abd4e380a5462e83873fe22ab8c219yVaU"
CLIENT_SECRET = "THFnhmQ6jckSWWzV6m9Mj78CexLCKjd009f4h9gQaIo8fUUULOhWP7DD"
REDIRECT_URI = "id.ac.ugm.student.vnext.simaster://oauth2"
BASE_URL = "https://api.simaster.ugm.ac.id/vnext/v1/checkpoint"


def do_checkin(username: str, access_token: str):
    header = {
        "Content-type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        latitude = float(os.getenv("KKN_LOCATION_LATITUDE", "0.0"))
        longitude = float(os.getenv("KKN_LOCATION_LONGITUDE", "0.0"))
        radius = int(os.getenv("KKN_LOCATION_RADIUS_METERS", "0"))
        qr_value = int(os.getenv("QR_CODE_VALUE", "0"))
    except (TypeError, ValueError):
        print(
            "\nError: Either one of the following is not set correctly in .env file:"
            "\n1. KKN_LOCATION_LATITUDE: float"
            "\n2. KKN_LOCATION_LONGITUDE: float"
            "\n3. KKN_LOCATION_RADIUS_METERS: int"
            "\n4. QR_CODE_VALUE: int"
        )
        return

    random_lat, random_long = generate_random_points(latitude, longitude, radius)
    print(f"\nGenerated random point for attendance: (Lat: {random_lat}, Long: {random_long})")

    params = {"lat": random_lat, "long": random_long}
    full_url = f"{BASE_URL}/checkin/{username}/{qr_value}"
    client = httpx.Client(timeout=10.0)

    try:
        resp = client.post(full_url, params=params, headers=header, follow_redirects=True)

        if resp.status_code == 200:
            print("\nSUCCESS: Check-in successful!")
        else:
            print(f"\nFAILED: Status Code {resp.status_code}")
    except Exception as e:
        print(f"Request Error: {e}")


def main():
    username = input("Username: ")
    password = getpass.getpass()

    oauth_client = OAuthClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
    login_result = oauth_client.complete_oauth_flow(username, password)

    if not login_result["success"]:
        print("ERROR:")
        print(login_result["error"])
        return

    access_token = login_result["access_token"]
    print("Login successful!")
    assert type(access_token) is str

    usernames = os.getenv("USERNAMES", "").split(",")
    for username in usernames:
        print(f"Checking in for {username}")
        do_checkin(username, access_token)


if __name__ == "__main__":
    main()
