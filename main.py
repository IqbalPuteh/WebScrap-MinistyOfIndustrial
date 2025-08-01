# Kemenperin web scraping using Playwright with BeautifulSoup and pandas

import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
import logging
import json
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable to store all scraped data
all_data = []
base_url = "https://kemenperin.go.id/direktori-perusahaan"
# DKI
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=JWlMr9dBZoh4NcRGhLV2lw1ZzJLjyJbE3zQxksmdgRg%2C"
# Jabar
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=g-g92cJf63GcZzFru_hX80HG3NA95zwE5tWTVGAI5xY%2C"
# Jateng
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=JQYaw_F3IWxjLT5vFsXUh6CwfCBsw3zUdgJGGaNtqc0%2C"
# Jatim
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=HJCA4sCEb2EHadmM-d2MTdZLHIqCSlODwIEaR0IZuz0%2C"
# Bali
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=0bCtGgIPKU5sHVP-I3RJR_zaGkICRuxrBuLF8pn6okw%2C"
# DIY
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=YaPZnRqzpP2obO5M2vJBT-05qeMzPo7KQSLLhi4zW28%2C"
# Banten
base_url = "https://kemenperin.go.id/direktori-perusahaan?what=&prov=szh3Nx9NmSTOTpqeCuh7rOYNcZov8Oricx3WNJaMJkg%2C"


async def get_pagination_info(page):
    try:
        # Get the page HTML content
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        pagination = soup.find('ul', {'class': 'pagination'})
        if not pagination:
            return None
        
        pages = []
        current_page = 1
        max_visible_page = 1
        has_more_pages = False
        
        # Find all pagination links
        for li in pagination.find_all('li'):
            links = li.find_all('a')
            for link in links:
                if link:
                    text = link.get_text(strip=True)
                    href = link.get('href', '')
                    is_active = 'active' in li.get('class', [])
                    
                    # Extract page number from text that might contain dots
                    import re
                    match = re.match(r'^(\d+)', text)
                    if match:
                        page_number = int(match.group(1))
                        if is_active:
                            current_page = page_number
                        
                        # Track the highest visible page number
                        max_visible_page = max(max_visible_page, page_number)
                        
                        # Check if this link has dots (indicating more pages)
                        if '..' in text:
                            has_more_pages = True
                        
                        pages.append({
                            'text': text,
                            'href': href,
                            'is_active': is_active,
                            'page_number': page_number,
                            'has_dots': '..' in text
                        })
                    else:
                        # Text is not a number (e.g., "Next", "Previous")
                        pages.append({
                            'text': text,
                            'href': href,
                            'is_active': is_active,
                            'page_number': None,
                            'has_dots': False
                        })
        
        # Remove duplicates
        unique_pages = []
        seen_page_numbers = set()
        for p in pages:
            if p['page_number'] is not None:
                if p['page_number'] not in seen_page_numbers:
                    unique_pages.append(p)
                    seen_page_numbers.add(p['page_number'])
            else:
                unique_pages.append(p)
        
        page_numbers = [p['page_number'] for p in unique_pages if p['page_number'] is not None]
        
        logger.info(f"Found page numbers: {sorted(page_numbers) if page_numbers else 'None'}")
        logger.info(f"Current page: {current_page}, Max visible: {max_visible_page}, Has more: {has_more_pages}")
        
        return {
            'current_page': current_page,
            'pages': unique_pages,
            'max_visible_page': max_visible_page,
            'has_more_pages': has_more_pages,
            'page_numbers': sorted(page_numbers) if page_numbers else []
        }
        
    except Exception as e:
        logger.error(f"Error getting pagination info: {e}")
        return None

async def find_next_page_to_scrape(page):
    try:
        pagination_info = await get_pagination_info(page)
        if not pagination_info:
            return None
        
        current_page = pagination_info['current_page']
        available_pages = pagination_info['page_numbers']
        has_more_pages = pagination_info['has_more_pages']
        
        # Find the next sequential page
        next_page = current_page + 1
        
        # If the next page is visible in current pagination, navigate to it
        if next_page in available_pages:
            return next_page
        
        # If the next page is not visible but there are more pages (indicated by dots)
        if has_more_pages:
            # Look for a page with dots that might lead us forward
            for page_info in pagination_info['pages']:
                if page_info.get('has_dots', False) and page_info['page_number'] > current_page:
                    return page_info['page_number']
        
        # No more pages found
        return None
        
    except Exception as e:
        logger.error(f"Error finding next page: {e}")
        return None

