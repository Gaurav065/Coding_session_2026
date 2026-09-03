import sys
sys.stdout.reconfigure(encoding='utf-8')

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def debug_hrefs():
    print("Launching Undetected Chromedriver...")
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options)
    
    try:
        driver.get("https://www.kaggle.com/competitions/kaggriculture/leaderboard")
        wait = WebDriverWait(driver, 60)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[text()='Team']")))
        
        links = driver.find_elements(By.CSS_SELECTOR, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and 'submission' in href.lower():
                print(f"FOUND SUBMISSION HREF: {href}")
                
        # Also let's check Kaggle.State
        state = driver.execute_script("return window.Kaggle && window.Kaggle.State;")
        if state:
            print("Found window.Kaggle.State!")
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_hrefs()
