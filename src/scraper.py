import csv
from datetime import datetime
import logging
from typing import List, Dict, Any
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import os
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_driver() -> webdriver.Firefox:
    """
    Sets up and returns a Firefox WebDriver instance.
    
    Returns:
        webdriver.Firefox: Configured Firefox WebDriver instance
    """
    firefox_options = Options()
    firefox_options.add_argument("--headless")
    
    driver = webdriver.Firefox(options=firefox_options)
    driver.set_window_size(1920, 1080)
    return driver

def get_page_episodes(driver: webdriver.Firefox, url: str) -> List[Dict[str, Any]]:
    """
    Scrapes episodes from a single page using Selenium.
    
    Args:
        driver (webdriver.Firefox): Firefox WebDriver instance
        url (str): URL to scrape
        
    Returns:
        List[Dict[str, Any]]: List of episode dictionaries
    """
    try:
        logger.info(f"Fetching content from {url}")
        driver.get(url)
        
        # Wait for the tiles to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tile"))
        )
        
        # Parse the page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        episode_tiles = soup.find_all('div', class_='tile')
        
        logger.info(f"Found {len(episode_tiles)} episode tiles")
        
        episodes = []
        for tile in episode_tiles:
            try:
                # Extract episode number
                number_elem = tile.find('span', class_='number')
                episode_number = number_elem.text.strip() if number_elem else "Unknown"
                
                # Extract title and URL
                title_elem = tile.find('h2', class_='tile-title').find('a')
                title = title_elem.text.strip()
                url = title_elem['href']
                if not url.startswith('http'):
                    url = f"https://www.desiringgod.org{url}"
                
                # Extract date
                date_elem = tile.find('time', class_='time')
                date = date_elem['datetime'] if date_elem else "Unknown"
                
                # Extract topic/category
                topic_elem = tile.find('a', attrs={'data-grouping-type': 'Topic'})
                topic = topic_elem.text.strip() if topic_elem else "Unknown"
                
                # Extract description
                description_elem = tile.find('div', class_='tile-description')
                description = description_elem.text.strip() if description_elem else "No description available"
                
                episodes.append({
                    'episode_number': episode_number,
                    'title': title,
                    'url': url,
                    'date': date,
                    'topic': topic,
                    'description': description
                })
                
            except (AttributeError, KeyError) as e:
                logger.error(f"Error parsing episode tile: {e}")
                continue
        
        return episodes
    
    except TimeoutException:
        logger.error("Timeout waiting for page to load")
        return []
    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        return []

