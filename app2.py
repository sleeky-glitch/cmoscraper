import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse
import re
from datetime import datetime
import time
import json
import pandas as pd
from PIL import Image
import io
import zipfile
import tempfile
import shutil
import base64


class NewspaperScraper:
    def __init__(self, date_str, temp_dir):
        self.date_str = date_str
        self.temp_dir = temp_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.base_folder = os.path.join(temp_dir, 'gujarat_samachar_images')
        self.log_file = os.path.join(temp_dir, 'scraping_log.json')
        self.metadata_file = os.path.join(temp_dir, 'article_metadata.json')
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10

        # Create base folder if it doesn't exist
        os.makedirs(self.base_folder, exist_ok=True)

        # Initialize logs and metadata
        self.successful_urls = self.load_log()
        self.metadata = self.load_metadata()

    def load_log(self):
        """Load or create the log file"""
        default_log = {
            'successful_urls': [],
            'stats': {
                'total_downloaded': 0,
                'last_successful_date': None,
                'article_ids_by_page': {},
                'last_successful_ids': {}
            }
        }

        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            return default_log
        except Exception as e:
            st.error(f"Error loading log file: {e}")
            return default_log

    def load_metadata(self):
        """Load or create the metadata file"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            st.error(f"Error loading metadata file: {e}")
            return {}

    def save_log(self):
        """Save the log file"""
        try:
            self.successful_urls['stats']['last_successful_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.log_file, 'w') as f:
                json.dump(self.successful_urls, f, indent=4)
        except Exception as e:
            st.error(f"Error saving log file: {e}")

    def save_metadata(self):
        """Save the metadata file"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=4, ensure_ascii=False)
        except Exception as e:
            st.error(f"Error saving metadata file: {e}")

    def get_article_metadata(self, soup, url, article_id):
        """Extract metadata from article page"""
        metadata = {
            'url': url,
            'article_id': article_id,
            'title': '',
            'date_scraped': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            title_elem = soup.find('div', class_='article_title')
            if title_elem:
                metadata['title'] = title_elem.get_text(strip=True)

            content_elem = soup.find('div', class_='article_text')
            if content_elem:
                metadata['content'] = content_elem.get_text(strip=True)
        except Exception as e:
            st.warning(f"Error extracting metadata: {e}")

        return metadata

    def download_image(self, url, folder_path, page, article_id):
        """Download image from article page"""
        try:
            if url in self.successful_urls['successful_urls']:
                return False, "Already downloaded"

            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code != 200:
                self.consecutive_failures += 1
                return False, f"HTTP {response.status_code}"

            soup = BeautifulSoup(response.text, 'html.parser')
            img_tag = soup.find('img', id='current_artical')

            if not img_tag or 'src' not in img_tag.attrs:
                return False, "No image found"

            img_url = img_tag['src']
            os.makedirs(folder_path, exist_ok=True)

            img_response = requests.get(img_url, headers=self.headers, timeout=10)
            if img_response.status_code == 200:
                ext = os.path.splitext(urlparse(img_url).path)[1]
                if not ext:
                    ext = '.jpeg'

                filename = f'page{page}_article_{article_id}{ext}'
                filepath = os.path.join(folder_path, filename)

                with open(filepath, 'wb') as f:
                    f.write(img_response.content)

                metadata = self.get_article_metadata(soup, url, article_id)
                self.metadata[str(article_id)] = metadata
                self.save_metadata()

                self.consecutive_failures = 0
                self.successful_urls['successful_urls'].append(url)

                if str(page) not in self.successful_urls['stats']['article_ids_by_page']:
                    self.successful_urls['stats']['article_ids_by_page'][str(page)] = []

                if article_id not in self.successful_urls['stats']['article_ids_by_page'][str(page)]:
                    self.successful_urls['stats']['article_ids_by_page'][str(page)].append(article_id)

                self.successful_urls['stats']['last_successful_ids'][str(page)] = article_id
                self.successful_urls['stats']['total_downloaded'] += 1

                self.save_log()
                return True, filepath

            return False, "Failed to download image"

        except Exception as e:
            self.consecutive_failures += 1
            return False, str(e)

    def jump_search_for_page(self, page, start_range=348000, end_range=348999):
        """
        Perform a jump search to find valid articles, starting with large gaps and narrowing down.
        Once an article is found, search nearby IDs.
        """
        status_text = st.empty()
        progress_bar = st.progress(0)
        search_stats = st.empty()

        range_size = end_range - start_range
        found_articles = []

        # Initial jump size will be range_size / 10
        initial_jump = max(range_size // 10, 1)
        jump_size = initial_jump

        status_text.text(f"Starting jump search for page {page} with jump size {jump_size}")

        current_id = start_range
        searched_ids = set()
        found_ids = set()

        while jump_size >= 1:
            search_stats.text(f"""
            Current jump size: {jump_size}
            IDs searched: {len(searched_ids)}
            Articles found: {len(found_articles)}
            Current ID: {current_id}
            """)

            # Try current ID
            if current_id not in searched_ids and start_range <= current_id <= end_range:
                url = f'https://epaper.gujaratsamachar.com/view_article/ahmedabad/{self.date_str}/{page}/{current_id}'
                status_text.text(f"Trying ID: {current_id} (Jump size: {jump_size})")

                success, result = self.download_image(url, os.path.join(self.base_folder, self.date_str), page, current_id)
                searched_ids.add(current_id)

                if success:
                    found_articles.append({
                        'article_id': current_id,
                        'url': url,
                        'filepath': result
                    })
                    found_ids.add(current_id)

                    # Search 10 IDs before and after the found ID
                    search_range = 10
                    for nearby_id in range(current_id - search_range, current_id + search_range + 1):
                        if nearby_id not in searched_ids and start_range <= nearby_id <= end_range:
                            url = f'https://epaper.gujaratsamachar.com/view_article/ahmedabad/{self.date_str}/{page}/{nearby_id}'
                            status_text.text(f"Searching near found article: {nearby_id}")

                            success, result = self.download_image(url, os.path.join(self.base_folder, self.date_str), page, nearby_id)
                            searched_ids.add(nearby_id)

                            if success:
                                found_articles.append({
                                    'article_id': nearby_id,
                                    'url': url,
                                    'filepath': result
                                })
                                found_ids.add(nearby_id)

                    # Reduce jump size after finding an article
                    jump_size = max(jump_size // 2, 1)

                # Update progress
                progress = len(searched_ids) / range_size
                progress_bar.progress(min(progress, 1.0))

            # Move to next position
            current_id += jump_size

            # If we've reached the end of the range
            if current_id > end_range:
                if jump_size == 1:
                    break
                # Reduce jump size and start from beginning
                jump_size = max(jump_size // 2, 1)
                current_id = start_range
                status_text.text(f"Reducing jump size to {jump_size} and starting over")

            time.sleep(0.5)  # Prevent too rapid requests

        # Sort found articles by ID
        found_articles.sort(key=lambda x: x['article_id'])

        # Display final statistics for this page
        if found_articles:
            st.write(f"""
            ### Page {page} Summary
            - Total articles found: {len(found_articles)}
            - ID range: {min(found_ids)} to {max(found_ids)}
            - Total IDs searched: {len(searched_ids)}
            """)
        else:
            st.write(f"""
            ### Page {page} Summary
            - No articles found
            - IDs searched: {len(searched_ids)}
            """)

        return found_articles

    def create_zip_file(self):
        """Create a zip file of all downloaded content"""
        zip_path = os.path.join(self.temp_dir, f'gujarat_samachar_{self.date_str}.zip')

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add images
                for root, dirs, files in os.walk(self.base_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.temp_dir)
                        zipf.write(file_path, arcname)

                # Add metadata and log files
                if os.path.exists(self.metadata_file):
                    zipf.write(self.metadata_file, os.path.basename(self.metadata_file))
                if os.path.exists(self.log_file):
                    zipf.write(self.log_file, os.path.basename(self.log_file))

            return zip_path
        except Exception as e:
            st.error(f"Error creating zip file: {e}")
            return None


def extract_article_id(url):
    """Extract article ID from the URL"""
    match = re.search(r'/(\d+)$', url)
    if match:
        return int(match.group(1))
    return None


def create_download_link(zip_path):
    """Create a download link for the zip file"""
    try:
        with open(zip_path, 'rb') as f:
            bytes = f.read()
            b64 = base64.b64encode(bytes).decode()
            filename = os.path.basename(zip_path)
            href = f'<a href="data:application/zip;base64,{b64}" download="{filename}">Download ZIP File</a>'
            return href
    except Exception as e:
        st.error(f"Error creating download link: {e}")
        return None


def main():
    st.set_page_config(page_title="Gujarat Samachar Scraper", layout="wide")

    st.title("Gujarat Samachar E-Paper Scraper")

    # Create a temporary directory for this session
    with tempfile.TemporaryDirectory() as temp_dir:
        with st.sidebar:
            st.header("Settings")
            date_str = st.date_input(
                "Select Date",
                datetime.now()
            ).strftime('%d-%m-%Y')

            num_pages = st.number_input("Number of Pages to Scrape", min_value=1, max_value=20, value=4)

            # Add range settings with defaults
            start_range = st.number_input("Start Range", min_value=300000, max_value=399999, value=348000)
            end_range = st.number_input("End Range", min_value=300000, max_value=399999, value=348999)

        # Main content area
        st.header("Scraping Configuration")

        if st.button("Start Scraping"):
            scraper = NewspaperScraper(date_str, temp_dir)

            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["Progress", "Results", "Download"])

            with tab1:
                progress_container = st.container()

            with tab2:
                results_container = st.container()

            with tab3:
                download_container = st.container()

            all_downloads = []

            with progress_container:
                st.write("### Scraping Progress")

                overall_progress = st.progress(0)
                overall_status = st.empty()
                total_downloads = 0
                total_articles_found = 0

                for page_idx, page in enumerate(range(1, num_pages + 1)):
                    st.write(f"#### Processing Page {page}")
                    overall_status.text(f"Processing page {page} of {num_pages}")

                    downloads = scraper.jump_search_for_page(page, start_range, end_range)
                    all_downloads.extend(downloads)
                    total_articles_found += len(downloads)

                    overall_progress.progress((page_idx + 1) / num_pages)

                    # Update overall statistics
                    st.sidebar.metric("Total Articles Found", total_articles_found)
                    st.sidebar.metric("Pages Completed", page_idx + 1)

                overall_status.text("Scraping completed!")

            with results_container:
                st.write("### Scraping Results")

                # Display statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Downloads", len(all_downloads))
                with col2:
                    st.metric("Pages Processed", num_pages)
                with col3:
                    st.metric("Success Rate", f"{(len(all_downloads)/(num_pages*100))*100:.1f}%")

                # Display metadata
                if scraper.metadata:
                    st.write("#### Article Metadata")
                    metadata_df = pd.DataFrame(scraper.metadata).T
                    st.dataframe(metadata_df)

            with download_container:
                st.write("### Download Files")

                if all_downloads:
                    # Create zip file
                    zip_path = scraper.create_zip_file()
                    if zip_path:
                        # Create download link
                        href = create_download_link(zip_path)
                        if href:
                            st.markdown(href, unsafe_allow_html=True)

                            st.write("""
                            The ZIP file contains:
                            - All downloaded images
                            - Metadata file (article_metadata.json)
                            - Scraping log (scraping_log.json)
                            """)
                else:
                    st.warning("No files to download. Please run the scraper first.")


if __name__ == "__main__":
    main()

