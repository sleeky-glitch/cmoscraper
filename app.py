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
        self.successful_urls = self.load_log()
        self.metadata = self.load_metadata()
        self.consecutive_failures = 0
        self.max_consecutive_failures = 10

        # Create base folder if it doesn't exist
        os.makedirs(self.base_folder, exist_ok=True)

    # [Previous methods remain largely the same, just updated to use temp_dir]

    def create_zip_file(self):
        """Create a zip file of all downloaded content"""
        zip_path = os.path.join(self.temp_dir, f'gujarat_samachar_{self.date_str}.zip')

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

def create_download_link(zip_path):
    """Create a download link for the zip file"""
    with open(zip_path, 'rb') as f:
        bytes = f.read()
        b64 = base64.b64encode(bytes).decode()
        filename = os.path.basename(zip_path)
        href = f'<a href="data:application/zip;base64,{b64}" download="{filename}">Download ZIP File</a>'
        return href

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
            search_range = st.number_input("Search Range Around Each ID", min_value=10, max_value=100, value=50)

        # Main content area
        st.header("Page URLs")

        # Create a form for URL inputs
        with st.form("url_inputs"):
            page_links = {}
            cols = st.columns(2)

            for page in range(1, num_pages + 1):
                with cols[page % 2]:
                    page_links[page] = st.text_input(
                        f"Starting URL for Page {page}",
                        help="Paste the full URL of any article on this page"
                    )

            submit_button = st.form_submit_button("Start Scraping")

        if submit_button:
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
                status_text = st.empty()

                for page_idx, page in enumerate(range(1, num_pages + 1)):
                    if page_links[page]:
                        start_id = extract_article_id(page_links[page])
                        if start_id:
                            status_text.text(f"Processing page {page}")
                            downloads = scraper.search_around_id(page, start_id, search_range)
                            all_downloads.extend(downloads)
                            st.write(f"Downloaded {len(downloads)} articles from page {page}")
                        else:
                            st.error(f"Invalid URL format for page {page}")
                    else:
                        st.warning(f"No URL provided for page {page}")

                    overall_progress.progress((page_idx + 1) / num_pages)

                status_text.text("Scraping completed!")

            with results_container:
                st.write("### Scraping Results")

                # Display statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Downloads", len(all_downloads))
                with col2:
                    st.metric("Pages Processed", num_pages)
                with col3:
                    st.metric("Success Rate", f"{(len(all_downloads)/(num_pages*search_range*2))*100:.1f}%")

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

                    # Create download link
                    href = create_download_link(zip_path)
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
