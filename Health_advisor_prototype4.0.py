import os
import json
import requests
import random
import winsound
from datetime import date
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

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


# --- TOOLS ---
def get_weather(target_area: str = "Singapore"):
    """Searches NEA for your specific area."""
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        forecasts = resp['items'][0]['forecasts']
        for f in forecasts:
            if target_area.lower() in f['area'].lower():
                return f"{f['area']}: {f['forecast']}"
        return f"Singapore: {forecasts[0]['forecast']} (Area '{target_area}' not found)"
    except:
        return "Weather Offline"


def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    """Updates calories and exercise in the JSON file."""
    today = str(date.today())
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") != today: data = {"date": today, "calories": 0, "exercise_mins": 0}
    else:
        data = {"date": today, "calories": 0, "exercise_mins": 0}

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


# --- UI ---
def draw_ui(location="Singapore"):
    data = update_daily_log(0, 0)
    weather = get_weather(location)
    table = Table.grid(expand=True)
    table.add_column(width=45)

    progress = int((data['calories'] / LIMIT) * 20)
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)
    status = "OVER LIMIT!" if data['calories'] > LIMIT else "OK"

    table.add_row(f" [yellow]CALORIES :[/] {data['calories']} / {LIMIT} ({status})")
    table.add_row(f"  \\[{bar}\\]")
    table.add_row(f" [cyan]EXERCISE :[/] {data['exercise_mins']} / 30 mins")
    table.add_row(f" [green]WEATHER  :[/] {weather}")
    table.add_row("")
    table.add_row(f" [magenta]GOAL OF THE DAY:[/] {random.choice(GOALS)}")

    console.print(Panel(
        table,
        title="[bold white] PERSONAL HEALTH ASSISTANT [/]",
        border_style="bright_blue",
        width=60,
        box=box.SQUARE,
        padding=(0, 2)
    ))


# --- CHAT SESSION ---
instruction = (
    f"You are a Singapore Health Advisor. Daily limit: {LIMIT}kcal. "
    "1. Always call 'update_daily_log' when user mentions food or exercise. "
    "2. If they ask about running/weather, use 'get_weather' with the area name. "
    "3. Keep responses brief and encouraging."
)

# Start a chat session with automatic function calling enabled
chat = client.chats.create(
    model="gemini-2.0-flash-lite",
    config=types.GenerateContentConfig(
        system_instruction=instruction,
        tools=[get_weather, update_daily_log]
    )
)

# --- RUN LOOP ---
current_loc = "Singapore"
while True:
    draw_ui(current_loc)
    user_input = console.input("\n[bold white]Update (Food/Exercise/Weather): [/]")
    if user_input.lower() in ["exit", "quit"]: break

    # Logic to catch location mentions so the dashboard updates
    # This checks if any word in the user input matches an area Gemini might have used
    response = chat.send_message(user_input)

    # Optional: Update current_loc if the user specifically asked for a new place
    # This helps keep the dashboard weather relevant to the chat
    for word in user_input.split():
        if word.istitle():  # Areas are usually capitalized like 'Jurong'
            current_loc = word.strip("?!.,")

    console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")