def get_therapy_theology_episodes_page(driver: webdriver.Firefox, url: str) -> List[Dict[str, Any]]:
    """
    Scrapes Therapy and Theology episodes from a single page using Selenium.
    
    Args:
        driver (webdriver.Firefox): Firefox WebDriver instance
        url (str): URL to scrape
        
    Returns:
        List[Dict[str, Any]]: List of episode dictionaries
    """
    try:
        logger.info(f"Fetching Therapy and Theology content from {url}")
        driver.get(url)
        
        # Wait for content to load - try multiple possible selectors
        wait_selectors = [
            "h2", "h3", ".episode", ".episode-item", 
            "[data-episode]", "article", "div[class*='episode']"
        ]
        
        for selector in wait_selectors:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                break
            except TimeoutException:
                continue
        
        # Add a small delay to let content fully render
        time.sleep(3)
        
        # Parse the page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look for episode containers using multiple strategies
        episode_items = []
        
        # Strategy 1: Look for h2/h3 headers with season/episode patterns
        headers = soup.find_all(['h2', 'h3'])
        for header in headers:
            text = header.get_text(strip=True)
            if re.search(r'S\d+\s+E\d+', text):
                # Find the parent container that likely contains the full episode info
                parent = header.parent
                while parent and parent.name != 'body':
                    if parent.name in ['div', 'article', 'section']:
                        episode_items.append(parent)
                        break
                    parent = parent.parent
        
        # Strategy 2: If no episodes found, look for any text containing season/episode patterns
        if not episode_items:
            all_text_elements = soup.find_all(string=re.compile(r'S\d+\s+E\d+'))
            for text_elem in all_text_elements:
                parent = text_elem.parent
                while parent and parent.name != 'body':
                    if parent.name in ['div', 'article', 'section']:
                        episode_items.append(parent)
                        break
                    parent = parent.parent
        
        # Remove duplicates
        episode_items = list(set(episode_items))
        
        logger.info(f"Found {len(episode_items)} Therapy and Theology episode items")
        
        episodes = []
        for item in episode_items:
            try:
                # Extract episode title/number (format like "S8 E6 | Title")
                text_content = item.get_text()
                
                # Look for season/episode pattern
                season_episode_match = re.search(r'S(\d+)\s+E(\d+)', text_content)
                if season_episode_match:
                    season = season_episode_match.group(1)
                    episode = season_episode_match.group(2)
                    episode_number = f"S{season}E{episode}"
                    
                    # Extract the title part after the season/episode
                    title_match = re.search(r'S\d+\s+E\d+\s*\|\s*([^\n\r]+)', text_content)
                    if title_match:
                        title = title_match.group(1).strip()
                    else:
                        # Try to find title in nearby elements
                        title_elem = item.find(['h2', 'h3'])
                        if title_elem:
                            full_title = title_elem.get_text(strip=True)
                            title_match = re.search(r'S\d+\s+E\d+\s*\|\s*(.+)', full_title)
                            title = title_match.group(1) if title_match else "Unknown Title"
                        else:
                            title = "Unknown Title"
                else:
                    episode_number = "Unknown"
                    title = "Unknown Title"
                
                # Extract URL (look for links within the item)
                url_elem = item.find('a', href=True)
                episode_url = url_elem['href'] if url_elem else "Unknown"
                if episode_url and episode_url != "Unknown" and not episode_url.startswith('http'):
                    episode_url = f"https://therapyandtheology.transistor.fm{episode_url}"
                
                # Extract date - look for date patterns in text
                date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', text_content)
                if date_match:
                    date = date_match.group(0)
                else:
                    # Look for other date formats
                    date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text_content) or re.search(r'\d{4}-\d{2}-\d{2}', text_content)
                    date = date_match.group(0) if date_match else "Unknown"
                
                # Extract description - look for paragraph or description text
                description_parts = []
                paragraphs = item.find_all('p')
                for p in paragraphs:
                    p_text = p.get_text(strip=True)
                    if len(p_text) > 20 and not re.search(r'S\d+\s+E\d+', p_text):
                        description_parts.append(p_text)
                
                description = ' '.join(description_parts[:2]) if description_parts else "No description available"
                
                # Set topic as "Therapy & Theology" for all episodes
                topic = "Therapy & Theology"
                
                # Only add if we have meaningful data
                if episode_number != "Unknown" or title != "Unknown Title":
                    episodes.append({
                        'episode_number': episode_number,
                        'title': title,
                        'url': episode_url,
                        'date': date,
                        'topic': topic,
                        'description': description
                    })
                
            except Exception as e:
                logger.error(f"Error parsing Therapy and Theology episode item: {e}")
                continue
        
        return episodes
    
    except Exception as e:
        logger.error(f"Error fetching Therapy and Theology content: {e}")
        return []

