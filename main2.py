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
                'category_id': cat['id'],
                'list_location': cat['listLocation']
            }
            for cat in categories
        ]
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return []

async def extract_subcategories(html_content, category_name):
    """Extract subcategories from a category page"""
    soup = BeautifulSoup(html_content, 'html.parser')
    subcategories = []
    
    # Find the category section
    category_sections = soup.find_all('h4')
    for section in category_sections:
        if category_name in section.text:
            # Get the list of subcategories that follows
            subcat_list = section.find_next('ul')
            if subcat_list:
                for item in subcat_list.find_all('li'):
                    subcategories.append({
                        'name': item.text.strip(),
                        'parent_category': category_name
                    })
    
    return subcategories

async def main():
    browser_config = BrowserConfig()
    run_config = CrawlerRunConfig()
    
    # Enable JavaScript execution
    browser_config.javascript = True
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # First get main categories
        result = await crawler.arun(
            url="https://www.ultrasoundcases.info/cases/peripheral-vessels/",
            config=run_config
        )
        
        main_categories = await extract_main_categories(result.html)
        
        print("\nUltrasound Cases Categories and Subcategories:")
        print("=" * 80)
        
        # Process each main category
        for category in main_categories:
            print(f"\nMain Category: {category['name']}")
            print(f"URL: {category['url']}")
            print("-" * 80)
            
            # Extract subcategories
            subcategories = await extract_subcategories(result.html, category['name'])
            
            if subcategories:
                print("\nSubcategories:")
                for subcat in subcategories:
                    print(f"- {subcat['name']}")
            else:
                print("No subcategories found")
            
            print("-" * 40)
            
            # Add a small delay between requests to be polite
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())