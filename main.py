import os
import logging
import folium
import re
import pdfplumber
import requests
from flask import Flask, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Initialize Flask app
app = Flask(__name__, static_url_path='/static')

# Set up logging
log_level = os.getenv('LOG_LEVEL', 'WARNING').upper()  # Default to 'WARNING' if not set
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

def get_chrome_paths():
    """Retrieve the Chrome and Chromedriver paths from the environment."""
    chrome_binary = os.getenv("GOOGLE_CHROME_BIN", "/usr/bin/chromedriver")
    chromedriver_binary = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
    return chrome_binary, chromedriver_binary

def download_pdf(url, save_path):
    """Download a PDF file from the given URL."""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('Content-Type', ''):
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            logger.warning(f"Failed to download PDF from {url}. Status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading PDF from {url}: {e}")
        return False

def extract_addresses_from_pdf(pdf_path):
    """Extract addresses from a PDF."""
    address_pattern = r'\d{1,5}\s(?:\d{1,5}\s)?(?:[NSEW]?\s)?[A-Za-z0-9]+(?:\s[A-Za-z0-9]+)*(?:St|Street|Ave|Avenue|Blvd|Road|Rd|Ln|Drive|Dr|Ct|Court|Way|N|S|E|W|NW|NE|SW|SE|Trail)?(?:,\s?[A-Za-z]+(?:,\s?[A-Za-z]{2})?)?'
    addresses = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    business_text = re.split(r'New Business|Old Business', text, flags=re.IGNORECASE)
                    for section in business_text[1:]:
                        addresses.extend(re.findall(address_pattern, section))
        logger.debug(f"Extracted addresses from {pdf_path}: {addresses[:5]}")  # Only show first 5 for brevity
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}")
    return addresses

def get_meeting_data():
    """Scrapes the meeting agenda and address data."""
    try:
        logger.info("Fetching meeting data...")
        chrome_binary, chromedriver_binary = get_chrome_paths()

        if not os.path.exists(chrome_binary):
            raise FileNotFoundError(f"Chrome binary not found at {chrome_binary}")
        if not os.path.exists(chromedriver_binary):
            raise FileNotFoundError(f"Chromedriver binary not found at {chromedriver_binary}")

        # Chrome setup
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = chrome_binary

        # Chromedriver setup
        service = Service(chromedriver_binary)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # URL of the meeting page
        url = "https://www.fortville.in.gov/meetings"
        driver.get(url)

        # Explicit wait for page elements to load
        wait = WebDriverWait(driver, 20)
        elements = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, ".agenda-column a[aria-label*='Download PDF Agenda']")
        ))

        meetings = []
        static_dir = "static"
        os.makedirs(static_dir, exist_ok=True)

        for element in elements:
            agenda_text = element.get_attribute("aria-label")
            agenda_url = element.get_attribute("href")
            pdf_path = os.path.join(static_dir, os.path.basename(agenda_url))

            if download_pdf(agenda_url, pdf_path):
                addresses = extract_addresses_from_pdf(pdf_path)
                meetings.append((agenda_text, agenda_url, addresses))

        driver.quit()
        return meetings
    except Exception as e:
        logger.error(f"Error fetching meeting data: {str(e)}")
        return []

def create_map(meetings):
    """Generates a map with pins for each meeting address."""
    geolocator = Nominatim(user_agent="town-meetings-map")
    map = folium.Map(location=[40.7128, -74.0060], zoom_start=12)

    default_city = "Fortville"
    default_state = "IN"
    latitudes = []
    longitudes = []

    for agenda, address_url, addresses in meetings:
        for address in addresses:
            if ',' not in address:
                address = f"{address}, {default_city}, {default_state}"
            try:
                location = geolocator.geocode(address, timeout=20)
                if location:
                    latitudes.append(float(location.latitude))
                    longitudes.append(float(location.longitude))
                    folium.Marker(
                        location=[location.latitude, location.longitude],
                        popup=f"Agenda: {agenda}\nAddress: {address}",
                        icon=folium.Icon(color='blue')
                    ).add_to(map)
                else:
                    logger.warning(f"No location found for address: {address}")
            except GeocoderTimedOut:
                logger.warning(f"Timeout while geocoding address: {address}")
                continue

    if latitudes and longitudes:
        map.location = [sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)]
    else:
        map.location = [40.7128, -74.0060]

    map_path = os.path.join("static", "meeting_map.html")
    map.save(map_path)
    return map_path

@app.route('/')
def index():
    meetings = get_meeting_data()
    map_path = create_map(meetings)
    logger.info(f"Generated map HTML at: {map_path}")

    # Ensure the file path is relative and works correctly with url_for
    map_html = "meeting_map.html"  # Only the file name
    return render_template('map.html', map_html=map_html)

if __name__ == "__main__":
    app.run(debug=True)
