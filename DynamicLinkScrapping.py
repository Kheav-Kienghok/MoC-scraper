from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webelement import WebElement
import time
import threading
from typing import List, Set


class NewsScraper:
    def __init__(self, base_url: str = "https://uat.moc.gov.kh", category: int = 2) -> None:
        self.base_url: str = base_url
        self.page_url: str = f"{base_url}/news?category={category}"
        self.seen_links: Set[str] = set()
        self.all_links: List[str] = []
        self.normalized: Set[str] = set()
        self.driver: webdriver.Chrome = self._setup_driver()

    def _setup_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        return driver
    
    def load_page(self) -> None:
        self.driver.get(self.page_url)
        time.sleep(5)  # wait for full load

    def extract_links(self) -> List[str]:
        elements: List[WebElement] = self.driver.find_elements(By.CSS_SELECTOR, "a[href^='/news/']")
        new_links: List[str] = []
        for element in elements:
            href: str | None = element.get_attribute("href")
            if href and href not in self.seen_links:
                self.seen_links.add(href)
                new_links.append(href)
        return new_links

    def scroll_and_scrape(self) -> None:
        last_height: int = self.driver.execute_script("return document.body.scrollHeight")

        while True:

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1250);")
            time.sleep(7)

            new_links = self.extract_links()
            if new_links:
                self.all_links.extend(new_links)

            new_height: int = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def show_links(self) -> None:
        # Normalize links by removing trailing slashes and deduplicate
        self.normalized = set(link.rstrip("/") for link in self.all_links)
        print(f"✅ Total unique news links found: {len(self.normalized)}")

        # for link in sorted(normalized):
        #     print(link)

    def save_links_to_file(self, filename: str = "news_links.txt") -> None:

        if not self.normalized:
            self.normalized = set(link.rstrip("/") for link in self.all_links)
        with open(filename, "w", encoding="utf-8") as f:
            for link in sorted(self.normalized):
                f.write(link + "\n")

    def save_screenshot(self, filename: str = "screenshot.png") -> None:
        self.driver.save_screenshot(filename)

    def cleanup(self) -> None:
        self.driver.quit()


def main() -> None:
    scraper = NewsScraper()
    try:
        print("Starting scraping...")
        start_time: float = time.time()

        scraper.load_page()
        scraper.scroll_and_scrape()
        scraper.show_links()
        scraper.save_links_to_file()

        end_time: float = time.time()
        elapsed: float = end_time - start_time
        print(f"\nScraping completed in {elapsed:.2f} seconds")

        user_input_received: bool = False

        def wait_for_input() -> None:
            nonlocal user_input_received
            input("Press Enter to exit (auto-exits in 10 seconds)...")
            user_input_received = True

        input_thread = threading.Thread(target=wait_for_input, daemon=True)
        input_thread.start()

        wait_start: float = time.time()
        while time.time() - wait_start < 10:
            if user_input_received:
                break
            time.sleep(0.1)

        if not user_input_received:
            print("\nNo input received. Auto exiting...")

    finally:
        scraper.cleanup()


if __name__ == "__main__":
    main()
