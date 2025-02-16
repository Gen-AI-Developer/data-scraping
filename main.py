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
                filename = os.path.basename(urlparse(url).path)
                if not filename:
                    filename = f"file_{hash(url)}"
                
                filepath = os.path.join(folder, filename)
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(await response.read())
                return filepath
            else:
                print(f"Failed to download {url}: Status {response.status}")
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

async def scrape_case_details(soup, session):
    """Extract all details from the company-details div"""
    print("\n=== Starting Case Detail Extraction ===")
    company_details = soup.find('div', class_='company-details')
    if not company_details:
        print("Warning: company-details div not found")
        return None
    
    print("Found company-details div")
    case_data = {
        'title': '',
        'info': '',
        'clinical_info': '',
        'patient_details': {},
        'images': [],
        'image_captions': [],
        'videos': []
    }
    
    # Extract title and info
    title_section = company_details.find('div', class_='title-body')
    if title_section:
        case_data['title'] = title_section.find('h1').text.strip() if title_section.find('h1') else ''
        info_div = title_section.find('div', class_='info')
        case_data['info'] = info_div.text.strip() if info_div else ''
        print(f"Found title: {case_data['title']}")
    else:
        print("Warning: title-body not found")
    
    # Extract clinical information
    clinical_section = company_details.find('div', class_='about-details')
    if clinical_section:
        clinical_info = clinical_section.find('p')
        case_data['clinical_info'] = clinical_info.text.strip() if clinical_info else ''
        print("Found clinical information")
    else:
        print("Warning: about-details not found")
    
    # Extract patient details
    patient_data = company_details.find('div', class_='patient-data')
    if patient_data:
        print("Found patient data section")
        for li in patient_data.find_all('li'):
            key = li.find('span').text.strip().rstrip(':')
            value = li.text.replace(li.find('span').text, '').strip()
            case_data['patient_details'][key] = value
            print(f"Found patient detail: {key}: {value}")
    else:
        print("Warning: patient-data not found")
    
    # Extract images and their captions
    portfolio = company_details.find('div', class_='portfolio')
    if portfolio:
        print("Found portfolio section")
        image_links = portfolio.find_all('a', href=True)
        print(f"Found {len(image_links)} image links")
        
        for img_link in image_links:
            if 'jpg' in img_link['href'].lower() or 'png' in img_link['href'].lower():
                img_url = urljoin("https://www.ultrasoundcases.info", img_link['href'])
                caption_div = img_link.find_next('div', class_='caption')
                caption = caption_div.text.strip() if caption_div else ''
                
                print(f"Processing image: {img_url}")
                # Download image
                filepath = await download_file(session, img_url, "images")
                if filepath:
                    case_data['images'].append(filepath)
                    case_data['image_captions'].append(caption)
                    print(f"Successfully downloaded image to: {filepath}")
                else:
                    print(f"Failed to download image: {img_url}")
    else:
        print("Warning: portfolio section not found")
    
    print(f"=== Completed Case Detail Extraction: {len(case_data['images'])} images downloaded ===\n")
    return case_data

async def get_case_links(soup):
    """Extract all case links from the category page"""
    print("\n=== Starting Case Link Extraction ===")
    case_links = []
    
    # Try different possible containers
    content_container = soup.find('div', class_='candidate-filter-result')
    if not content_container:
        print("Warning: candidate-filter-result not found, trying alternative containers...")
        content_container = soup.find('div', class_='content-container')
    
    if content_container:
        print("Found content container")
        
        # Try to find case items
        case_items = content_container.find_all('div', class_='candidate')
        if not case_items:
            print("Warning: No items with class 'candidate' found, trying alternative classes...")
            case_items = content_container.find_all('div', class_='case-item')
        
        print(f"Found {len(case_items)} case items")
        
        for case in case_items:
            link = case.find('a', href=True)
            if link:
                case_url = urljoin("https://www.ultrasoundcases.info", link['href'])
                case_title = link.text.strip()
                print(f"Found case: {case_title} | URL: {case_url}")
                case_links.append(case_url)
    else:
        print("Warning: No content container found")
    
    print(f"=== Completed Case Link Extraction: {len(case_links)} cases found ===\n")
    return case_links

async def get_category_links(soup):
    """Extract all category links from the main page"""
    print("\n=== Starting Category Link Extraction ===")
    category_links = []
    
    # Look for the dropdown menu
    dropdown = soup.find('div', class_='dropdown-menu')
    if not dropdown:
        print("Warning: Dropdown menu not found")
        return category_links
    
    # Find all category titles (they have class 'dropdown-title')
    categories = dropdown.find_all('a', class_='dropdown-title')
    print(f"Found {len(categories)} main categories")
    
    for category in categories:
        category_url = urljoin("https://www.ultrasoundcases.info", category['href'])
        category_name = category.text.strip()
        category_id = category.get('data-id', '')
        
        # Find all subcategories that follow this category until the next category
        subcategories = []
        current = category.find_next('a')
        while current and 'dropdown-title' not in current.get('class', []):
            if 'dropdown-item' in current.get('class', []):
                subcat_url = urljoin("https://www.ultrasoundcases.info", current['href'])
                subcat_name = current.text.strip()
                subcat_id = current.get('data-id', '')
                
                subcategories.append({
                    'url': subcat_url,
                    'name': subcat_name,
                    'id': subcat_id
                })
            current = current.find_next('a')
        
        category_links.append({
            'url': category_url,
            'name': category_name,
            'id': category_id,
            'subcategories': subcategories
        })
        
        print(f"\nFound category: {category_name} | ID: {category_id}")
        print(f"Category URL: {category_url}")
        print(f"Found {len(subcategories)} subcategories:")
        for subcat in subcategories:
            print(f"  - {subcat['name']} | URL: {subcat['url']}")
    
    print(f"\n=== Completed Category Link Extraction: {len(category_links)} categories found ===\n")
    return category_links

