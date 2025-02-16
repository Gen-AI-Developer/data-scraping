import asyncio
import aiohttp
import aiofiles
import csv
import os
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

# Create necessary directories
Path("images").mkdir(exist_ok=True)
Path("videos").mkdir(exist_ok=True)

async def download_file(session, url, folder):
    """Download a file (image or video) to the specified folder"""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                # Extract filename from URL
                filename = os.path.basename(urlparse(url).path)
                if not filename:
                    filename = f"file_{hash(url)}"
                
                filepath = os.path.join(folder, filename)
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(await response.read())
                return filepath
    except Exception as e:
        print(f"Error downloading {url}: {str(e)}")
    return None

async def scrape_organ_cases(crawler, base_url):
    """Scrape cases for each organ from the main page"""
    result = await crawler.arun(
        url=base_url,
        config=CrawlerRunConfig(
            wait_until="networkidle"
        )
    )
    
    soup = BeautifulSoup(result.html, 'html.parser')
    
    # Add debug print to see the HTML structure
    print("HTML Content:", soup.prettify()[:500])  # Print first 500 chars for debugging
    
    # Step 2: Locate candidate-container
    candidate_container = soup.find('div', class_='candidate-container')
    if not candidate_container:
        print("Warning: candidate-container not found")
        # Try alternative selectors
        candidate_container = soup.find('div', class_='content-container')
    
    # Step 3: Find organ links
    organ_section = soup.find('div', class_='option-title active')
    if not organ_section:
        print("Warning: option-title active not found")
        # Try alternative selectors
        organ_section = soup.find('div', class_='category-list')
    
    organ_links = []
    if organ_section:
        organ_links = organ_section.find_all('a')
        print(f"Found {len(organ_links)} organ links")
    
    # Step 4 & 5: Extract candidate information
    filter_results = candidate_container.find('div', class_='candidate-filter-result visible') if candidate_container else None
    if not filter_results:
        print("Warning: candidate-filter-result visible not found")
        # Try alternative selectors
        filter_results = candidate_container
    
    candidates = []
    if filter_results:
        # Try multiple possible selectors for candidates
        candidate_elements = filter_results.find_all('div', class_='candidate')
        if not candidate_elements:
            candidate_elements = filter_results.find_all('div', class_='case-item')
        
        print(f"Found {len(candidate_elements)} candidates")
        
        for candidate in candidate_elements:
            title = candidate.find('h3')
            if not title:
                title = candidate.find('h2')
            title = title.text.strip() if title else ""
            
            cases_count_elem = candidate.find('span', class_='cases-count')
            if not cases_count_elem:
                cases_count_elem = candidate.find('span', class_='count')
            cases_count = cases_count_elem.text.strip() if cases_count_elem else "0"
            cases_count = int(''.join(filter(str.isdigit, cases_count)))
            
            # Get the link and convert to absolute URL
            link = candidate.find('a')['href'] if candidate.find('a') else None
            if link:
                # Convert relative URL to absolute URL
                link = urljoin("https://www.ultrasoundcases.info", link)
                print(f"Found candidate link: {link}")
            
            candidates.append({
                'title': title,
                'cases_count': cases_count,
                'link': link
            })
    
    return candidates, organ_links

async def scrape_candidate_page(crawler, session, candidate_url):
    """Scrape individual candidate page"""
    print(f"Scraping candidate page: {candidate_url}")
    
    result = await crawler.arun(
        url=candidate_url,
        config=CrawlerRunConfig(
            wait_until="networkidle"
        )
    )
    
    soup = BeautifulSoup(result.html, 'html.parser')
    
    # Add debug print
    print("Candidate page HTML:", soup.prettify()[:500])
    
    # Step 8: Find thumb elements
    cases = []
    half_grid = soup.find('div', class_='half-grid')
    if not half_grid:
        print("Warning: half-grid not found")
        # Try alternative selectors
        half_grid = soup.find('div', class_='cases-grid')
    
    if half_grid:
        thumb_elements = half_grid.find_all('div', class_='thumb')
        if not thumb_elements:
            thumb_elements = half_grid.find_all('div', class_='case-item')
        
        print(f"Found {len(thumb_elements)} thumb elements")
        
        for thumb in thumb_elements:
            case_data = {
                'title': "",
                'description': "",
                'image_paths': [],
                'video_paths': [],
                'link': None
            }
            
            # Try multiple selectors for title
            title_elem = thumb.find('h3')
            if not title_elem:
                title_elem = thumb.find('h2')
            if title_elem:
                case_data['title'] = title_elem.text.strip()
            
            # Try multiple selectors for description
            desc_elem = thumb.find('p')
            if not desc_elem:
                desc_elem = thumb.find('div', class_='description')
            if desc_elem:
                case_data['description'] = desc_elem.text.strip()
            
            # Get the link and convert to absolute URL
            link = thumb.find('a')['href'] if thumb.find('a') else None
            if link:
                case_data['link'] = urljoin("https://www.ultrasoundcases.info", link)
                print(f"Found case link: {case_data['link']}")
            
            # Download images
            images = thumb.find_all('img')
            for img in images:
                src = img.get('src')
                if src:
                    img_url = urljoin("https://www.ultrasoundcases.info", src)
                    print(f"Found image URL: {img_url}")
                    filepath = await download_file(session, img_url, "images")
                    if filepath:
                        case_data['image_paths'].append(filepath)
                        print(f"Downloaded image to: {filepath}")
            
            cases.append(case_data)
    
    return cases

async def main():
    base_url = "https://www.ultrasoundcases.info/cases/abdomen-and-retroperitoneum/"
    
    # CSV headers
    csv_headers = [
        "organ", "candidate_title", "total_cases",
        "case_title", "description", "image_paths", "video_paths"
    ]
    
    async with AsyncWebCrawler() as crawler:
        async with aiohttp.ClientSession() as session:
            # Step 1-5: Get candidates and organ links
            candidates, organ_links = await scrape_organ_cases(crawler, base_url)
            
            # Create/open CSV file
            with open("ultrasound_cases_detailed.csv", "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
                writer.writeheader()
                
                # Process each candidate
                for candidate in candidates:
                    print(f"Processing candidate: {candidate['title']}")
                    
                    if candidate['link']:
                        # Step 6-9: Scrape candidate page
                        cases = await scrape_candidate_page(crawler, session, candidate['link'])
                        
                        # Step 10: Save to CSV
                        for case in cases:
                            row = {
                                "organ": "Abdomen and Retroperitoneum",
                                "candidate_title": candidate['title'],
                                "total_cases": candidate['cases_count'],
                                "case_title": case['title'],
                                "description": case['description'],
                                "image_paths": "|".join(case['image_paths']),
                                "video_paths": "|".join(case['video_paths'])
                            }
                            writer.writerow(row)
                            csvfile.flush()
                    
                    # Be nice to the server
                    await asyncio.sleep(2)
    
    print("Scraping completed!")

if __name__ == "__main__":
    asyncio.run(main())