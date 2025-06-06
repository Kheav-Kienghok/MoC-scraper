import requests
from bs4 import BeautifulSoup

def extract_link(url):
    """
    Extracts all (text, href) pairs from <a> tags inside <div class="tp-blog__link">
    within the <div id="blog-one-page"> of the given URL.
    Returns a list of tuples: (link_text, href)
    """
    response = requests.get(url)
    response.encoding = 'utf-8'

    links = []

    if response.status_code == 200:
        extract_text = BeautifulSoup(response.text, 'html.parser')
        blog_div = extract_text.find('div', id='blog-one-page')
        if blog_div:
            blog_links = blog_div.find_all('div', class_='tp-blog__link')
            for link_div in blog_links:
                a_tag = link_div.find('a')
                if a_tag and a_tag.has_attr('href'):
                    links.append(a_tag['href'])
        else:
            print("No blog-one-page div found.")
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")

    return links

# Example usage:
if __name__ == "__main__":
    url = "https://cambodiaip.gov.kh"
    for href in extract_link(url):
        print(f"Link: {href}")
