import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup
import re

async def extract_main_categories(html_content):
    """
    Extract main category information from the HTML content's JSON data.
    
    Args:
        html_content (str): The HTML content containing the JSON categories data.
        
    Returns:
        list: A list of dictionaries containing category information with keys:
            - name (str): The category header/name
            - url (str): The full URL to the category page
            - category_id (str): The unique identifier for the category
            - list_location (str): The URL path component for the category
            
    Example:
        [
            {
                'name': 'Peripheral Vessels',
                'url': 'https://www.ultrasoundcases.info/cases/peripheral-vessels/',
                'category_id': '123',
                'list_location': 'peripheral-vessels'
            },
            ...
        ]
    """
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
    """
    Extract subcategory information for a given main category from the HTML content.
    
    Args:
        html_content (str): The HTML content of the category page.
        category_name (str): The name of the main category to find subcategories for.
        
    Returns:
        list: A list of dictionaries containing subcategory information with keys:
            - name (str): The subcategory name
            - url (str): The full URL to the subcategory page
            - parent_category (str): The name of the parent main category
            
    Example:
        [
            {
                'name': 'Carotid Artery',
                'url': 'https://www.ultrasoundcases.info/cases/peripheral-vessels/carotid/',
                'parent_category': 'Peripheral Vessels'
            },
            ...
        ]
    """
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
                    link = item.find('a')
                    if link:
                        url = link.get('href', '')
                        # Ensure URL is absolute
                        if url and not url.startswith('http'):
                            url = f"https://www.ultrasoundcases.info{url}"
                        
                        subcategories.append({
                            'name': item.text.strip(),
                            'url': url,
                            'parent_category': category_name
                        })
    
    return subcategories

async def extract_cases(html_content):
    """
    Extract cases from a subcategory page.
    
    Args:
        html_content (str): The HTML content of the subcategory page.
        
    Returns:
        tuple: (list of case dictionaries, total case count)
            Each case dictionary contains:
            - title (str): The title of the case
            - url (str): The URL to the case
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    cases = []
    
    # Find the filtered candidate wrapper div
    wrapper = soup.find('div', class_='filtered-candidate-wrapper')
    if wrapper:
        # Find all case items with class 'candidate'
        case_items = wrapper.find_all('div', class_='candidate')
        
        for item in case_items:
            link = item.get('href')
            if link and not link.startswith('http'):
                url = f"https://www.ultrasoundcases.info{link}"
                
                # The case ID/number is in the data-id attribute
                case_num = item.get('data-id', '')
                
                # The title is the text content of the div
                title = item.text.strip()
                
                # Format the title to match expected output
                # Extract the case count using regex to handle numbers properly
                match = re.match(r'(.*?)(\d+)\s*Cases', title)
                if match:
                    main_title = match.group(1).strip()
                    case_count = match.group(2).strip()
                    title = f"{main_title} - {case_count} Cases"
                
                cases.append({
                    'title': title,
                    'url': url,
                    'case_number': case_num
                })
    
    return cases, len(cases)

async def main():
    """
    Main async function to crawl and extract ultrasound case categories, subcategories,
    and their cases.
    """
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
        
        print("\nUltrasound Cases Categories, Subcategories, and Cases:")
        print("=" * 80)
        
        # Process each main category
        for category in main_categories:
            print(f"\nMain Category: {category['name']}")
            print(f"URL: {category['url']}")
            print("-" * 80)
            
            # Get category page content
            category_result = await crawler.arun(
                url=category['url'],
                config=run_config
            )
            
            # Extract subcategories
            subcategories = await extract_subcategories(category_result.html, category['name'])
            
            if subcategories:
                print("\nSubcategories:")
                for subcat in subcategories:
                    print(f"\n- {subcat['name']}")
                    print(f"  URL: {subcat['url']}")
                    print()  # Add blank line after URL
                    
                    # Get subcategory page content and extract cases
                    subcat_result = await crawler.arun(
                        url=subcat['url'],
                        config=run_config
                    )
                    
                    cases, case_count = await extract_cases(subcat_result.html)
                    print(f"  Number of cases: {case_count}")
                    
                    if cases:
                        print("  Cases:")
                        for case in cases:
                            print(f"    • Case {case['case_number']}: {case['title']}")
                            print(f"      {case['url']}")
                    
                    # Add a small delay between requests
                    await asyncio.sleep(1)
            else:
                print("No subcategories found")
            
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(main())