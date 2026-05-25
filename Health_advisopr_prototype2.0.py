import os
import json
import requests
from datetime import date
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

# --- SETUP ---
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
console = Console()
LIMIT = 2000
STATS_FILE = "daily_stats.json"


# --- TOOLS & LOGIC ---
def get_nea_weather():
    """Fetches the 2-hour weather forecast from Singapore NEA (data.gov.sg)."""
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        area = resp['items'][0]['forecasts'][0]['area']
        forecast = resp['items'][0]['forecasts'][0]['forecast']
        return f"Weather in {area}: {forecast}"
    except:
        return "Weather data unavailable."


def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    """Updates the local JSON file with food/exercise and returns the current balance."""
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

    return data


# --- THE UI RENDERER ---
def print_dashboard(data, weather):
    """Creates a beautiful dashboard layout."""
    cal_color = "green" if data['calories'] <= LIMIT else "bold red"
    ex_color = "cyan" if data['exercise_mins'] >= 30 else "yellow"

    # Create Columns for a 'Card' look
    stats_table = Table.grid(expand=True)
    stats_table.add_column(justify="left")
    stats_table.add_row(f"[{cal_color}]🔥 Calories: {data['calories']} / {LIMIT}[/]")
    stats_table.add_row(f"[{ex_color}]🏃 Exercise: {data['exercise_mins']} / 30 mins[/]")
    stats_table.add_row(f"☁️ {weather}")

    console.print(Panel(stats_table, title="[bold white]DAILY HEALTH SUMMARY[/]", border_style="blue"))


# --- MAIN LOOP ---
tools = [get_nea_weather, update_daily_log]
instruction = (
    f"You are a Health Advisor. Daily limit is {LIMIT} kcal. "
    "When food or exercise is logged, use 'update_daily_log'. Always check 'get_nea_weather' for run advice. "
    "If calories > limit or exercise < 30m, insist on a mushroom salad for dinner."
)

chat = client.chats.create(
    model="gemini-2.0-flash-lite",
    config=types.GenerateContentConfig(system_instruction=instruction, tools=tools)
)

console.print(Panel.fit("Welcome, User! I am tracking your 2000kcal budget.", style="bold magenta"))

while True:
    user_input = console.input("[bold white]Input (Food/Exercise): [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Analyzing and updating..."):
        response = chat.send_message(user_input)

    # Update visual dashboard after every turn
    current_data = update_daily_log(0, 0)  # Just fetch current
    weather_info = get_nea_weather()
    print_dashboard(current_data, weather_info)

    console.print(f"\n[bold blue]ADVISOR:[/] {response.text}\n")