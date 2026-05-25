import sys
import io
import os
import json
import requests
import random
import winsound
import cv2
import time
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

# --- FIX: ENSURE WINDOWS SUPPORTS UTF-8 AND COLORS ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
load_dotenv()

# We use force_terminal=True to ensure colors show up in the PyCharm terminal
console = Console(force_terminal=True, color_system="truecolor")

# --- CONFIG & INITIALIZATION ---
# Upgraded to Gemini 3.1 Pro (Released Feb 19, 2026)
# This model is specifically better at reasoning and custom tools
MODEL_ID = "gemini-3.1-pro-preview"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

LIMIT = 2000
STATS_FILE = "daily_stats.json"

# Gamification
HEALTH_POINTS = 0
bonus_awarded = False

GOALS = ["Drink 2L water 💧", "10k steps 👟", "No soda 🚫", "5-min plank 🧱", "Eat fruit 🍎"]
MOTIVATION = ["Success is small efforts! ✨", "Your only limit is you. 🚀", "Don't stop till you're proud. 🏆"]

# --- CORE FUNCTIONS ---

def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    """Primary tool for logging health data. Used by both AI and manual input."""
    today = str(date.today())

    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") != today:
                # Reset for new day but keep the streak
                data = {"date": today, "calories": 0, "exercise_mins": 0, "streak": data.get("streak", 0)}
    else:
        data = {"date": today, "calories": 0, "exercise_mins": 0, "streak": 0}

    data["calories"] += calories
    data["exercise_mins"] += exercise_mins

    with open(STATS_FILE, "w") as f:
        json.dump(data, f)

    if calories > 0 or exercise_mins > 0:
        winsound.Beep(1200, 200)
    return data

def get_weather(target_area: str = "Singapore"):
    """Fetches real-time weather from NEA (Requirement from Line 99)."""
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        forecasts = resp['items'][0]['forecasts']
        for f in forecasts:
            if target_area.lower() in f['area'].lower():
                return f"{f['area']}: {f['forecast']}"
        return f"SG General: {forecasts[0]['forecast']}"
    except:
        return "Weather Service Offline"

def draw_ui(stats):
    """Renders a colorful, high-contrast dashboard."""
    os.system('cls' if os.name == 'nt' else 'clear')
    weather = get_weather()
    current_time = datetime.now().strftime("%I:%M %p")

    # Vibrant Header
    header = Table.grid(expand=True)
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(f"[bold cyan]🕒 {current_time}[/]", f"[bold yellow]🌤️ {weather}[/]")

    # Calories Progress Bar (Changes color based on limit)
    cal_percent = min(stats['calories'] / LIMIT, 1.0)
    cal_color = "bold green" if stats['calories'] <= LIMIT else "bold red"
    cal_bar = "█" * int(cal_percent * 20) + "░" * (20 - int(cal_percent * 20))

    # Exercise Progress Bar
    ex_percent = min(stats['exercise_mins'] / 30, 1.0)
    ex_bar = "█" * int(ex_percent * 20) + "░" * (20 - int(ex_percent * 20))

    # Main Dashboard Table
    main_table = Table(box=box.DOUBLE_EDGE, border_style="bright_magenta", title="[bold white]VIBRANT HEALTH ADVISOR[/]")
    main_table.add_column("METRIC", style="bold white")
    main_table.add_column("STATUS", width=35)

    main_table.add_row("HP", f"[bold gold1]🏆 {HEALTH_POINTS} Points[/]")
    main_table.add_row("CALORIES", f"[{cal_color}]{cal_bar}[/] {stats['calories']}/{LIMIT} kcal")
    main_table.add_row("EXERCISE", f"[bold dodger_blue1]{ex_bar}[/] {stats['exercise_mins']}/30 min")
    main_table.add_row("STREAK", f"[bold orange3]🔥 {stats.get('streak', 0)} DAY STREAK[/]")
    main_table.add_row("MISSION", f"[bold medium_purple1]🎯 {random.choice(GOALS)}[/]")

    console.print(header)
    console.print(Panel(main_table, border_style="bright_blue"))
    console.print(f"[italic white]'{random.choice(MOTIVATION)}'[/]\n")

# --- CHAT & VISION LOGIC ---

# Reuse the same chat session for efficiency and quota management
chat_session = client.chats.create(
    model=MODEL_ID,
    config=types.GenerateContentConfig(
        system_instruction=(
            "You are a Singapore Health Expert. "
            "1. When shown an image OR described food, call 'update_daily_log' to add calories. "
            "2. When the user mentions running or exercise, call 'update_daily_log' with exercise_mins. "
            "3. If weather is requested, use 'get_weather'. "
            "4. Be high-energy, helpful, and warn if calories > 2000. "
            "5. Always recommend a local SG healthy spot if they are over the limit."
        ),
        tools=[update_daily_log, get_weather]
    )
)

def run_advisor():
    global HEALTH_POINTS, bonus_awarded

    while True:
        stats = update_daily_log(0, 0) # Get current stats

        # Point Check: Reward for being under limit
        if 0 < stats['calories'] <= LIMIT and not bonus_awarded:
            HEALTH_POINTS += 10
            bonus_awarded = True
            console.print("[bold gold1]⭐ DAILY BONUS: +10 HP![/]")

        draw_ui(stats)

        user_input = console.input("[bold white]Action (Type 'snap', log food/run, or ask): [/]")
        if user_input.lower() in ["exit", "quit"]: break

        with console.status("[bold green]Advisor is thinking..."):
            try:
                # Manual Mission Completion
                if "completed" in user_input.lower() and "mission" in user_input.lower():
                    HEALTH_POINTS += 5
                    console.print("\n[bold gold1]ADVISOR: Mission Complete! +5 HP earned![/]")
                    continue

                # Camera Analysis (Vision)
                if user_input.lower() == "snap":
                    cap = cv2.VideoCapture(0)
                    for i in range(3, 0, -1):
                        console.print(f"[bold yellow]📷 GET READY... {i}[/]")
                        time.sleep(1)
                    ret, frame = cap.read()
                    if ret:
                        cv2.imwrite("snap.jpg", frame)
                        img = Image.open("snap.jpg")
                        response = chat_session.send_message(message=["Estimate and log these calories.", img])
                        console.print(f"\n[bold green]ADVISOR:[/] {response.text}")
                    cap.release()

                # General Text / Search / Exercise Log
                else:
                    response = chat_session.send_message(message=user_input)
                    console.print(f"\n[bold green]ADVISOR:[/] {response.text}")

            except Exception as e:
                console.print(f"[bold red]System Error:[/] {e}")

        console.input("\n[dim]Press Enter to refresh dashboard...[/]")

if __name__ == "__main__":
    run_advisor()
