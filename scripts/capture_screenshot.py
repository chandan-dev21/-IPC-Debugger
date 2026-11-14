"""
Automated Multi-View Screenshot Capture Script
Captures authentic screenshots of all tabs in the IPC Debugger dashboard.
"""

import os
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

PORT = 8504
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

print("[1/5] Starting Streamlit server on port", PORT)
proc = subprocess.Popen(
    [
        "python",
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        str(PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

time.sleep(5)

try:
    print("[2/5] Initializing headless Chrome...")
    options = Options()
    options.binary_location = CHROME_PATH
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    url = f"http://localhost:{PORT}"
    driver.get(url)
    time.sleep(4)

    # 1. System Overview
    driver.save_screenshot(os.path.join(ASSETS_DIR, "dashboard_overview.png"))
    print("Saved dashboard_overview.png")

    tabs = [
        ("Pipes Lab", "pipes_lab.png"),
        ("Message Queues Lab", "queues_lab.png"),
        ("Shared Memory Lab", "shared_memory_lab.png"),
        ("Deadlock & Bottleneck Lab", "deadlock_lab.png"),
        ("Metrics & History", "metrics_history.png"),
    ]

    for label, filename in tabs:
        try:
            # Find radio button label and click
            radio_elements = driver.find_elements(By.XPATH, f"//p[contains(text(), '{label}')]")
            if radio_elements:
                radio_elements[0].click()
                time.sleep(2.5)
                driver.save_screenshot(os.path.join(ASSETS_DIR, filename))
                print(f"Saved {filename}")
        except Exception as e:
            print(f"Could not capture {label}: {e}")

    driver.quit()
except Exception as e:
    print(f"Error during capture: {e}")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
    print("Streamlit process stopped.")