async def navigate_to_page(page, page_number):
    try:
        # Get current HTML to find the pagination link
        html_content = await page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the pagination link for the specific page
        pagination = soup.find('ul', {'class': 'pagination'})
        if pagination:
            for li in pagination.find_all('li'):
                links = li.find_all('a')
                for link in links:
                    if link:
                        link_text = link.get_text(strip=True)
                        # Check if the link text starts with the page number
                        import re
                        match = re.match(r'^(\d+)', link_text)
                        if match and int(match.group(1)) == page_number:
                            # Use the href to navigate directly
                            href = link.get('href')
                            if href:
                                # Convert relative URL to absolute if needed
                                if href.startswith('/'):
                                    full_url = f"https://kemenperin.go.id{href}"
                                elif href.startswith('direktori-perusahaan'):
                                    full_url = f"https://kemenperin.go.id/{href}"
                                else:
                                    full_url = href
                                
                                logger.info(f"Navigating to page {page_number} via URL: {full_url}")
                                await page.goto(full_url)
                                await page.wait_for_load_state('networkidle')
                                await page.wait_for_selector('#newspaper-a', timeout=40000)
                                return True
        
        logger.warning(f"Page {page_number} link not found in current pagination")
        return False
            
    except Exception as e:
        logger.error(f"Error navigating to page {page_number}: {e}")
        return False

async def scrape_all_pages():

    global all_data
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Set to True for production
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Navigate to the base URL
            logger.info(f"Navigating to {base_url}")
            await page.goto(base_url)
            await page.wait_for_load_state('networkidle')
            
            # Wait for table to load
            await page.wait_for_selector('#newspaper-a', timeout=40000)
            
            scraped_pages = set()  # Keep track of pages we've already scraped
            
            while True:
                # Get current pagination info
                pagination_info = await get_pagination_info(page)
                if not pagination_info:
                    logger.warning("No pagination info found")
                    break
                
                current_page = pagination_info['current_page']
                
                # Skip if we've already scraped this page
                if current_page in scraped_pages:
                    logger.warning(f"Page {current_page} already scraped, stopping to avoid infinite loop")
                    break
                
                logger.info(f"Scraping page {current_page}")
                
                # Scrape current page data
                page_data = await scrape_table_data(page)
                if page_data:
                    all_data.extend(page_data)
                    scraped_pages.add(current_page)
                    logger.info(f"Total rows collected so far: {len(all_data)}")
                else:
                    logger.warning(f"No data found on page {current_page}")
                
                # Find next page to scrape
                next_page = await find_next_page_to_scrape(page)
                
                if next_page and next_page not in scraped_pages:
                    logger.info(f"Attempting to navigate to page {next_page}")
                    if await navigate_to_page(page, next_page):
                        await asyncio.sleep(2)  # Be respectful to the server
                    else:
                        logger.warning(f"Failed to navigate to page {next_page}")
                        break
                else:
                    logger.info("No more new pages to scrape")
                    break
                
                # Safety break to prevent infinite loops
                if len(scraped_pages) > 200000:  # Adjust this limit as needed
                    logger.warning("Reached maximum page limit (10000), stopping")
                    break
            
            logger.info(f"Scraping completed! Scraped pages: {sorted(scraped_pages)}")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        
        finally:
            await browser.close()

async def scrape_table_data(page):
    try:
        # Get the page HTML content
        html_content = await page.content()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the table with id 'newspaper-a'
        table = soup.find('table', {'id': 'newspaper-a'})
        if not table:
            logger.warning("Table not found on page")
            return []
        
        # Extract all rows
        rows = []
        table_rows = table.find_all('tr')
        
        for row in table_rows:
            # Check if this is a row with bgcolor="white" and valign="top"
            is_white_row = (row.get('bgcolor') == 'white' and row.get('valign') == 'top')
            
            cells = row.find_all(['td', 'th'])
            if cells:
                if is_white_row:
                    # For white rows, parse BR-separated content and reconstruct proper columns
                    all_segments = []
                    
                    # Extract all segments from all cells
                    for cell in cells:
                        # Create a copy of the cell to avoid modifying the original
                        cell_copy = BeautifulSoup(str(cell), 'html.parser').find(['td', 'th'])
                        
                        # Replace <br> tags with a special delimiter
                        for br in cell_copy.find_all('br'):
                            br.replace_with('|||BR_SEPARATOR|||')
                        
                        # Get the text and split by our delimiter
                        cell_text = cell_copy.get_text()
                        segments = cell_text.split('|||BR_SEPARATOR|||')
                        
                        # Clean and collect all non-empty segments
                        for segment in segments:
                            cleaned_segment = segment.strip()
                            if cleaned_segment:
                                all_segments.append(cleaned_segment)
                    
                    # Now reconstruct the row based on patterns in the data
                    if len(all_segments) >= 3:
                        reconstructed_row = []
                        
                        # First segment should be the number (ID)
                        reconstructed_row.append(all_segments[0])
                        
                        # Second segment should be company name
                        reconstructed_row.append(all_segments[1])
                        
                        # Third segment should be KBLI code
                        reconstructed_row.append(all_segments[2])
                        
                        # Fourth segment (if exists) should be address
                        if len(all_segments) > 3:
                            reconstructed_row.append(all_segments[3])
                        else:
                            reconstructed_row.append('')
                        
                        # Look for phone number (usually starts with "Telp." or contains phone patterns)
                        phone = ''
                        for segment in all_segments[4:]:
                            if 'telp' in segment.lower() or 'phone' in segment.lower() or segment.startswith('0') or segment.startswith('+'):
                                phone = segment
                                break
                        reconstructed_row.append(phone)
                        
                        # Add any remaining segments as additional columns
                        remaining_segments = [seg for seg in all_segments[4:] if seg != phone]
                        for seg in remaining_segments:
                            reconstructed_row.append(seg)
                        
                        rows.append(reconstructed_row)
                    else:
                        # If we don't have enough segments, fall back to original method
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        rows.append(row_data)
                        
                else:
                    # For non-white rows, use the original method
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    rows.append(row_data)
        
        logger.info(f"Extracted {len(rows)} rows from current page")
        return rows
        
    except Exception as e:
        logger.error(f"Error extracting table data: {e}")
        return []

