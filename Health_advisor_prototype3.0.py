import os
import json
import requests
import winsound  # Built-in Windows sound library
from datetime import date
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme
from rich.highlighter import RegexHighlighter


# --- SOUND LOGIC ---
def play_notification(is_warning=False):
    """Plays a Windows system sound."""
    if is_warning:
        # Plays the 'Critical Stop' or 'Hand' sound
        winsound.MessageBeep(winsound.MB_ICONHAND)
    else:
        # Plays a simple notification 'Asterisk' sound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)


# --- UI & HIGHLIGHTING ---
class HealthHighlighter(RegexHighlighter):
    base_style = "health."
    highlights = [
        r"(?P<energy>calories|kcal|energy)",
        r"(?P<nutrition>protein|vitamins|carbs|fats|mushroom|salad)",
        r"(?P<action>run|exercise|workout|walk)",
        r"(?P<warning>exceeded|limit|danger|stop|warning)"
    ]


custom_theme = Theme({
    "health.energy": "bold yellow",
    "health.nutrition": "bold green",
    "health.action": "bold cyan",
    "health.warning": "bold red",
    "dash.title": "bold white on blue"
})

load_dotenv()
console = Console(highlighter=HealthHighlighter(), theme=custom_theme)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

LIMIT = 2000
STATS_FILE = "daily_stats.json"


def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    today = str(date.today())
    data = {"date": today, "calories": 0, "exercise_mins": 0}
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            saved = json.load(f)
            if saved.get("date") == today: data = saved

    data["calories"] += calories
    data["exercise_mins"] += exercise_mins

    # Trigger Sound Alerts
    if calories > 0:
        if data["calories"] > LIMIT:
            play_notification(is_warning=True)  # Danger sound
        else:
            play_notification(is_warning=False)  # Success sound

    with open(STATS_FILE, "w") as f:
        json.dump(data, f)
    return data


def get_weather(target_area: str = "Singapore"):
    """
    Fetches the 2-hour forecast for a specific area in Singapore.
    If area isn't found, returns a general summary.
    """
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()

        # Get the list of all area forecasts
        forecasts = resp['items'][0]['forecasts']

        # Search for a match (e.g., if user says 'Clementi')
        target_area = target_area.title()  # Capitalize first letter
        for entry in forecasts:
            if target_area in entry['area']:
                return f"{entry['area']}: {entry['forecast']}"

        # Fallback if specific area isn't in the list
        general = resp['items'][0]['forecasts'][0]
        return f"Area '{target_area}' not found. General ({general['area']}): {general['forecast']}"
    except:
        return "Weather data unavailable."


def draw_ui():
    stats = update_daily_log(0, 0)
    weather = get_weather()

    # We use a simple grid and force the width of the text column
    table = Table.grid(expand=True)
    table.add_column(justify="left", width=55)  # Locked width for stability

    # Progress Bar using standard ASCII characters for better compatibility
    progress = int((stats['calories'] / LIMIT) * 20)
    bar_color = "red" if stats['calories'] > LIMIT else "green"
    # Using '#' and '-' instead of blocks for perfect alignment on Windows
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)

    table.add_row(f"  [health.energy]ENERGY LOG:[/] {stats['calories']} / {LIMIT} kcal")
    table.add_row(f"  [{bar_color}][{bar}][/]")
    table.add_row(f"  [health.action]EXERCISE :[/]{stats['exercise_mins']} / 30 mins")
    # Truncate weather to prevent it from pushing the border out
    short_weather = (weather[:50] + '..') if len(weather) > 50 else weather
    table.add_row(f"  [health.nutrition]WEATHER  :[/] {short_weather}")

    # Use 'box.ASCII' for the most stable borders on Windows
    from rich import box
    console.print(Panel(
        table,
        title="[dash.title] MY HEALTH DASHBOARD [/]",
        border_style="blue",
        width=65,  # Fixed outer width
        box=box.SQUARE,  # Clean straight corners
        padding=(0, 1)
    ))

# --- START CHAT ---
chat = client.chats.create(
    model="gemini-2.0-flash-lite",
    config=types.GenerateContentConfig(
        system_instruction=f"Health Advisor. Limit {LIMIT}kcal. Log food/exercise via tools. If over limit or <30m exercise, suggest mushroom salad.",
        tools=[update_daily_log, get_weather]
    )
)

console.print("[bold magenta]System Online. Audio Alerts Active.[/]")

while True:
    draw_ui()
    user_input = console.input("\n[bold white]What did you eat or do?[/] > ")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Syncing..."):
        response = chat.send_message(user_input)

    console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")