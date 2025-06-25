import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import os


def is_valid_url(url, base_domain):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ['http', 'https'] and
            parsed.netloc and
            url.startswith(f"https://{base_domain}")
        )
    except:
        return False


def is_useful_link(link):
    return not (link.lower().endswith(".pdf") or "#" in link)


async def is_url_ok(session, url):
    try:
        async with session.head(url, timeout=10, allow_redirects=True) as response:
            return response.status == 200
    except:
        return False


async def extract_links(session, url):
    links = []
    try:
        async with session.get(url, timeout=10) as response:
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

    async with aiohttp.ClientSession() as session:
        print(f"Starting async crawl of {start_url} with max depth {max_depth}")

        while queue:
            tasks = []
            batch = []

            # Collect URLs at current depth
            while queue and len(batch) < concurrency:
                url, depth = queue.popleft()
                if url in visited_urls or depth > max_depth or not is_valid_url(url, base_domain):
                    continue
                visited_urls.add(url)
                batch.append((url, depth))

            for url, depth in batch:
                tasks.append(handle_url(session, url, depth, base_domain, queue, all_links, visited_urls, max_depth, semaphore))

            await asyncio.gather(*tasks)

        return all_links


async def handle_url(session, url, depth, base_domain, queue, all_links, visited_urls, max_depth, semaphore):
    async with semaphore:
        print(f"Crawling (depth {depth}): {url}")
        links = await extract_links(session, url)
        for link in links:
            if is_useful_link(link) and link.startswith(f"https://{base_domain}"):
                ok = await is_url_ok(session, link)
                if ok and link not in visited_urls:
                    all_links.add(link)
                    if depth + 1 <= max_depth:
                        queue.append((link, depth + 1))


def save_links_to_file(links, filename="crawled_links.txt"):
    try:
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        sorted_links = sorted(links)

        with open(filename, 'w', encoding='utf-8') as file:
            file.write(f"Total unique links found: {len(sorted_links)}\n")
            file.write("=" * 50 + "\n\n")
            for i, link in enumerate(sorted_links, 1):
                file.write(f"{i:4d}. {link}\n")

        print(f"Successfully saved {len(sorted_links)} links to {filename}")
    except Exception as e:
        print(f"Error saving to file: {e}")


def main():
    start_url = "https://www.mfaic.gov.kh/"
    print("Starting comprehensive async web crawl...")
    print(f"Target website: {start_url}")

    all_links = asyncio.run(crawl_website(start_url=start_url, max_depth=2, concurrency=10))

    print(f"\nCrawling completed!")
    print(f"Total unique and usable links found: {len(all_links)}")

    output_file = "crawled_links.txt"
    save_links_to_file(all_links, output_file)

    print(f"\nResults saved to: {output_file}")
    print("Sample links:")
    for i, link in enumerate(sorted(all_links)[:10], 1):
        print(f"  {i}. {link}")
    if len(all_links) > 10:
        print(f"  ... and {len(all_links) - 10} more links")


if __name__ == "__main__":
    main()