def create_dataframe(data):
    if not data:
        return pd.DataFrame()
    
    # Remove duplicate rows
    unique_data = []
    seen_rows = set()
    
    for row in data:
        row_tuple = tuple(str(cell).strip() for cell in row)
        if row_tuple not in seen_rows:
            seen_rows.add(row_tuple)
            unique_data.append(row)
    
    logger.info(f"Removed {len(data) - len(unique_data)} duplicate rows")
    
    # Tentukan jumlah kolom maksimum
    max_cols = max(len(row) for row in unique_data)
    
    # Pad semua baris agar punya jumlah kolom yang sama
    padded_data = [row + [''] * (max_cols - len(row)) for row in unique_data]

    # Buat header default jika tidak tersedia
    column_names = [f"Column_{i+1}" for i in range(max_cols)]
    
    df = pd.DataFrame(padded_data, columns=column_names)

    # Bersihkan DataFrame
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    df = df.dropna(how='all').drop_duplicates().reset_index(drop=True)
    
    return df


def save_to_csv(filename=None):
    global all_data
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kemenperin_companies_{timestamp}.csv"
    
    if not all_data:
        logger.warning("No data to save")
        return
    
    try:
        df = create_dataframe(all_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"Data saved to {filename} ({len(df)} rows)")
        
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")

def save_to_json(filename=None):
    global all_data
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kemenperin_companies_{timestamp}.json"
    
    if not all_data:
        logger.warning("No data to save")
        return
    
    try:
        df = create_dataframe(all_data)
        df.to_json(filename, orient='records', force_ascii=False, indent=2)
        logger.info(f"Data saved to {filename} ({len(df)} records)")
        
    except Exception as e:
        logger.error(f"Error saving to JSON: {e}")

def save_to_excel(filename=None):
    """Save scraped data to Excel file using pandas with formatting"""
    global all_data
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kemenperin_companies_{timestamp}.xlsx"
    
    if not all_data:
        logger.warning("No data to save")
        return
    
    try:
        df = create_dataframe(all_data)
        
        # Save to Excel with formatting
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Companies', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Companies']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(str(col))
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)
        
        logger.info(f"Data saved to {filename} ({len(df)} rows)")
        
    except Exception as e:
        logger.error(f"Error saving to Excel: {e}")

def analyze_data():
    global all_data
    
    if not all_data or len(all_data) < 2:
        logger.warning("Not enough data to analyze")
        return
    
    try:
        df = create_dataframe(all_data)
        
        logger.info("\n=== Data Analysis ===")
        logger.info(f"Total records: {len(df)}")
        logger.info(f"Columns: {', '.join(df.columns)}")
        
        # Show data types
        logger.info("\nData types:")
        for col in df.columns:
            logger.info(f"  {col}: {df[col].dtype}")
        
        # Show first few rows
        logger.info("\nFirst 5 rows:")
        logger.info(df.head().to_string())
        
        # Basic statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        if len(numeric_cols) > 0:
            logger.info("\nNumeric column statistics:")
            logger.info(df[numeric_cols].describe().to_string())
        
        # Check for missing values
        missing_values = df.isnull().sum()
        if missing_values.any():
            logger.info("\nMissing values per column:")
            logger.info(missing_values[missing_values > 0].to_string())
        
    except Exception as e:
        logger.error(f"Error analyzing data: {e}")

async def main():
    global all_data
    
    logger.info("Starting Kemenperin company directory scraping...")
    #logger.info("Using Playwright for browser automation + BeautifulSoup for parsing + pandas for data manipulation")
    
    await scrape_all_pages()
    
    if all_data:
        logger.info(f"Scraping completed! Total rows: {len(all_data)}")
        
        # Analyze the data
        analyze_data()
        
        # Save data in multiple formats
        save_to_csv()
        save_to_json()
        save_to_excel()
    else:
        logger.warning("No data was scraped")

if __name__ == "__main__":
    asyncio.run(main())