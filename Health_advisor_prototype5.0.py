import os
import json
import requests
import random
import winsound
from datetime import datetime, date
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markup import escape

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
    "BONUS CHALLENGE! try cycling to marina barrage from bedok reservoir"
]


# --- UTILS ---
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def is_night_mode():
    now = datetime.now().hour
    return now >= 22 or now < 6


# --- TOOLS ---
def get_weather(target_area: str = "Singapore"):
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        forecasts = resp['items'][0]['forecasts']
        for f in forecasts:
            if target_area.lower() in f['area'].lower():
                # We use escape() here to make sure area names with special chars don't break Rich
                return f"{f['area']}: {f['forecast']}"
        return f"Singapore: {forecasts[0]['forecast']}"
    except:
        return "Weather Offline"


def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    today = str(date.today())
    data = {"date": today, "calories": 0, "exercise_mins": 0}
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            try:
                saved = json.load(f)
                if saved.get("date") == today: data = saved
            except:
                pass

    data["calories"] += calories
    data["exercise_mins"] += exercise_mins
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)

    if calories > 0:
        if data["calories"] > LIMIT:
            winsound.MessageBeep(winsound.MB_ICONHAND)
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    return data


# --- THE UI ---
def draw_ui(location="Singapore"):
    data = update_daily_log(0, 0)
    weather_text = get_weather(location)
    night = is_night_mode()

    theme_color = "bright_black" if night else "bright_blue"
    title_style = "bold white"
    title_text = "🌙 NIGHT MODE ACTIVE" if night else "☀️ PERSONAL HEALTH ASSISTANT"

    table = Table.grid(expand=True)
    table.add_column(width=50)

    # Progress Bar
    progress = int((data['calories'] / LIMIT) * 20)
    bar_color = "red" if data['calories'] > LIMIT else ("blue" if night else "green")
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)

    # We use f-strings carefully and escape variables to prevent MarkupError
    table.add_row(f"[yellow]CALORIES :[/] {data['calories']} / {LIMIT}")
    # We double-backslash the brackets of the bar to escape them
    table.add_row(f"  [{bar_color}]\\[{bar}\\][/{bar_color}]")
    table.add_row(f"[cyan]EXERCISE :[/] {data['exercise_mins']} / 30 mins")
    # escape() ensures that any weird characters in weather don't trigger tags
    table.add_row(f"[green]WEATHER  :[/] {escape(weather_text)}")
    table.add_row("")
    table.add_row(f"[magenta]GOAL     :[/] {escape(random.choice(GOALS))}")

    console.print(Panel(
        table,
        title=f"[{title_style}]{title_text}[/]",
        border_style=theme_color,
        width=60,
        box=box.SQUARE,
        padding=(0, 2)
    ))


# --- CHAT SETUP ---
instruction = (
    f"You are a Health Advisor. Limit {LIMIT}kcal. "
    "Use update_daily_log for stats and get_weather for area-specific forecasts. "
    "Keep responses encouraging. If the user exceeds the limit, suggest a salad."
)
chat = client.chats.create(
    model="gemini-2.0-flash-lite",
    config=types.GenerateContentConfig(system_instruction=instruction, tools=[get_weather, update_daily_log])
)

# --- RUN LOOP ---
current_loc = "Singapore"
while True:
    clear_screen()
    draw_ui(current_loc)

    user_input = console.input("\n[bold white]Update (Food/Exercise/Location): [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Syncing..."):
        try:
            response = chat.send_message(user_input)

            # Search input for a location update
            for word in user_input.split():
                if word.istitle() and len(word) > 3:
                    current_loc = word.strip("?!.,")

            console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")

    console.input("\n[dim]Press Enter to continue...[/]")