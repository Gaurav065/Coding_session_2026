import os
import time
from playwright.sync_api import sync_playwright

REPLAY_DIR = r"D:\replays"
os.makedirs(REPLAY_DIR, exist_ok=True)

def scrape_kaggle_replays():
    print(f"Starting Kaggle Scraper. Replays will be saved to {REPLAY_DIR}")
    
    with sync_playwright() as p:
        # Launch browser (non-headless is often better for bypassing bot detection)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        print("Navigating to Kaggriculture Leaderboard...")
        page.goto("https://www.kaggle.com/competitions/kaggriculture/leaderboard")
        
        # Wait for the leaderboard to load
        page.wait_for_selector("ul.leaderboard-list", timeout=15000)
        
        print("Scraping Top 20 Players...")
        # Get the top 20 rows
        rows = page.query_selector_all("li.leaderboard__row")[:20]
        
        for index, row in enumerate(rows):
            # Extract team name / player name
            team_name_element = row.query_selector("a.team-link")
            if not team_name_element:
                continue
            
            team_name = team_name_element.inner_text().strip()
            print(f"[{index+1}/20] Processing Team: {team_name}")
            
            # Click on the team to view their latest submissions/episodes
            # Note: Kaggle requires navigating to their specific episode list to download the JSON replay
            team_url = team_name_element.get_attribute("href")
            
            # Open a new tab for the team's episodes
            team_page = context.new_page()
            team_page.goto(f"https://www.kaggle.com{team_url}")
            
            try:
                # Find the latest completed episode download button
                team_page.wait_for_selector("button[aria-label='Download replay']", timeout=5000)
                download_buttons = team_page.query_selector_all("button[aria-label='Download replay']")
                
                if download_buttons:
                    print(f"Downloading replay for {team_name}...")
                    with team_page.expect_download() as download_info:
                        download_buttons[0].click()
                    
                    download = download_info.value
                    file_path = os.path.join(REPLAY_DIR, f"{team_name}_replay.json")
                    download.save_as(file_path)
                    print(f"Saved: {file_path}")
                else:
                    print(f"No replay found for {team_name}")
                    
            except Exception as e:
                print(f"Could not download replay for {team_name}: {e}")
                
            team_page.close()
            time.sleep(2) # Be polite to Kaggle servers
            
        browser.close()
        print("Scraping complete!")

if __name__ == "__main__":
    scrape_kaggle_replays()
