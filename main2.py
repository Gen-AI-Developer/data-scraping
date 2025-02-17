import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

async def extract_main_categories(html_content):
    """Extract main category names and links from the JSON data"""
    start_idx = html_content.find('<div id="jsoncats"')
    if start_idx == -1:
        print("Warning: Could not find jsoncats div")
        return []
    
    json_start = html_content.find('[', start_idx)
    json_end = html_content.find(']', json_start) + 1
    json_str = html_content[json_start:json_end]
    
    try:
        categories = json.loads(json_str)
        return [
            {
                'name': cat['header'],
                'url': f"https://www.ultrasoundcases.info/cases/{cat['listLocation']}/",
                'category_id': cat['id']
            }
            for cat in categories
        ]
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"JSON string found: {json_str[:200]}...")
        return []

async def extract_subcases(html_content):
    """Extract individual cases from a category page"""
    soup = BeautifulSoup(html_content, 'html.parser')
    cases = []
    
    # Find all case entries
    case_entries = soup.find_all('article', class_='blog-grid')
    
    for entry in case_entries:
        try:
            # Extract case details
            title_elem = entry.find('h3')
            if title_elem and title_elem.find('a'):
                title = title_elem.find('a').text.strip()
                url = title_elem.find('a')['href']
                
                # Extract description if available
                desc_elem = entry.find('p')
                description = desc_elem.text.strip() if desc_elem else "No description available"
                
                # Extract author if available
                author_elem = entry.find('div', class_='author')
                author = author_elem.text.strip() if author_elem else "Unknown author"
                
                cases.append({
                    'title': title,
                    'url': f"https://www.ultrasoundcases.info{url}" if not url.startswith('http') else url,
                    'description': description,
                    'author': author
                })
        except Exception as e:
            print(f"Error extracting case details: {e}")
            continue
            
    return cases

async def main():
    browser_config = BrowserConfig()
    run_config = CrawlerRunConfig()
    
    # Enable JavaScript execution
    browser_config.javascript = True
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # First get main categories
        result = await crawler.arun(
            url="https://www.ultrasoundcases.info/",
            config=run_config
        )
        
        main_categories = await extract_main_categories(result.html)
        
        print("\nUltrasound Cases Categories and Subcases:")
        print("=" * 80)
        
        # Visit each category URL and extract subcases
        for category in main_categories:
            print(f"\nCategory: {category['name']}")
            print("-" * 80)
            
            # Crawl the category page
            category_result = await crawler.arun(
                url=category['url'],
                config=run_config
            )
            
            # Extract subcases
            subcases = await extract_subcases(category_result.html)
            
            # Print subcases
            if subcases:
                for case in subcases:
                    print(f"\nTitle: {case['title']}")
                    print(f"URL: {case['url']}")
                    print(f"Description: {case['description']}")
                    print(f"Author: {case['author']}")
                    print("-" * 40)
            else:
                print("No cases found in this category")
            
            # Add a small delay between requests to be polite
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())