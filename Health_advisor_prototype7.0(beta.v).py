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
    "Drink 2L of water today 💧",
    "Hit 10,000 steps 👟",
    "Swap your afternoon snack for a fruit 🍎",
    "Try a 5-minute plank challenge 🧱",
    "No sugary drinks for the next 24 hours 🚫"
]


# --- CORE LOGIC: AUTO-RESET & STREAK ---
def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    """Updates stats, handles midnight resets, and calculates streaks safely."""
    today = date.today()
    today_str = str(today)

    # Default data structure
    data = {"date": today_str, "calories": 0, "exercise_mins": 0, "streak": 0}

    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            try:
                saved = json.load(f)
                if saved.get("date") == today_str:
                    # Use .get(key, default) to prevent KeyError crashes
                    data["calories"] = saved.get("calories", 0)
                    data["exercise_mins"] = saved.get("exercise_mins", 0)
                    data["streak"] = saved.get("streak", 0)
                else:
                    # NEW DAY LOGIC:
                    # Check if yesterday was successful to update the streak
                    was_yesterday_success = saved.get("calories", 0) <= LIMIT and saved.get("calories", 0) > 0
                    if was_yesterday_success:
                        data["streak"] = saved.get("streak", 0) + 1
                    else:
                        data["streak"] = 0
            except:
                pass  # Use default data if file is corrupted

    # Add the current session's numbers
    data["calories"] += calories
    data["exercise_mins"] += exercise_mins

    with open(STATS_FILE, "w") as f:
        json.dump(data, f)

    if calories > 0:
        winsound.MessageBeep(winsound.MB_ICONHAND if data["calories"] > LIMIT else winsound.MB_ICONASTERISK)
    return data


# --- TOOLS ---
def get_running_route(start_point: str = "Dakota Residences"):
    routes = {
        "dakota": "Start: Dakota Residences PCN -> Mountbatten Bridge -> Geylang River PCN -> Tanjong Rhu Promenade -> Gardens by the Bay East (3.8km).",
        "bishan": "Start: Bishan-AMK Park -> Kallang PCN South -> St. Andrew's Village (3.2km).",
        "punggol": "Start: Punggol Waterway Point -> Sunrise Bridge -> Punggol East Container Park (3.9km)."
    }
    for key in routes:
        if key in start_point.lower(): return routes[key]
    return f"From {start_point}, find the nearest PCN for a scenic 3.5km run!"


def get_weather(target_area: str = "Singapore"):
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        forecasts = resp['items'][0]['forecasts']
        for f in forecasts:
            if target_area.lower() in f['area'].lower(): return f"{f['area']}: {f['forecast']}"
        return f"Singapore: {forecasts[0]['forecast']}"
    except:
        return "Weather Offline"


def analyze_food_image(file_path: str):
    try:
        img = Image.open(file_path)
        prompt = "Identify food and estimate calories. Reply: 'Food: [Name], Calories: [Number]'"
        response = client.models.generate_content(model="gemini-2.0-flash", contents=[prompt, img])
        return response.text
    except:
        return "Image Analysis Failed."


# --- UI DISPLAY ---
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def is_night_mode():
    return datetime.now().hour >= 22 or datetime.now().hour < 6


def draw_ui(location="Singapore"):
    stats = update_daily_log(0, 0)
    weather = get_weather(location)
    night = is_night_mode()

    theme_color = "bright_black" if night else "bright_blue"
    bar_color = "red" if stats['calories'] > LIMIT else ("blue" if night else "green")

    table = Table.grid(expand=True)
    table.add_column(width=50)

    progress = int((stats['calories'] / LIMIT) * 20)
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)

    # Header Info
    table.add_row(f"[yellow]CALORIES :[/] {stats['calories']} / {LIMIT} kcal")
    table.add_row(f"  [{bar_color}]\\[{bar}\\][/{bar_color}]")
    table.add_row(f"[cyan]EXERCISE :[/] {stats['exercise_mins']} / 30 mins")
    table.add_row(f"[green]WEATHER  :[/] {escape(weather)}")

    # Streak & Mission
    streak_msg = f"🔥 {stats['streak']} DAY STREAK!" if stats['streak'] > 0 else "🚀 DAY 1 - START YOUR STREAK!"
    table.add_row(f"\n[bold orange3]{streak_msg}[/]")
    table.add_row(f"[magenta]MISSION  :[/] {escape(random.choice(GOALS))}")

    console.print(Panel(
        table,
        title=f"[bold white]{'🌙 NIGHT MODE' if night else '☀️ HEALTH ADVISOR'}[/]",
        border_style=theme_color,
        width=60,
        box=box.SQUARE
    ))


# --- MAIN LOOP ---
instruction = "Advisor. Use update_daily_log for stats. Use get_weather and get_running_route (3-4km). Analyze images if provided."
chat = client.chats.create(model="gemini-2.0-flash", config=types.GenerateContentConfig(system_instruction=instruction,
                                                                                        tools=[get_weather,
                                                                                               update_daily_log,
                                                                                               get_running_route]))

current_loc = "Singapore"
while True:
    clear_screen()
    draw_ui(current_loc)

    user_input = console.input("\n[bold white]What did you eat or do? [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Advisor is syncing..."):
        # Check for image files in input
        if any(ext in user_input.lower() for ext in [".jpg", ".png", ".jpeg"]):
            filename = next((word for word in user_input.split() if "." in word), None)
            if filename and os.path.exists(filename):
                vision_result = analyze_food_image(filename)
                user_input += f"\n(Image Scan Result: {vision_result})"

        response = chat.send_message(user_input)
        for word in user_input.split():
            if word.istitle() and len(word) > 3: current_loc = word.strip("?!.,")

    console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")
    console.input("\n[dim]Press Enter...[/]")