import os
import json
import requests
import random
import winsound
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markup import escape
from PIL import Image

# --- CONFIG ---
load_dotenv()
console = Console()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
LIMIT = 2000
STATS_FILE = "daily_stats.json"

GOALS = [
    "Drink 2L of water today 💧", "Hit 10,000 steps 👟", "No sugary drinks 🚫",
    "Try a 5-minute plank 🧱", "Eat a fruit with lunch 🍎"
]

session_stats = {"calories": 0, "exercise_mins": 0}


# --- FUNCTIONS ---
def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    global session_stats
    today = date.today()
    yesterday = today - timedelta(days=1)

    session_stats["calories"] += calories
    session_stats["exercise_mins"] += exercise_mins

    data = {"date": str(today), "calories": session_stats["calories"],
            "exercise_mins": session_stats["exercise_mins"], "streak": 0}

    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            try:
                saved = json.load(f)
                if saved.get("date") == str(yesterday):
                    was_success = 0 < saved.get("calories", 0) <= LIMIT
                    data["streak"] = saved.get("streak", 0) + 1 if was_success else 0
                elif saved.get("date") == str(today):
                    data["streak"] = saved.get("streak", 0)
            except:
                pass

    with open(STATS_FILE, "w") as f:
        json.dump(data, f)

    if calories != 0:
        winsound.Beep(1000, 200)
    return data, session_stats


def get_running_route(start_point: str = "Dakota"):
    routes = {
        "dakota": "Dakota Residences PCN -> Mountbatten Bridge -> Tanjong Rhu -> GBTB East (3.8km).",
        "old airport": "Old Airport Road -> Geylang Park Connector -> Marina Reservoir Loop (3.5km).",
        "bishan": "Bishan-AMK Park -> Kallang PCN South -> St. Andrew's Village (3.2km)."
    }
    for key in routes:
        if key in start_point.lower(): return routes[key]
    return f"From {start_point}, head to the nearest PCN for a scenic 3.5km run!"


def get_weather(target_area: str = "Singapore"):
    now = datetime.now().strftime("%I:%M %p")
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        for f in resp['items'][0]['forecasts']:
            if target_area.lower() in f['area'].lower():
                return f"{f['area']}: {f['forecast']}", now
        return f"Singapore: {resp['items'][0]['forecasts'][0]['forecast']}", now
    except:
        return "Weather Offline", now


# --- UI ---
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def draw_ui(location="Singapore"):
    p, live = update_daily_log(0, 0)
    weather, live_time = get_weather(location)

    table = Table.grid(expand=True)
    table.add_column(width=50)
    table.add_row(f"[bold white]🕒 {live_time}[/] | [green]🌤️ {escape(weather)}[/]")
    table.add_row("-" * 55)

    progress = int((live['calories'] / LIMIT) * 20)
    bar_color = "red" if live['calories'] > LIMIT else "green"
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)

    table.add_row(f"[yellow]CALORIES :[/] {live['calories']} / {LIMIT} kcal")
    table.add_row(f"  [{bar_color}]\\[{bar}\\][/{bar_color}]")
    table.add_row(f"[cyan]EXERCISE :[/] {live['exercise_mins']} / 30 mins")
    table.add_row(f"\n[bold orange3]🔥 {p.get('streak', 0)} DAY STREAK![/]")
    table.add_row(f"[magenta]MISSION  :[/] {escape(random.choice(GOALS))}")
    console.print(Panel(table, title="☀️ HEALTH ASSISTANT", border_style="bright_blue", width=60, box=box.SQUARE))


# --- MAIN ---
instruction = (
    "You are a Singapore Health & Local Guide. "
    "1. Use 'update_daily_log' for tracking. "
    "2. Recommend stalls at Old Airport Road or restaurants at Kallang Wave Mall/PLQ. "
    "3. Provide specific unit numbers and calorie-friendly options based on remaining budget."
)

# FIXED: Removed google_search to solve the 400 Error
chat = client.chats.create(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        system_instruction=instruction,
        tools=[get_weather, update_daily_log, get_running_route]
    )
)

current_loc = "Singapore"
while True:
    clear_screen()
    draw_ui(current_loc)
    user_input = console.input("\n[bold white]Update/Search: [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Processing..."):
        try:
            # Check for images
            if any(ext in user_input.lower() for ext in [".jpg", ".png"]):
                filename = next((w for w in user_input.split() if "." in w), None)
                if filename and os.path.exists(filename):
                    img = Image.open(filename)
                    # FIXED: Vision uses generate_content separately or direct multi-modal
                    response = chat.send_message(contents=[user_input, img])
                else:
                    response = chat.send_message(contents=user_input)
            else:
                response = chat.send_message(contents=user_input)

            for word in user_input.split():
                if word.istitle() and len(word) > 3: current_loc = word.strip("?!.,")

            console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")

    console.input("\n[dim]Press Enter to refresh...[/]")