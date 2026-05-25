import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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

# --- CONFIG ---
load_dotenv()
# Force the terminal to show colors and use a specific system
console = Console(force_terminal=True, color_system="standard")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
LIMIT = 2000
STATS_FILE = "daily_stats.json"

# Gamification Variables
HEALTH_POINTS = 0  # Resets every run
bonus_awarded = False

GOALS = ["Drink 2L water 💧", "10k steps 👟", "No soda 🚫", "5-min plank 🧱", "Eat fruit 🍎"]
MOTIVATION = ["Success is small efforts! ✨", "Your only limit is you. 🚀", "Don't stop till you're proud. 🏆", "The best is yet to be👑", "Count your calories, don't make calories count for you🥇"]

session_stats = {"calories": 0, "exercise_mins": 0}
current_loc = "Singapore"


# --- CORE FUNCTIONS ---

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def log_discovery(category, content):
    """Saves AI findings to a permanent text file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open("discovery_history.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {category.upper()}:\n{content}\n")
        f.write("-" * 30 + "\n")


def capture_from_camera():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): return None
    for i in range(3, 0, -1):
        console.print(f"[bold cyan]📷 GET READY... {i}[/]")
        time.sleep(1)
    ret, frame = cap.read()
    if ret:
        filename = "health_snap.jpg"
        cv2.imwrite(filename, frame)
        cap.release()
        return filename
    cap.release()
    return None


def update_daily_log(calories: int = 0, exercise_mins: int = 0):
    global session_stats
    today = date.today()
    session_stats["calories"] += calories
    session_stats["exercise_mins"] += exercise_mins
    data = {"date": str(today), "calories": session_stats["calories"], "streak": 0}

    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            try:
                saved = json.load(f)
                yesterday = str(today - timedelta(days=1))
                if saved.get("date") == yesterday:
                    data["streak"] = saved.get("streak", 0) + (1 if 0 < saved.get("calories", 0) <= LIMIT else 0)
                elif saved.get("date") == str(today):
                    data["streak"] = saved.get("streak", 0)
            except:
                pass
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)
    if calories != 0: winsound.Beep(1000, 200)
    return data, session_stats


def get_weather(target_area: str = "Singapore"):
    now = datetime.now().strftime("%I:%M %p")
    try:
        url = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
        resp = requests.get(url).json()
        for f in resp['items'][0]['forecasts']:
            if target_area.lower() in f['area'].lower(): return f"{f['area']}: {f['forecast']}", now
        return f"Singapore: {resp['items'][0]['forecasts'][0]['forecast']}", now
    except:
        return "Weather Offline", now


def draw_ui(location="Singapore"):
    p, live = update_daily_log(0, 0)
    weather, live_time = get_weather(location)

    table = Table.grid(expand=True)
    table.add_column(width=50)

    # Header & Points
    table.add_row(f"[bold white]🕒 {live_time}[/] | [green]🌤️ {escape(weather)}[/]")
    table.add_row(f"[bold gold1]🏆 HEALTH POINTS :[/] {HEALTH_POINTS} HP")
    table.add_row("-" * 55)

    # Progress Bar
    bar_color = "red" if live['calories'] > LIMIT else "green"
    bar_len = min(int((live['calories'] / LIMIT) * 20), 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)

    table.add_row(f"[yellow]CALORIES :[/] {live['calories']} / {LIMIT} kcal")
    table.add_row(f"  [{bar_color}]{bar}[/]")
    table.add_row(f"[cyan]EXERCISE :[/] {live['exercise_mins']} / 30 mins")

    # Motivation & Mission
    table.add_row(f"\n[bold orange3]🔥 {p.get('streak', 0)} DAY STREAK![/]")
    table.add_row(f"[magenta]MISSION  :[/] {escape(random.choice(GOALS))}")
    table.add_row(f"[italic white]QUOTE    :[/] {random.choice(MOTIVATION)}")

    console.print(Panel(table, title="☀️ SG HEALTH DASHBOARD", border_style="bright_blue", width=60, box=box.SQUARE))


# --- MAIN LOOP ---

while True:
    clear_screen()

    # Point Check: Reward for being active but under limit
    p, live = update_daily_log(0, 0)
    if 0 < live['calories'] <= LIMIT and not bonus_awarded:
        HEALTH_POINTS += 10
        bonus_awarded = True
        console.print("[bold gold1]⭐ BONUS: +10 HP for staying healthy today![/]")
        winsound.Beep(1500, 300)

    draw_ui(current_loc)
    user_input = console.input(f"\n[bold white]Action (HP: {HEALTH_POINTS}): [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Processing..."):
        try:
            # 1. HANDLE MISSION COMPLETION
            if "completed" in user_input.lower() and "mission" in user_input.lower():
                HEALTH_POINTS += 5
                winsound.Beep(2000, 100)
                winsound.Beep(2500, 100)
                console.print("\n[bold gold1]ADVISOR: Mission Complete! +5 HP earned. Keep it up![/]")

            # 2. HANDLE CAMERA / VISION (CALORIE ESTIMATOR)
            elif user_input.lower() == "snap" or any(ext in user_input.lower() for ext in [".jpg", ".png"]):
                vision_chat = client.chats.create(
                    model="gemini-2.0-flash",
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            f"You are a Singapore Calorie Expert. Current: {live['calories']}/{LIMIT}. "
                            "Analyze the food image. 1. Estimate calories (e.g. Chicken Rice: 660kcal). "
                            "2. Call 'update_daily_log'. 3. If this meal exceeds the limit, warn the user!"
                            "3. Read the weather from the url given on line 99 and if the user gives data about the any place in singapore mentioned in the weather, give the forecast and live weather of the particular area."
                        ),
                        tools=[update_daily_log]
                    )
                )
                if user_input.lower() == "snap":
                    file = capture_from_camera()
                    if not file: continue
                    img = Image.open(file)
                    response = vision_chat.send_message(message=["Analyze, estimate calories, and log them.", img])
                else:
                    filename = next((w for w in user_input.split() if "." in w), None)
                    img = Image.open(filename)
                    response = vision_chat.send_message(message=[f"Analyze {user_input} and log calories.", img])

                log_discovery("Vision Log", response.text)
                console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")

            # 3. HANDLE WEATHER & LOGGING (Custom Tools)
            elif any(word in user_input.lower() for word in ["weather", "log", "calories", "exercise"]):
                tool_chat = client.chats.create(
                    model="gemini-2.0-flash",
                    config=types.GenerateContentConfig(tools=[get_weather, update_daily_log])
                )
                response = tool_chat.send_message(message=user_input)
                console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")

            # 4. HANDLE RECOMMENDATIONS (Google Search)
            else:
                search_chat = client.chats.create(
                    model="gemini-2.0-flash",
                    config=types.GenerateContentConfig(tools=[{"google_search": {}}])
                )
                response = search_chat.send_message(message=f"Singapore Local Reviews & Unit Numbers: {user_input}")
                log_discovery("Food Discovery", response.text)
                console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")

            # Update dashboard location header if a Place name is detected
            for word in user_input.split():
                clean = word.strip("?!.,")
                if clean.istitle() and len(clean) > 3: current_loc = clean

        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")

    console.input("\n[dim]Press Enter to refresh...[/]")