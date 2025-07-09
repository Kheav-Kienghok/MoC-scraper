import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import os
import time


def is_valid_url(url, base_domain):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ["http", "https"]
            and parsed.netloc
            and url.startswith(f"https://{base_domain}")
        )
    except:
        return False


def is_useful_link(link):
    return not (link.lower().endswith(".pdf") or "#" in link)


async def is_url_ok(session, url):
    try:
        async with session.head(
            url, timeout=10, allow_redirects=True, ssl=False
        ) as response:
            return response.status == 200
    except:
        return False


async def extract_links(session, url):
    links = []
    try:
        async with session.get(url, timeout=10, ssl=False) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup.find_all("a", href=True):
                    href = tag.get("href")
                    absolute_url = urljoin(url, href)
                    links.append(absolute_url)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return links


async def crawl_website(start_url, max_depth=2, concurrency=10):
    base_domain = urlparse(start_url).netloc
    visited_urls = set()
    all_links = set()
    queue = deque([(start_url, 0)])
    semaphore = asyncio.Semaphore(concurrency)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        print(f"Starting async crawl of {start_url} with max depth {max_depth}")

        while queue:
            tasks = []
            batch = []

            while queue and len(batch) < concurrency:
                url, depth = queue.popleft()
                if (
                    url in visited_urls
                    or depth > max_depth
                    or not is_valid_url(url, base_domain)
                ):
                    continue
                visited_urls.add(url)
                batch.append((url, depth))

            for url, depth in batch:
                tasks.append(
                    handle_url(
                        session,
                        url,
                        depth,
                        base_domain,
                        queue,
                        all_links,
                        visited_urls,
                        max_depth,
                        semaphore,
                    )
                )

            await asyncio.gather(*tasks)

        return all_links


async def handle_url(
    session,
    url,
    depth,
    base_domain,
    queue,
    all_links,
    visited_urls,
    max_depth,
    semaphore,
):
    async with semaphore:
        print(f"Crawling (depth {depth}): {url}")
        links = await extract_links(session, url)
        for link in links:
            if is_useful_link(link) and link.startswith(f"https://{base_domain}"):
                ok = await is_url_ok(session, link)
                if ok and link not in visited_urls:
                    print(f"  ✅ Found: {link}") 
                    all_links.add(link)
                    if depth + 1 <= max_depth:
                        queue.append((link, depth + 1))


def save_links_by_type(
    all_links, link_file="crawled_links.txt", pdf_file="pdf_links.txt"
):
    try:
        os.makedirs(
            os.path.dirname(link_file) if os.path.dirname(link_file) else ".",
            exist_ok=True,
        )

        normal_links = sorted(
            [link for link in all_links if not link.lower().endswith(".pdf")]
        )
        pdf_links = sorted(
            [link for link in all_links if link.lower().endswith(".pdf")]
        )

        with open(link_file, "w", encoding="utf-8") as file:
            file.write(f"Total non-PDF links: {len(normal_links)}\n")
            file.write("=" * 50 + "\n\n")
            for i, link in enumerate(normal_links, 1):
                file.write(f"{i:4d}. {link}\n")

        with open(pdf_file, "w", encoding="utf-8") as file:
            file.write(f"Total PDF links: {len(pdf_links)}\n")
            file.write("=" * 50 + "\n\n")
            for i, link in enumerate(pdf_links, 1):
                file.write(f"{i:4d}. {link}\n")

        print(f"Saved {len(normal_links)} non-PDF links to {link_file}")
        print(f"Saved {len(pdf_links)} PDF links to {pdf_file}")

    except Exception as e:
        print(f"Error saving links: {e}")


def main():
    start_url = "https://mfaic.gov.kh/"
    print("Starting comprehensive web crawl...")
    print(f"Target website: {start_url}")

    start_time = time.time()

    all_links = asyncio.run(crawl_website(start_url=start_url))

    print(f"\nCrawling completed!")
    print(f"Total unique and usable links found: {len(all_links)}")

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time taken: {elapsed_time:.2f} seconds")

    save_links_by_type(
        all_links, link_file="crawled_links.txt", pdf_file="pdf_links.txt"
    )

    print(f"\nSample of non-PDF links:")
    sample_links = sorted([l for l in all_links if not l.lower().endswith(".pdf")])[:10]
    for i, link in enumerate(sample_links, 1):
        print(f"  {i}. {link}")
    if len(all_links) > 10:
        print(f"  ... and more links saved to file.")


if __name__ == "__main__":
    main()