def get_therapy_theology_episodes(max_pages: int = 5) -> List[Dict[str, Any]]:
    """
    Scrapes Therapy and Theology episodes from the Transistor.fm website, handling pagination.
    
    Args:
        max_pages (int): Maximum number of pages to scrape
    
    Returns:
        List[Dict[str, Any]]: List of episode dictionaries containing episode details
    """
    base_url = "https://therapyandtheology.transistor.fm/episodes"
    all_episodes = []
    
    driver = setup_driver()
    try:
        # Start with the main episodes page
        logger.info("Fetching Therapy and Theology episodes from main page")
        page_episodes = get_therapy_theology_episodes_page(driver, base_url)
        if page_episodes:
            all_episodes.extend(page_episodes)
            logger.info(f"Total Therapy and Theology episodes collected so far: {len(all_episodes)}")
        
        # Try pagination if available
        current_page = 2
        pages_scraped = 1
        
        while pages_scraped < max_pages:
            # Try different pagination URL formats
            pagination_urls = [
                f"{base_url}?page={current_page}",
                f"{base_url}/{current_page}",
                f"{base_url}?p={current_page}"
            ]
            
            episode_found = False
            for url in pagination_urls:
                try:
                    page_episodes = get_therapy_theology_episodes_page(driver, url)
                    if page_episodes:
                        all_episodes.extend(page_episodes)
                        logger.info(f"Total Therapy and Theology episodes collected so far: {len(all_episodes)}")
                        episode_found = True
                        break
                except Exception as e:
                    logger.warning(f"Failed to fetch from {url}: {e}")
                    continue
            
            if not episode_found:
                logger.info(f"No more Therapy and Theology episodes found. Stopping pagination.")
                break
            
            # Add a small delay between pages
            time.sleep(2)
            current_page += 1
            pages_scraped += 1
    
    finally:
        driver.quit()
    
    return all_episodes

def get_apj_episodes(max_pages: int = 15) -> List[Dict[str, Any]]:
    """
    Scrapes Ask Pastor John episodes from the Desiring God website, handling pagination.
    First visits the base URL for latest episodes, then jumps to page 215 and continues until the end.
    
    Args:
        max_pages (int): Maximum number of pages to scrape after page 215
    
    Returns:
        List[Dict[str, Any]]: List of episode dictionaries containing episode details
    """
    base_url = "https://www.desiringgod.org/ask-pastor-john"
    all_episodes = []
    
    driver = setup_driver()
    try:
        # First get the latest episodes from the base URL
        logger.info("Fetching latest episodes from base URL")
        page_episodes = get_page_episodes(driver, base_url)
        if page_episodes:
            all_episodes.extend(page_episodes)
            logger.info(f"Total episodes collected so far: {len(all_episodes)}")
        
        # Now start from page 215 and continue
        current_page = 215
        pages_scraped = 0
        
        while pages_scraped < max_pages:
            url = f"{base_url}/recent.html?page={current_page}"
            
            # Get episodes from the current page
            page_episodes = get_page_episodes(driver, url)
            
            if not page_episodes:
                logger.info(f"No more episodes found on page {current_page}. Stopping pagination.")
                break
                
            all_episodes.extend(page_episodes)
            logger.info(f"Total episodes collected so far: {len(all_episodes)}")
            
            # Check if there's a "Load More Episodes" button
            try:
                load_more = driver.find_element(By.CLASS_NAME, "load-more")
                if not load_more.is_displayed():
                    logger.info("No more episodes to load")
                    break
            except NoSuchElementException:
                logger.info("No 'Load More' button found")
                break
            
            # Add a small delay between pages
            time.sleep(2)
            current_page += 1
            pages_scraped += 1
    
    finally:
        driver.quit()
    
    return all_episodes

def read_existing_episodes(filename: str) -> Dict[str, Dict[str, Any]]:
    """
    Reads existing episodes from the CSV file.
    
    Args:
        filename (str): Name of the CSV file
        
    Returns:
        Dict[str, Dict[str, Any]]: Dictionary of episodes keyed by episode number
    """
    existing_episodes = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_episodes[row['episode_number']] = row
            logger.info(f"Found {len(existing_episodes)} existing episodes in {filename}")
        except IOError as e:
            logger.error(f"Error reading existing episodes: {e}")
    return existing_episodes

