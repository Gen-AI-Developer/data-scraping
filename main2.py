import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig

async def extract_cases(html_content):
    """Extract case names and links from the JSON data in the page"""
    # Find the JSON data between <div id="jsoncats"> tags
    start_idx = html_content.find('<div id="jsoncats"')
    if start_idx == -1:
        print("Warning: Could not find jsoncats div")
        return []
    
    # Extract the JSON string
    json_start = html_content.find('[', start_idx)
    json_end = html_content.find(']', json_start) + 1
    json_str = html_content[json_start:json_end]
    
    # Parse JSON and extract case info
    try:
        cases = json.loads(json_str)
        return [
            {
                'name': case['header'],
                'url': f"https://www.ultrasoundcases.info/cases/{case['listLocation']}/",
                'category_id': case['id']
            }
            for case in cases
        ]
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print(f"JSON string found: {json_str[:200]}...")  # Print first 200 chars of JSON
        return []

async def main():
    browser_config = BrowserConfig()
    run_config = CrawlerRunConfig()
    
    # Enable JavaScript execution
    browser_config.javascript = True
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://www.ultrasoundcases.info/",
            config=run_config
        )
        
        # Extract cases from the raw HTML content
        cases = await extract_cases(result.html)
        
        # Print the results
        print("\nUltrasound Cases Categories:")
        print("-" * 50)
        for case in cases:
            print(f"Name: {case['name']}")
            print(f"URL: {case['url']}")
            print(f"Category ID: {case['category_id']}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())