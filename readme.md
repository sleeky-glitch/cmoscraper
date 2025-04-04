# Gujarat Samachar E-Paper Scraper

A Streamlit application for scraping articles from Gujarat Samachar e-paper.

## Features

- Scrape multiple pages
- Configurable search range around article IDs
- Download all content as a ZIP file
- View scraping statistics and metadata
- Progress tracking

## Usage

1. Select the date to scrape
2. Enter the number of pages
3. Set the search range
4. Paste the URL for each page
5. Click "Start Scraping"
6. Download the ZIP file with all content

## Running Locally

```bash
pip install -r requirements.txt
streamlit run newspaper_scraper_app.py
