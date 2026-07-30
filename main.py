import os
import json
import requests
from colorama import Fore, init
import time
from bs4 import BeautifulSoup

init(autoreset=True)

def get_favorites(user_id, cookie):
    url = f"https://games.roblox.com/v2/users/{user_id}/favorite/games?limit=100&sortOrder=Desc"
    all_data = []
    
    try:
        while url:
            response = requests.get(url, cookies={".ROBLOSECURITY": cookie})
            response.raise_for_status()
            data = response.json()
            all_data.extend(data.get("data", []))
            
            cursor = data.get("nextPageCursor")
            if cursor:
                url = f"https://games.roblox.com/v2/users/{user_id}/favorite/games?limit=100&sortOrder=Desc&cursor={cursor}"
            else:
                break
        return {"data": all_data}
    except requests.exceptions.RequestException as e:
        print(Fore.RED + f"Failed to fetch favorited games: {e}")
        return None

def get_xsrf_token(cookie):
    try:
        home_page = requests.get("https://www.roblox.com/home", cookies={".ROBLOSECURITY": cookie})
        soup = BeautifulSoup(home_page.text, "html.parser")
        csrf_tag = soup.find("meta", {"name": "csrf-token"})
        return csrf_tag["data-token"]
    except Exception as e:
        print(Fore.RED + f"Failed to fetch XSRF token: {e}")
        return None

def get_root_place_id(universe_id, cookie):
    url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
    try:
        response = requests.get(url, cookies={".ROBLOSECURITY": cookie})
        response.raise_for_status()
        data = response.json().get('data', [])
        if data:
            return data[0].get('rootPlaceId')
        return None
    except requests.exceptions.RequestException as e:
        print(Fore.RED + f"Failed to fetch root place ID for universe {universe_id}: {e}")
        return None

def unfavor_game(cookie, user_id, game_id, xsrf_token):
    url = f"https://catalog.roblox.com/v1/favorites/users/{user_id}/assets/{game_id}/favorite"
    headers = {
        "X-CSRF-TOKEN": xsrf_token,
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        response = requests.delete(url, cookies={".ROBLOSECURITY": cookie}, headers=headers)
        print(f"Unfavorite request for game {game_id} sent. Status code: {response.status_code}")
        
        if response.status_code == 403 and "x-csrf-token" in response.headers:
            return response.status_code, response.headers["x-csrf-token"]
            
        if response.status_code not in (200, 403):
            print(f"Response body: {response.text}")
            
        return response.status_code, xsrf_token
    except requests.exceptions.RequestException as e:
        print(Fore.RED + f"Failed to unfavor game: {game_id}. {e}")
        return None, xsrf_token

def main(settings):
    os.system('cls' if os.name == 'nt' else 'clear')
    cookie = settings["cookie"]
    mass_unfavor = settings["mass_unfavor"]
    whitelist = set(settings.get("whitelist", []))
    
    try:
        user_id = requests.get("https://users.roblox.com/v1/users/authenticated", cookies={".ROBLOSECURITY": cookie}).json()["id"]
    except Exception as e:
        print(Fore.RED + "Please provide a valid cookie in settings.json")
        os.system("pause")
        return

    xsrf_token = get_xsrf_token(cookie)

    if xsrf_token is None:
        os.system("pause")
        return

    favorites = get_favorites(user_id, cookie)

    if favorites is None or 'data' not in favorites:
        os.system("pause")
        return

    games = favorites.get('data', [])
    print(Fore.GREEN + f"You currently have {len(games)} favorited games.\n")

    if mass_unfavor:
        input(Fore.LIGHTRED_EX + "!!! Warning: Mass unfavor is enabled. This will unfavorite all your favorited games except the games you've added to the whitelist! Press Enter to continue.")
        os.system('cls' if os.name == 'nt' else 'clear')
        print(Fore.GREEN + f"You currently have {len(games)} favorited games.\n")

    unfavorited = 0
    retry_delay = 10

    for item in games:
        total_attempts = 0
        game_name = item.get('name')
        universe_id = item.get('id')
        
        if not game_name or not universe_id:
            continue
        
        root_place = item.get('rootPlace', {})
        place_id = root_place.get('id')

        if universe_id not in whitelist and place_id not in whitelist:
            if not place_id:
                place_id = get_root_place_id(universe_id, cookie)
            
            if not place_id:
                print(Fore.YELLOW + f"Could not find place ID for {game_name} (Universe ID: {universe_id}). Skipping.")
                continue

            unfavor = 'y' if mass_unfavor else input(Fore.LIGHTWHITE_EX + f"Do you want to unfavor game {game_name} (ID: {place_id})? (y/n): ").strip().lower()

            if unfavor == 'y':
                while True:
                    response_code, new_xsrf_token = unfavor_game(cookie, user_id, place_id, xsrf_token)
                    total_attempts += 1
                    
                    if new_xsrf_token and new_xsrf_token != xsrf_token:
                        xsrf_token = new_xsrf_token
                        if response_code == 403:
                            continue

                    if response_code == 200:
                        print(Fore.GREEN + f"Unfavorited game: {game_name} (ID: {place_id})")
                        unfavorited += 1
                        time.sleep(1.5)
                        break
                    elif response_code == 409:
                        print(Fore.YELLOW + f"Game already unfavorited: {game_name} (ID: {place_id})")
                        break
                    elif response_code == 429:
                        print(Fore.YELLOW + f"Rate limited. Waiting 10 seconds before retrying...")
                        time.sleep(10)
                        continue
                    else:
                        print(Fore.RED + f"Failed to unfavor game: {game_name} (ID: {place_id}).")
                        
                        if total_attempts >= 5:
                            print(Fore.RED + f"Giving up on {game_name} after 5 attempts.")
                            break

                
                        time.sleep(retry_delay)
                        
                        new_token = get_xsrf_token(cookie)
                        if new_token is None:
                            os.system("pause")
                            return
                        xsrf_token = new_token
        else:
            print(Fore.YELLOW + f"Skipping game: {game_name} (ID: {place_id})")

    print(Fore.MAGENTA + f"Unfavorited {unfavorited} games.")
    os.system("pause")

if __name__ == "__main__":
    with open("settings.json", 'r') as file:
        settings = json.load(file)
    main(settings)
