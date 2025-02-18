import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
import json

async def fetch_sitemap(url):
    """Fetch sitemap XML and save it to a file"""
    print(f"Fetching sitemap from: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content = await response.text()
            
            # Save raw XML
            with open('sitemap.xml', 'w', encoding='utf-8') as f:
                f.write(content)
            print("Saved sitemap.xml")
            
            return content

def parse_sitemap(xml_content):
    """Parse sitemap and analyze URL patterns"""
    root = ET.fromstring(xml_content)
    all_urls = []
    digit_ending_urls = []
    
    # Find all URLs in the sitemap
    for url in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        url_text = url.text
        # Store URL and its last segment for analysis
        last_segment = url_text.rstrip('/').split('/')[-1]
        all_urls.append({
            'url': url_text,
            'last_segment': last_segment
        })
        
        # Check if URL ends with digits
        if last_segment and last_segment[-1].isdigit():
            digit_ending_urls.append(url_text)
    
    # Save all URLs for analysis
    with open('all_urls.txt', 'w', encoding='utf-8') as f:
        for url_info in all_urls:
            f.write(f"URL: {url_info['url']}\n")
            f.write(f"Last segment: {url_info['last_segment']}\n")
            f.write("-" * 80 + "\n")
    
    # Save URLs ending with digits
    with open('digit_ending_urls.txt', 'w', encoding='utf-8') as f:
        for url in digit_ending_urls:
            f.write(f"{url}\n")
    
    print(f"Saved {len(all_urls)} URLs to all_urls.txt")
    print(f"Saved {len(digit_ending_urls)} URLs ending with digits to digit_ending_urls.txt")
    
    # Print sample URLs ending with digits
    print("\nSample URLs ending with digits:")
    for url in digit_ending_urls[:5]:
        print(f"- {url}")
    
    return all_urls, digit_ending_urls

async def extract_case_info(html_content):
    """
    Extract case information from the HTML content
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    cases = []
    
    # Try different class combinations to find the grid
    grid = soup.find('div', class_='candidate-filter-result visible grid')
    if not grid:
        grid = soup.find('div', class_='candidate-filter-result')
    if not grid:
        print("Debug: HTML content length:", len(html_content))
        print("Debug: First 500 chars of HTML:", html_content[:500])
        return cases

    # Find all grid items
    case_items = grid.find_all('div', {'class': 'candidate half-grid'})
    print(f"Found {len(case_items)} cases")
    
    for item in case_items:
        try:
            # Get case number from data-id attribute
            case_num = item.get('data-id', '')
            
            # Get title from the text content
            title = item.text.strip()
            
            # Get URL from href attribute
            url = item.get('href', '')
            if url and not url.startswith('http'):
                url = f"https://www.ultrasoundcases.info{url}"
            
            # Get thumbnail if available
            thumbnail = item.find('img')
            thumbnail_url = thumbnail.get('src', '') if thumbnail else ''
            
            cases.append({
                'title': title,
                'url': url,
                'case_number': case_num,
                'thumbnail_url': thumbnail_url
            })
            print(f"Debug: Extracted case {case_num}: {title}")
        except Exception as e:
            print(f"Error processing case item: {e}")
            print(f"Item HTML: {item}")
    
    return cases

async def main():
    print("Starting sitemap analysis...")
    
    # Fetch and save sitemap
    sitemap_url = "https://www.ultrasoundcases.info/sitemap.xml"
    sitemap_content = await fetch_sitemap(sitemap_url)
    
    # Analyze URLs
    urls, digit_urls = parse_sitemap(sitemap_content)
    
    print(f"\nTotal URLs found: {len(urls)}")
    print(f"URLs ending with digits: {len(digit_urls)}")

if __name__ == "__main__":
    asyncio.run(main())