from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

# === Setup Chrome ===
options = Options()
# options.add_argument("--headless")  # Uncomment to run headless if needed
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)

# === Load page ===
URL = "https://uat.moc.gov.kh/news?category=2"
driver.get(URL)
time.sleep(5)  # Wait for page to load fully

# === Scroll to just above the footer ===
footer = driver.find_element(By.CSS_SELECTOR, "body > div > footer")
driver.execute_script("""
    window.scrollTo(0, arguments[0].offsetTop - window.innerHeight);
""", footer)

time.sleep(3)  # Pause so you can see the scroll

# === Insert a new div above the footer ===
driver.execute_script("""
    let footer = document.querySelector('body > div > footer');
    let newDiv = document.createElement('div');
    newDiv.style.background = '#ffeb3b';
    newDiv.style.padding = '20px';
    newDiv.style.textAlign = 'center';
    newDiv.style.fontSize = '18px';
    newDiv.textContent = 'This div is inserted just above the footer!';
    footer.parentNode.insertBefore(newDiv, footer);
""")

time.sleep(5)  # Pause to see the inserted element

# Cleanup
driver.quit()
