import requests
import random
import time

BACKEND_URL = "http://127.0.0.1:8000/sensor-data"

while True:
    data = {
        "motion": random.choice([True, False]),
        "sound_level": random.randint(30, 120),
        "gas_level": random.randint(20, 500)
    }

    try:
        response = requests.post(BACKEND_URL, json=data)

        print("Sent:", data)
        print("Server:", response.json())

    except Exception as e:
        print("Error:", e)

    time.sleep(5)