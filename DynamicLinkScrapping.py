from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import logging
from typing import List, Set, Optional
from pathlib import Path


class NewsScraper:
    def __init__(
        self,
        base_url: str = "https://uat.moc.gov.kh",
        category: int = 2,
        headless: bool = False,
        timeout: int = 10,
    ) -> None:
        self.base_url: str = base_url
        self.page_url: str = f"{base_url}/news?category={category}"
        self.seen_links: Set[str] = set()
        self.all_links: List[str] = []
        self.timeout: int = timeout
        self.headless: bool = headless
        self.driver: Optional[webdriver.Chrome] = None
        self._setup_logging()

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("Dynamic.log"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def _setup_driver(self) -> webdriver.Chrome:
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")

        # Performance optimizations
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-images")
        options.add_argument(
            "--disable-javascript"
        )  # Only if JS isn't needed for link extraction
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        # Memory optimization
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=4096")

        driver = webdriver.Chrome(options=options)
        if not self.headless:
            driver.maximize_window()
        return driver

    def __enter__(self):
        self.driver = self._setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def load_page(self) -> bool:
        try:
            if not self.driver:
                self.driver = self._setup_driver()

            self.driver.get(self.page_url)

            # Use WebDriverWait instead of fixed sleep
            wait = WebDriverWait(self.driver, self.timeout)
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/news/']"))
            )

            self.logger.info("Page loaded successfully")
            return True

        except TimeoutException:
            self.logger.error(f"Timeout waiting for page to load: {self.page_url}")
            return False
        except Exception as e:
            self.logger.error(f"Error loading page: {e}")
            return False

    def extract_links(self) -> List[str]:
        try:
            elements: List[WebElement] = self.driver.find_elements(
                By.CSS_SELECTOR, "a[href^='/news/']"
            )
            new_links: List[str] = []

            for element in elements:
                try:
                    href: Optional[str] = element.get_attribute("href")
                    if href:
                        # Normalize link immediately
                        normalized_href = href.rstrip("/")
                        if normalized_href not in self.seen_links:
                            self.seen_links.add(normalized_href)
                            new_links.append(normalized_href)
                except Exception as e:
                    self.logger.warning(f"Error extracting href from element: {e}")
                    continue

            return new_links

        except NoSuchElementException:
            self.logger.warning("No news links found on current page")
            return []
        except Exception as e:
            self.logger.error(f"Error extracting links: {e}")
            return []

    def scroll_and_scrape(self) -> None:
        if not self.driver:
            self.logger.error("Driver not initialized")
            return

        last_height: int = self.driver.execute_script(
            "return document.body.scrollHeight"
        )
        no_new_content_count = 0
        max_no_content_iterations = (
            10  # Stop after 10 consecutive iterations with no new content
        )

        while no_new_content_count < max_no_content_iterations:
            # Optimized scrolling - scroll to specific position
            scroll_position = (
                "document.body.scrollHeight - 1080"
                if not self.headless
                else "document.body.scrollHeight - 1250"
            )
            self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")

            # Reduced wait time with dynamic adjustment
            time.sleep(3)

            new_links = self.extract_links()
            if new_links:
                self.all_links.extend(new_links)
                no_new_content_count = 0  # Reset counter
                self.logger.info(
                    f"Found {len(new_links)} new links. Total: {len(self.all_links)}"
                )
            else:
                no_new_content_count += 1
                self.logger.info(
                    f"No new links found. Attempt {no_new_content_count}/{max_no_content_iterations}"
                )

            new_height: int = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            if new_height == last_height:
                no_new_content_count += 1
            last_height = new_height

        self.logger.info("Finished scrolling and scraping")

    def get_unique_links(self) -> Set[str]:
        """Get unique normalized links"""
        return set(self.all_links)  # Already normalized in extract_links

    def show_links(self) -> None:
        unique_links = self.get_unique_links()
        print(f"✅ Total unique news links found: {len(unique_links)}")

    def save_links_to_file(self, filename: str = "news_links.txt") -> bool:
        try:
            filepath = Path(filename)
            unique_links = self.get_unique_links()

            with filepath.open("w", encoding="utf-8") as f:
                for link in sorted(unique_links):
                    f.write(link + "\n")

            self.logger.info(
                f"Saved {len(unique_links)} links to {filepath.absolute()}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error saving links to file: {e}")
            return False

    def cleanup(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Driver cleaned up successfully")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")


def main() -> None:
    # Use context manager for automatic cleanup
    with NewsScraper(headless=False, timeout=15) as scraper:
        try:
            print("Starting scraping...")
            start_time: float = time.time()

            if not scraper.load_page():
                print("Failed to load page. Exiting...")
                return

            scraper.scroll_and_scrape()
            scraper.show_links()

            if scraper.save_links_to_file():
                print("Links saved successfully!")

            end_time: float = time.time()
            elapsed: float = end_time - start_time
            print(f"\nScraping completed in {elapsed:.2f} seconds")

        except KeyboardInterrupt:
            print("\nScraping interrupted by user")
        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