async def get_subcategory_links(soup):
    """Extract all subcategory links from a category page"""
    print("\n=== Starting Subcategory Link Extraction ===")
    subcategory_links = []
    subcategories = soup.find_all('div', class_='subcategory-item')
    if not subcategories:
        print("Warning: No subcategory items found with class 'subcategory-item', trying alternative selectors")
        subcategories = soup.find_all('div', class_='list-item')
    
    print(f"Found {len(subcategories)} subcategory containers")
    
    for subcat in subcategories:
        link = subcat.find('a', href=True)
        if link:
            subcat_url = urljoin("https://www.ultrasoundcases.info", link['href'])
            subcat_name = link.text.strip()
            subcategory_links.append({
                'url': subcat_url,
                'name': subcat_name
            })
            print(f"Found subcategory: {subcat_name} | URL: {subcat_url}")
    
    print(f"=== Completed Subcategory Link Extraction: {len(subcategory_links)} subcategories found ===\n")
    return subcategory_links

async def main():
    print("\n=== Starting Web Scraping Process ===")
    base_url = "https://www.ultrasoundcases.info/cases/"
    print(f"Base URL: {base_url}")
    
    # Create directories
    Path("images").mkdir(exist_ok=True)
    Path("videos").mkdir(exist_ok=True)
    print("Created necessary directories")
    
    # CSV headers
    csv_headers = [
        "category", "subcategory", "title", "info", "clinical_info",
        "patient_sex", "patient_age", "body_part",
        "image_path", "image_caption"
    ]
    
    # Create/open CSV file
    with open("case_details.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
        writer.writeheader()
        
        async with AsyncWebCrawler() as crawler:
            async with aiohttp.ClientSession() as session:
                # Get the main page
                result = await crawler.arun(
                    url=base_url,
                    config=CrawlerRunConfig(
                        wait_until="networkidle"
                    )
                )
                
                soup = BeautifulSoup(result.html, 'html.parser')
                categories = await get_category_links(soup)
                
                # Process each category and its subcategories
                for category in categories:
                    print(f"\nProcessing category: {category['name']}")
                    
                    for subcategory in category['subcategories']:
                        try:
                            print(f"\nProcessing subcategory: {subcategory['name']}")
                            
                            # Get the subcategory page
                            result = await crawler.arun(
                                url=subcategory['url'],
                                config=CrawlerRunConfig(
                                    wait_until="networkidle"
                                )
                            )
                            
                            soup = BeautifulSoup(result.html, 'html.parser')
                            
                            # Debug print to see the HTML structure
                            print("\nSubcategory page HTML structure:")
                            print(soup.prettify()[:1000])  # Print first 1000 chars
                            
                            case_links = await get_case_links(soup)
                            
                            if not case_links:
                                print("No cases found in this subcategory, might need to check HTML structure")
                            
                            # Process each case
                            for case_url in case_links:
                                try:
                                    print(f"\nProcessing case: {case_url}")
                                    
                                    result = await crawler.arun(
                                        url=case_url,
                                        config=CrawlerRunConfig(
                                            wait_until="networkidle"
                                        )
                                    )
                                    
                                    soup = BeautifulSoup(result.html, 'html.parser')
                                    case_data = await scrape_case_details(soup, session)
                                    
                                    if case_data:
                                        # Write a row for each image
                                        for img_path, img_caption in zip(case_data['images'], case_data['image_captions']):
                                            row = {
                                                "category": category['name'],
                                                "subcategory": subcategory['name'],
                                                "title": case_data['title'],
                                                "info": case_data['info'],
                                                "clinical_info": case_data['clinical_info'],
                                                "patient_sex": case_data['patient_details'].get('Sex', ''),
                                                "patient_age": case_data['patient_details'].get('Age', ''),
                                                "body_part": case_data['patient_details'].get('Body part', ''),
                                                "image_path": img_path,
                                                "image_caption": img_caption
                                            }
                                            writer.writerow(row)
                                            csvfile.flush()
                                    
                                    # Be nice to the server
                                    await asyncio.sleep(2)
                                    
                                except Exception as e:
                                    print(f"Error processing case {case_url}: {str(e)}")
                                    continue
                                
                        except Exception as e:
                            print(f"Error processing subcategory {subcategory['name']}: {str(e)}")
                            continue

if __name__ == "__main__":
    asyncio.run(main())