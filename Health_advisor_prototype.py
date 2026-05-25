import os
import json
from datetime import date
from dotenv import load_dotenv
from google import genai

# Setup
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- SETTINGS ---
LIMIT = 2000
STATS_FILE = "daily_stats.json"
TODAY = str(date.today())


def load_data():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            # Reset if it's a new day
            if data.get("date") != TODAY:
                return {"date": TODAY, "calories": 0, "exercise_mins": 0}
            return data
    return {"date": TODAY, "calories": 0, "exercise_mins": 0}


def save_data(data):
    with open(STATS_FILE, "w") as f:
        json.dump(data, f)


# Initialize data
user_stats = load_data()

print(f"--- Health Advisor Active (Limit: {LIMIT} kcal) ---")

while True:
    user_input = input("\nLog food/exercise (e.g., 'I ate 1 burger' or 'I ran 30 mins'): ")
    if user_input.lower() in ["exit", "quit"]: break

    # We send the current stats to Gemini so it can do the math and advice
    context = (
        f"CONTEXT: The user's daily limit is {LIMIT} kcal. "
        f"They have already consumed {user_stats['calories']} kcal today. "
        f"They have exercised for {user_stats['exercise_mins']} minutes. "
        "INSTRUCTIONS: 1. Estimate calories for any food mentioned. 2. Update the remaining budget. "
        "3. If calories > limit OR exercise < 30 mins, suggest a very light dinner like 'salad with mushrooms'."
        "4. Output format: 'Food [name] consumed [x] calories. Left with [y] calories.' followed by advice."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=context + "\nUser says: " + user_input
        )

        # Simple simulation of data update (Real apps use 'tool calling' for this,
        # but for now, we can extract it or let the AI 'tell' us)
        # For this version, let's assume Gemini is smart enough to guide the user.
        print(f"\nAssistant: {response.text}")

        # Note: In a full version, we would use 'Regex' or 'Tool Calling'
        # to pull the numbers back out of Gemini's text and save_data().

    except Exception as e:
        print(f"Error: {e}")