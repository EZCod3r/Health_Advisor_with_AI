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


# --- CORE LOGIC ---
def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    today = date.today()
    today_str = str(today)
    data = {"date": today_str, "calories": 0, "exercise_mins": 0, "streak": 0}

    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            try:
                saved = json.load(f)
                if saved.get("date") == today_str:
                    data = saved
                else:
                    was_yesterday_success = 0 < saved.get("calories", 0) <= LIMIT
                    data["streak"] = saved.get("streak", 0) + 1 if was_yesterday_success else 0
            except:
                pass

    data["calories"] += calories
    data["exercise_mins"] += exercise_mins
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)
    return data


# --- TOOLS ---
def get_running_route(start_point: str = "Dakota Residences"):
    """Suggests a scenic 3-4km PCN route based on starting location."""
    routes = {
        "dakota": "Dakota Residences PCN -> Mountbatten Bridge -> Tanjong Rhu Promenade -> Gardens by the Bay East (3.8km).",
        "old airport": "Old Airport Road -> Geylang Park Connector -> Marina Reservoir Loop (3.5km).",
        "bishan": "Bishan-AMK Park -> Kallang PCN South -> St. Andrew's Village (3.2km).",
        "tampines": "Tampines Eco Green -> Sun Plaza Park -> Tampines Avenue 9 (3.4km)."
    }
    for key in routes:
        if key in start_point.lower(): return routes[key]
    return f"From {start_point}, find the nearest PCN for a 3.5km scenic run."


def get_weather(target_area: str = "Singapore"):
    """Returns weather AND the current live time."""
    now = datetime.now().strftime("%I:%M %p")
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        forecasts = resp['items'][0]['forecasts']
        for f in forecasts:
            if target_area.lower() in f['area'].lower():
                return f"{f['area']}: {f['forecast']}", now
        return f"Singapore: {forecasts[0]['forecast']}", now
    except:
        return "Weather Offline", now


# --- UI DISPLAY ---
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def draw_ui(location="Singapore"):
    stats = update_daily_log(0, 0)
    weather, live_time = get_weather(location)
    night = datetime.now().hour >= 22 or datetime.now().hour < 6

    table = Table.grid(expand=True)
    table.add_column(width=50)

    # Live Clock & Weather Row
    table.add_row(f"[bold white]🕒 TIME : {live_time}[/] | [green]🌤️ {escape(weather)}[/]")
    table.add_row("-" * 55)

    # Progress Bar
    progress = int((stats['calories'] / LIMIT) * 20)
    bar_color = "red" if stats['calories'] > LIMIT else ("blue" if night else "green")
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)

    table.add_row(f"[yellow]CALORIES :[/] {stats['calories']} / {LIMIT} kcal")
    table.add_row(f"  [{bar_color}]\\[{bar}\\][/{bar_color}]")
    table.add_row(f"[cyan]EXERCISE :[/] {stats['exercise_mins']} / 30 mins")

    streak_val = stats.get("streak", 0)
    streak_msg = f"🔥 {streak_val} DAY STREAK!" if streak_val > 0 else "🚀 DAY 1 - START YOUR STREAK!"
    table.add_row(f"\n[bold orange3]{streak_msg}[/]")
    table.add_row(f"[magenta]MISSION  :[/] {escape(random.choice(GOALS))}")

    console.print(Panel(table, title=f"[bold white]{'🌙 NIGHT MODE' if night else '☀️ HEALTH ASSISTANT'}[/]",
                        border_style="bright_blue", width=60, box=box.SQUARE))


# --- MAIN CHAT ---
instruction = (
    f"You are a Singapore Health & Food Guide. Daily Limit: {LIMIT}kcal.\n"
    "1. TRACKING: Use 'update_daily_log' for food/exercise.\n"
    "2. RUNNING: If user searches weather for an area, suggest a 3-4km PCN route nearby using 'get_running_route'.\n"
    "3. HAWKER GUIDE: When recommending food, suggest specific HIGHLY-RATED stalls (4+ stars) from Google Reviews. "
    "Identify the Hawker Center name, the Stall Name, and the Unit Number (e.g., Old Airport Road Food Centre, Xin Mei Xiang Lor Mee, #01-116).\n"
    "4. CALORIES: Suggest meals that fit their remaining budget (2000 - current_calories)."
)

chat = client.chats.create(model="gemini-2.0-flash", config=types.GenerateContentConfig(system_instruction=instruction,
                                                                                        tools=[get_weather,
                                                                                               update_daily_log,
                                                                                               get_running_route]))

current_loc = "Singapore"
while True:
    clear_screen()
    draw_ui(current_loc)

    user_input = console.input("\n[bold white]What's the plan? [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Advisor is searching..."):
        # Image logic
        if any(ext in user_input.lower() for ext in [".jpg", ".png", ".jpeg"]):
            filename = next((word for word in user_input.split() if "." in word), None)
            if filename and os.path.exists(filename):
                img = Image.open(filename)
                res = client.models.generate_content(model="gemini-2.0-flash",
                                                     contents=["Identify food & calories:", img])
                user_input += f"\n(Image Result: {res.text})"

        response = chat.send_message(user_input)
        for word in user_input.split():
            if word.istitle() and len(word) > 3: current_loc = word.strip("?!.,")

    console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")
    console.input("\n[dim]Press Enter to refresh...[/]")