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
from PIL import Image  # Make sure to: pip install Pillow

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
def get_running_route(start_point: str = "Dakota Residences"):
    """Suggests a scenic 3-4km PCN route based on starting location."""
    routes = {
        "dakota": "Start: Dakota Residences PCN -> Mountbatten Bridge -> Geylang River PCN -> Tanjong Rhu Promenade -> Gardens by the Bay East (3.8km).",
        "bishan": "Start: Bishan-AMK Park -> Kallang PCN South -> St. Andrew's Village (3.2km).",
        "punggol": "Start: Punggol Waterway Point -> Sunrise Bridge -> Punggol East Container Park (3.9km)."
    }
    for key in routes:
        if key in start_point.lower(): return routes[key]
    return f"From {start_point}, hit the nearest PCN and run for 20 mins for a scenic 3.5km loop!"


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
        winsound.MessageBeep(winsound.MB_ICONHAND if data["calories"] > LIMIT else winsound.MB_ICONASTERISK)
    return data


# --- VISION MODE (PHOTO SCANNER) ---
def analyze_food_image(file_path: str):
    """Opens an image, identifies food, and returns calorie estimate."""
    if not os.path.exists(file_path):
        return "Error: File not found. Please place the image in the project folder."

    try:
        img = Image.open(file_path)
        prompt = "Identify the food in this image and provide a single total calorie estimate. Reply ONLY with: 'Food Name: [Name], Estimated Calories: [Number]'"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, img]
        )
        return response.text
    except Exception as e:
        return f"Error analyzing image: {e}"


# --- UI LOGIC ---
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def is_night_mode():
    now = datetime.now().hour
    return now >= 22 or now < 6


def draw_ui(location="Singapore"):
    data = update_daily_log(0, 0)
    weather = get_weather(location)
    night = is_night_mode()

    theme_color = "bright_black" if night else "bright_blue"
    bar_color = "red" if data['calories'] > LIMIT else ("blue" if night else "green")

    table = Table.grid(expand=True)
    table.add_column(width=50)

    progress = int((data['calories'] / LIMIT) * 20)
    bar = "#" * min(progress, 20) + "-" * max(0, 20 - progress)

    table.add_row(f"[yellow]CALORIES :[/] {data['calories']} / {LIMIT}")
    table.add_row(f"  [{bar_color}]\\[{bar}\\][/{bar_color}]")
    table.add_row(f"[cyan]EXERCISE :[/] {data['exercise_mins']} / 30 mins")
    table.add_row(f"[green]WEATHER  :[/] {escape(weather)}")
    table.add_row(f"\n[magenta]MISSION  :[/] {escape(random.choice(GOALS))}")

    console.print(Panel(table, title=f"[bold white]{'🌙 NIGHT MODE' if night else '☀️ HEALTH ADVISOR'}[/]",
                        border_style=theme_color, width=60, box=box.SQUARE))


# --- MAIN CHAT ---
instruction = (
    "You are a Health Advisor. Tools: 1. update_daily_log (stats) 2. get_weather 3. get_running_route (3-4km PCN routes). "
    "NEW FEATURE: If the user provides a filename (e.g. meal.jpg), tell them you are analyzing it. "
    "After analyzing food, ALWAYS call 'update_daily_log' to add those calories to their total."
)

chat = client.chats.create(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(system_instruction=instruction,
                                       tools=[get_weather, update_daily_log, get_running_route])
)

# --- RUN LOOP ---
current_loc = "Singapore"
while True:
    clear_screen()
    draw_ui(current_loc)

    user_input = console.input("\n[bold white]Command (or Image Name): [/]")
    if user_input.lower() in ["exit", "quit"]: break

    with console.status("[bold green]Advisor Processing..."):
        # Check if user mentioned an image file
        if any(ext in user_input.lower() for ext in [".jpg", ".png", ".jpeg"]):
            # Extract filename (simple logic)
            filename = next((word for word in user_input.split() if "." in word), None)
            if filename:
                vision_result = analyze_food_image(filename)
                user_input += f"\n(Internal Scan Result: {vision_result})"

        response = chat.send_message(user_input)

        # Location update logic
        for word in user_input.split():
            if word.istitle() and len(word) > 3: current_loc = word.strip("?!.,")

    console.print(f"\n[bold blue]ADVISOR:[/] {response.text}")
    console.input("\n[dim]Press Enter...[/]")