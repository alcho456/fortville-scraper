import os
import re
import folium
from googlemaps import Client as GoogleMaps

def extract_meeting_details(title):
    """
    Extracts the meeting date and type from the title.
    Assumes format: MM/DD/YY - Meeting Type
    """
    pattern = r'(\d{2}/\d{2}/\d{2}) - (.+)'
    match = re.match(pattern, title)
    if match:
        date, meeting_type = match.groups()
        return date, meeting_type
    return None, None

def group_videos_with_short_addresses(video_details, base_file_url):
    """
    Groups videos by address, including video recording links, description file links,
    and the meeting type, for shorter address formats.
    """
    address_pattern = r'\b\d{1,5}\s(?:[NSEW]\s)?(?:\w+\s){1,3}(?:St|Ave|Blvd|Rd|Dr|Ln|Ct|Pl|Way|Terr|Pkwy|Cir)\b'
    address_dict = {}

    for video in video_details:
        video_url = f"https://www.youtube.com/watch?v={video['video_id']}"
        description_file_url = f"{base_file_url}/{video['video_id']}.txt"
        title = video['title']
        date, meeting_type = extract_meeting_details(title)
        addresses = re.findall(address_pattern, video['description'])

        for address in addresses:
            if address not in address_dict:
                address_dict[address] = []
            address_dict[address].append({
                "date": date,
                "meeting_type": meeting_type,
                "video_url": video_url,
                "description_file_url": description_file_url,
                "description": video['description']
            })

    return address_dict

def save_descriptions_to_files(video_details, output_dir="descriptions"):
    """Save video descriptions to text files."""
    os.makedirs(output_dir, exist_ok=True)

    for video in video_details:
        file_path = os.path.join(output_dir, f"{video['video_id']}.txt")
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(video['description'])

def geocode_address(address, api_key):
    """Geocode an address using Google Maps API."""
    gmaps = GoogleMaps(api_key)
    geocode_result = gmaps.geocode(address)
    if geocode_result:
        location = geocode_result[0]['geometry']['location']
        return location['lat'], location['lng']
    return None, None

def create_map_with_meeting_types(address_dict, api_key):
    """
    Creates a map with markers containing video links, description files, and meeting types.
    """
    m = folium.Map(location=[39.7684, -86.1581], zoom_start=10)  # Adjust to your town

    for address, videos in address_dict.items():
        lat, lng = geocode_address(address, api_key)
        if lat and lng:
            content = "".join(
                f'<li>'
                f'<b>{video["date"]} - {video["meeting_type"]}</b><br>'
                f'Recording: <a href="{video["video_url"]}" target="_blank">Watch Video</a><br>'
                f'Description: <a href="{video["description_file_url"]}" target="_blank">View Details</a>'
                f'</li>'
                for video in videos
            )
            popup_content = (
                f'<b>Address:</b> {address}<br>'
                f'<b>Details:</b><ul>{content}</ul>'
            )
            folium.Marker([lat, lng], popup=popup_content).add_to(m)

    return m

def main():
    # Fetch the API key from the environment
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")

    # Replace with your file hosting base URL
    base_file_url = "https://your-file-hosting-service.com/descriptions"

    # Fetch video details dynamically (or use static data for testing)
    video_details = [
        {
            "video_id": "abc123",
            "title": "11/26/25 - Fortville Plan Commission",
            "description": "Meeting agenda for Fortville Plan Commission. Address: 123 W Main St."
        },
        {
            "video_id": "def456",
            "title": "12/15/25 - Fortville Town Council",
            "description": "Meeting agenda for Fortville Town Council. Address: 1500 W 1000 N."
        }
    ]

    # Save descriptions to files
    save_descriptions_to_files(video_details)

    # Group videos by address
    address_dict = group_videos_with_short_addresses(video_details, base_file_url)

    # Create the map
    meeting_map = create_map_with_meeting_types(address_dict, api_key)

    # Save the map to an HTML file
    meeting_map.save("map_with_meetings.html")
    print("Map created and saved as map_with_meetings.html")

if __name__ == "__main__":
    main()
