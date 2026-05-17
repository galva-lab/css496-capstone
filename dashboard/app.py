import requests
import time

BACKEND_URL = "http://127.0.0.1:8000/latest"

while True:
    response = requests.get(BACKEND_URL)
    data = response.json()

    print("\nLATEST SENSOR DATA")
    print("------------------")
    print(data)

    time.sleep(3)