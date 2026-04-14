#!/usr/bin/env python3
"""
Akashvani Radio Station Scraper

This script scrapes radio station data from https://akashvani.gov.in/radio/live.php
and updates the README.md with a markdown table of all India radio stations.

Usage:
    python scrape_radio.py

Exit codes:
    0 - Success (table updated)
    1 - Failure (error occurred, README not updated)
"""

import json
import os
import re
import sys
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)


# Configuration
URL = "https://akashvani.gov.in/radio/live.php"
README_PATH = "README.md"
JSON_PATH = "stations.json"
BEGIN_MARKER = "<!-- BEGIN: station list -->"
END_MARKER = "<!-- END: station list -->"


def fetch_html(url):
    """
    Fetch HTML content from the given URL.

    Args:
        url: The URL to fetch

    Returns:
        HTML content as string

    Raises:
        Exception: If the request fails
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def extract_channels_from_script(html):
    """
    Extract the JavaScript 'channels' object from the HTML.
    This contains the stream URLs for each station.

    Args:
        html: The HTML content

    Returns:
        Dictionary mapping channel ID to channel data including live_url
    """
    # Find the var channels = { ... } block
    pattern = r"var\s+channels\s*=\s*(\{[\s\S]*?\});"
    match = re.search(pattern, html)

    if not match:
        return {}

    channels_json = match.group(1)

    # Direct extraction using regex - much simpler than converting to JSON
    # Pattern: 'ID': { ... live_url: 'URL' ... }
    stream_urls = {}
    id_pattern = r"'(\d+)':\s*\{[^}]*?live_url:\s*'([^']+)'"

    for match in re.finditer(id_pattern, channels_json):
        channel_id = match.group(1)
        live_url = match.group(2)
        stream_urls[channel_id] = {"live_url": live_url}

    return stream_urls


def extract_stations_from_html(html, stream_urls):
    """
    Extract station information from the HTML.
    Parses <li data-channel> elements for channel name, state, language, and EPG info.

    Args:
        html: The HTML content
        stream_urls: Dictionary mapping channel ID to stream URL

    Returns:
        List of dictionaries containing station data
    """
    soup = BeautifulSoup(html, "html.parser")
    stations = []

    # Find all <li> elements with data-channel attribute
    li_elements = soup.find_all("li", attrs={"data-channel": True})

    for li in li_elements:
        # Get EPG ID from data-channel attribute
        epg_id = li.get("data-channel", "")

        # Get channel name from .station-search .channel-name
        name_elem = li.select_one(".station-search .channel-name")
        channel_name = name_elem.get_text(strip=True) if name_elem else ""

        # Get state from .station-search .channel-state
        state_elem = li.select_one(".station-search .channel-state")
        state = state_elem.get_text(strip=True) if state_elem else ""

        # Get language from .station-search .channel-language
        lang_elem = li.select_one(".station-search .channel-language")
        language = lang_elem.get_text(strip=True) if lang_elem else ""

        # Get EPG URL from .epg-button href
        epg_button = li.select_one(".epg-button")
        epg_url = epg_button.get("href", "") if epg_button else ""

        # Get stream URL from the channels dictionary
        stream_url = stream_urls.get(epg_id, {})
        if isinstance(stream_url, dict):
            stream_url = stream_url.get("live_url", "")

        # Only add if we have a channel name
        if channel_name:
            stations.append(
                {
                    "name": channel_name,
                    "stream_url": stream_url,
                    "state": state,
                    "language": language,
                    "epg_url": epg_url,
                    "epg_id": epg_id,
                }
            )

    return stations


def generate_markdown_table(stations):
    """
    Generate a markdown table from the stations data.

    Args:
        stations: List of station dictionaries

    Returns:
        Markdown formatted table string
    """
    lines = []

    # Header row
    lines.append("| Channel Name | Stream URL | State | Language | Programme Guide |")
    lines.append("|--------------|------------|-------|----------|-----------------|")

    for station in stations:
        # Format channel name (escape pipe characters)
        name = station["name"].replace("|", "\\|")

        # Format stream URL as clickable link
        if station["stream_url"]:
            stream_link = f"[Stream]({station['stream_url']})"
        else:
            stream_link = "N/A"

        # Format state (escape pipe characters)
        state = station["state"].replace("|", "\\|")

        # Format language (escape pipe characters)
        language = station["language"].replace("|", "\\|")

        # Format EPG as clickable link, or N/A if empty
        if station["epg_url"]:
            epg_link = f"[EPG]({station['epg_url']})"
        else:
            epg_link = "N/A"

        lines.append(f"| {name} | {stream_link} | {state} | {language} | {epg_link} |")

    return "\n".join(lines)


def save_json(stations):
    """
    Save station data to JSON file.

    Args:
        stations: List of station dictionaries
    """
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=2, ensure_ascii=False)


def update_readme(table_content):
    """
    Update the README.md file with the new table content.
    Replaces content between BEGIN and END markers.

    Args:
        table_content: The markdown table to insert

    Returns:
        True if successful, False otherwise
    """
    if not os.path.exists(README_PATH):
        # Create a new README with the markers
        initial_content = f"""# India Radio Stations

List of All India Radio (Akashvani) stations updated daily.

{BEGIN_MARKER}
{table_content}
{END_MARKER}

---
*Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(initial_content)
        return True

    # Read existing README
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if markers exist
    if BEGIN_MARKER not in content or END_MARKER not in content:
        print("Error: README.md does not contain the required markers.")
        print(f"Add the following to your README.md:")
        print(f"  {BEGIN_MARKER}")
        print(f"  ... table will be inserted here ...")
        print(f"  {END_MARKER}")
        return False

    # Find positions of markers
    begin_idx = content.find(BEGIN_MARKER) + len(BEGIN_MARKER)
    end_idx = content.find(END_MARKER)

    # Build new content
    # Add timestamp to the table
    table_content = (
        f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        + table_content
    )
    new_content = content[:begin_idx] + "\n" + table_content + "\n" + content[end_idx:]

    # Write back
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main():
    """
    Main function to orchestrate the scraping and update process.
    """
    print("Fetching radio station data from akashvani.gov.in...")

    try:
        # Step 1: Fetch HTML
        html = fetch_html(URL)
        print("HTML fetched successfully.")

        # Step 2: Extract stream URLs from JavaScript
        print("Extracting stream URLs from JavaScript...")
        stream_urls = extract_channels_from_script(html)
        print(f"Found {len(stream_urls)} stream URLs.")

        # Step 3: Extract station details from HTML
        print("Extracting station details from HTML...")
        stations = extract_stations_from_html(html, stream_urls)
        print(f"Found {len(stations)} stations.")

        if not stations:
            print("Error: No stations found. The website structure may have changed.")
            sys.exit(1)

        # Step 4: Generate markdown table
        print("Generating markdown table...")
        table = generate_markdown_table(stations)

        # Step 5: Update README
        print("Updating README.md...")
        if not update_readme(table):
            print("Error: Failed to update README.md")
            sys.exit(1)

        # Step 6: Save JSON
        print("Saving stations.json...")
        save_json(stations)

        print(
            "SUCCESS: Updated {} stations in README.md and stations.json".format(
                len(stations)
            )
        )
        sys.exit(0)

    except requests.RequestException as e:
        print(f"Error: Failed to fetch data from website: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
