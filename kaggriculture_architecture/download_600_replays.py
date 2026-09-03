import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import time
import subprocess
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

REPLAY_DIR = r"D:\replays"
os.makedirs(REPLAY_DIR, exist_ok=True)

def fetch_top_20_episodes():
    submission_ids = []
    
    print("Launching Undetected Chromedriver...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    try:
        df = pd.read_csv('kaggriculture-publicleaderboard.csv')
        df = df.sort_values(by='Score', ascending=False)
        top_20_teams = df.head(20)['TeamName'].tolist()
    except Exception as e:
        print(f"Error reading CSV: {e}")
        driver.quit()
        return

    try:
        driver.get("https://www.kaggle.com/competitions/kaggriculture/leaderboard")
        wait = WebDriverWait(driver, 60)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[text()='Team']")))
        time.sleep(3)
        
        for idx, team_name in enumerate(top_20_teams):
            try:
                safe_name = str(team_name).encode('utf-8', 'replace').decode('utf-8')
                
                # Find the row
                element = driver.find_element(By.XPATH, f"//*[text()='{safe_name}' or contains(text(), '{safe_name}')]")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(1)
                
                # Fire a true React-compatible bubbling click event!
                driver.execute_script("""
                    var ev = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    arguments[0].dispatchEvent(ev);
                """, element)
                
                time.sleep(4)
                
                current_url = driver.current_url
                if 'submissionId=' in current_url:
                    sub_id = current_url.split('submissionId=')[1].split('&')[0]
                    if sub_id not in submission_ids:
                        submission_ids.append(sub_id)
                        print(f"[{idx+1}/20] Successfully extracted Submission ID for {safe_name}: {sub_id}")
                else:
                    print(f"[{idx+1}/20] URL didn't update for {safe_name} (URL: {current_url})")
                    
                # Close Modal
                driver.execute_script("""
                    var escapeEvent = new KeyboardEvent('keydown', {
                        key: 'Escape',
                        code: 'Escape',
                        keyCode: 27,
                        which: 27,
                        bubbles: true
                    });
                    document.dispatchEvent(escapeEvent);
                """)
                time.sleep(1)
            except Exception as e:
                print(f"[{idx+1}/20] Failed for {safe_name}: {e}")
                
    finally:
        driver.quit()

    print(f"\nExtracted {len(submission_ids)} unique Submission IDs.")
    
    if not submission_ids:
        print("No submission IDs found. Exiting.")
        return

    # Bulk download
    for sub_id in submission_ids:
        print(f"\nFetching episodes for Submission ID {sub_id}...")
        result = subprocess.run(
            ["python", "-m", "kaggle", "competitions", "episodes", str(sub_id)], 
            capture_output=True, text=True
        )
        
        lines = result.stdout.split('\n')
        ep_ids = []
        for line in lines:
            parts = line.split()
            if parts and parts[0].isdigit():
                ep_ids.append(parts[0])
                
        top_30 = ep_ids[:30]
        print(f"Downloading {len(top_30)} replays for Submission {sub_id}...")
        
        for ep_id in top_30:
            print(f"  Downloading Episode {ep_id}...")
            subprocess.run(
                ["python", "-m", "kaggle", "competitions", "replay", str(ep_id), "-p", REPLAY_DIR]
            )

    print("\nAll 600 replays have been downloaded!")

if __name__ == "__main__":
    fetch_top_20_episodes()
