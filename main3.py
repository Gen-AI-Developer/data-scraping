import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
import json
import csv
import re

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

async def extract_case_info(html_content, url):
    """Extract key information from a case page"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Initialize case info dictionary
    case_info = {
        'url': url,
        'case_of_month_date': '',
        'title': '',
        'clinical_info': '',
        'question': '',
        'options': '',
        'images_description': [],
        'conclusion': '',
        'details': {}
    }
    
    try:
        # Get Case of Month date
        date_elem = soup.find('h2', string=re.compile(r'Case of Month date', re.I))
        if date_elem:
            case_info['case_of_month_date'] = date_elem.text.replace('Case of Month date :', '').strip()
        
        # Get title
        title_elem = soup.find('h1')
        if title_elem:
            case_info['title'] = title_elem.text.strip()
        
        # Get Clinical Information
        clinical_elem = soup.find('h3', string=re.compile('Clinical information', re.I))
        if clinical_elem and clinical_elem.find_next('p'):
            case_info['clinical_info'] = clinical_elem.find_next('p').text.strip()
        
        # Get Question and Options
        question_elem = soup.find(string=re.compile(r'What would you do\?', re.I))
        if question_elem:
            case_info['question'] = question_elem.strip()
            # Find options (A, B, C, D)
            options = []
            for option in soup.find_all('p', string=re.compile(r'^[A-D]\)')):
                options.append(option.text.strip())
            case_info['options'] = '\n'.join(options)
        
        # Get Images Description
        images_section = soup.find('h3', string=re.compile('Ultrasound Images & Clips', re.I))
        if images_section:
            descriptions = []
            for desc in images_section.find_next_siblings('p'):
                if desc.text.strip():
                    descriptions.append(desc.text.strip())
            case_info['images_description'] = descriptions
        
        # Get Conclusion
        conclusion_elem = soup.find('h3', string=re.compile('Conclusion', re.I))
        if conclusion_elem and conclusion_elem.find_next('p'):
            case_info['conclusion'] = conclusion_elem.find_next('p').text.strip()
        
        # Get Details
        details_elem = soup.find('h3', string=re.compile('Details', re.I))
        if details_elem:
            details_text = details_elem.find_next('p').text.strip()
            for line in details_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    case_info['details'][key.strip()] = value.strip()
    
    except Exception as e:
        print(f"Error extracting info from {url}: {e}")
    
    return case_info

async def process_urls():
    """Process URLs from file and extract information"""
    browser_config = BrowserConfig()
    run_config = CrawlerRunConfig()
    
    # Configure browser
    browser_config.javascript = True
    browser_config.timeout = 30
    run_config.wait_for_timeout = 5000
    
    # Read URLs from file
    with open('digit_ending_urls.txt', 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    # Prepare CSV file
    fieldnames = ['url', 'case_of_month_date', 'title', 'clinical_info', 'question', 
                 'options', 'images_description', 'conclusion', 'details']
    
    with open('case_details.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each URL
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for i, url in enumerate(urls, 1):
                print(f"Processing {i}/{len(urls)}: {url}")
                
                try:
                    result = await crawler.arun(url=url, config=run_config)
                    if result and result.html:
                        case_info = await extract_case_info(result.html, url)
                        # Convert lists and dicts to strings for CSV
                        case_info['images_description'] = '\n'.join(case_info['images_description'])
                        case_info['details'] = '; '.join(f"{k}: {v}" for k, v in case_info['details'].items())
                        writer.writerow(case_info)
                        print(f"✓ Extracted: {case_info['title']}")
                    else:
                        print(f"✗ Failed to fetch: {url}")
                except Exception as e:
                    print(f"✗ Error processing {url}: {e}")
                
                # Add small delay between requests
                await asyncio.sleep(1)

async def main():
    print("Starting case information extraction...")
    await process_urls()
    print("\nDone! Results saved to case_details.csv")

if __name__ == "__main__":
    asyncio.run(main())