def save_to_csv(episodes: List[Dict[str, Any]], filename: str = 'ask_pastor_john.csv') -> None:
    """
    Saves the episode data to a CSV file, preserving existing episodes and avoiding duplicates.
    
    Args:
        episodes (List[Dict[str, Any]]): List of episode dictionaries
        filename (str): Name of the output CSV file
    """
    try:
        # Read existing episodes
        existing_episodes = read_existing_episodes(filename)
        
        # Add new episodes to existing ones, avoiding duplicates
        updated_episodes = existing_episodes.copy()
        new_episodes_count = 0
        for episode in episodes:
            if episode['episode_number'] not in existing_episodes:
                updated_episodes[episode['episode_number']] = episode
                new_episodes_count += 1
        
        # Sort episodes by episode number (descending)
        def sort_key(episode):
            episode_num = episode['episode_number']
            if episode_num == 'Unknown':
                return (0, 0, 0)  # Put Unknown episodes at the end
            
            # Handle season/episode format (e.g., "S8E6")
            season_episode_match = re.search(r'S(\d+)E(\d+)', episode_num)
            if season_episode_match:
                season = int(season_episode_match.group(1))
                episode = int(season_episode_match.group(2))
                return (1, season, episode)  # Group 1 for season/episode format
            
            # Handle numeric format (e.g., "2154")
            try:
                return (2, int(episode_num), 0)  # Group 2 for numeric format
            except ValueError:
                return (0, 0, 0)  # Fallback for any other format
        
        sorted_episodes = sorted(
            updated_episodes.values(),
            key=sort_key,
            reverse=True
        )
        
        # Write all episodes back to the file
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['episode_number', 'title', 'url', 'date', 'topic', 'description']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for episode in sorted_episodes:
                writer.writerow(episode)
        
        logger.info(f"Added {new_episodes_count} new episodes to {filename}")
        logger.info(f"Total episodes in file: {len(sorted_episodes)}")
    
    except IOError as e:
        logger.error(f"Error saving to CSV: {e}")

def scrape_all_sources():
    """
    Scrapes both Ask Pastor John and Therapy & Theology episodes.
    """
    logger.info("Starting to scrape all sources...")
    
    # Scrape Ask Pastor John episodes
    logger.info("Scraping Ask Pastor John episodes...")
    apj_episodes = get_apj_episodes(max_pages=15)
    if apj_episodes:
        save_to_csv(apj_episodes, 'ask_pastor_john.csv')
        logger.info(f"Successfully scraped {len(apj_episodes)} Ask Pastor John episodes")
    else:
        logger.error("No Ask Pastor John episodes were retrieved. Check the logs for errors.")
    
    # Scrape Therapy & Theology episodes
    logger.info("Scraping Therapy & Theology episodes...")
    tt_episodes = get_therapy_theology_episodes(max_pages=5)
    if tt_episodes:
        save_to_csv(tt_episodes, 'therapy_and_theology.csv')
        logger.info(f"Successfully scraped {len(tt_episodes)} Therapy & Theology episodes")
    else:
        logger.error("No Therapy & Theology episodes were retrieved. Check the logs for errors.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        source = sys.argv[1].lower()
        if source == "apj" or source == "ask-pastor-john":
            # Scrape only Ask Pastor John
            episodes = get_apj_episodes(max_pages=15)
            if episodes:
                save_to_csv(episodes, 'ask_pastor_john.csv')
            else:
                logger.error("No Ask Pastor John episodes were retrieved.")
        elif source == "tt" or source == "therapy-theology":
            # Scrape only Therapy & Theology  
            episodes = get_therapy_theology_episodes(max_pages=5)
            if episodes:
                save_to_csv(episodes, 'therapy_and_theology.csv')
            else:
                logger.error("No Therapy & Theology episodes were retrieved.")
        elif source == "all":
            # Scrape both sources
            scrape_all_sources()
        else:
            print("Usage: python scraper.py [apj|tt|all]")
            print("  apj: Scrape Ask Pastor John only")
            print("  tt: Scrape Therapy & Theology only") 
            print("  all: Scrape both sources")
    else:
        # Default: scrape both sources
        scrape_all_sources() 