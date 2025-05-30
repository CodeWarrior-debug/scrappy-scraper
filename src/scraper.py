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
        sorted_episodes = sorted(
            updated_episodes.values(),
            key=lambda x: int(x['episode_number'].replace('Unknown', '0')),
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

if __name__ == "__main__":
    episodes = get_apj_episodes(max_pages=216)  # Scrape up to 5 pages by default
    if episodes:
        save_to_csv(episodes)
    else:
        logger.error("No episodes were retrieved. Check the logs for errors.") 