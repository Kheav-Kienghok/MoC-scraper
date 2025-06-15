import aiohttp
import asyncio
import aiofiles

GRAPHQL_URL = "https://uat-graph.moc.gov.kh/graphql"
BASE_URL = "https://uat.moc.gov.kh/kh/news"

QUERY = """
query publicNewsList($filter: FilterNews, $pagination: PaginationInput, $websiteId: Int!, $newsCategoryId: Int) {
  publicNewsList(
    filter: $filter
    pagination: $pagination
    websiteId: $websiteId
    newsCategoryId: $newsCategoryId
  ) {
    data {
      id
      title
      title_en
      description
      description_en
      thumbnail
      summary
      summary_en
      created_at
      published_date
      category {
        id
        name
        name_en
      }
    }
    pagination {
      total
    }
  }
}
"""

async def fetch_page(session, page, website_id, news_category_id, page_size):
    """Fetch a single page of news data."""
    variables = {
        "filter": {"status": "PUBLISHED"},
        "pagination": {"page": page, "size": page_size},
        "websiteId": website_id,
        "newsCategoryId": news_category_id
    }

    async with session.post(
        GRAPHQL_URL,
        json={"query": QUERY, "variables": variables}
    ) as response:
        response.raise_for_status()
        data = await response.json()

        # Check for errors
        if "errors" in data:
            print(f"GraphQL errors on page {page}:", data["errors"])
            return None, None

        news_list = data["data"]["publicNewsList"]["data"]
        total = data["data"]["publicNewsList"]["pagination"]["total"]
        
        print(f"Fetched page {page} with {len(news_list)} items.")
        return news_list, total

async def fetch_all_news(website_id=1, news_category_id=0, page_size=100):
    """Fetch all news using async requests."""
    async with aiohttp.ClientSession() as session:
        # First, get the first page to determine total count
        first_page_data, total = await fetch_page(session, 1, website_id, news_category_id, page_size)
        
        if first_page_data is None:
            return []

        all_news = first_page_data.copy()
        
        # Calculate total pages needed
        total_pages = (total + page_size - 1) // page_size
        
        if total_pages > 1:
            # Create tasks for remaining pages
            tasks = []
            for page in range(2, total_pages + 1):
                task = fetch_page(session, page, website_id, news_category_id, page_size)
                tasks.append(task)
            
            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    print(f"Error fetching page: {result}")
                    continue
                
                news_list, _ = result
                if news_list:
                    all_news.extend(news_list)

    print(f"Total news fetched: {len(all_news)} (Expected total: {total})")
    return all_news

async def save_news_ids(news_data, filename="news_ids.txt"):
    """Save news IDs to file asynchronously."""
    ids = [f"{BASE_URL}/{item['id']}" for item in news_data]
    
    async with aiofiles.open(filename, "w") as f:
        for news_id in ids:
            await f.write(f"{news_id}\n")
    
    return ids

async def main():
    """Main async function."""
    print("Starting news fetch...")
    news = await fetch_all_news()
    
    if news:
        ids = await save_news_ids(news)
        print(f"{len(ids)} unique news items fetched and saved.")
    else:
        print("No news items fetched.")

if __name__ == "__main__":
    asyncio.run(main())