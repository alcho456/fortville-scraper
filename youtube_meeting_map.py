import os
import re
import folium
import yt_dlp
import base64
from googlemaps import Client as GoogleMaps


def extract_meeting_details(title):
    """Extracts the meeting date and type from the title."""
    pattern = r'(\d{2}/\d{2}/\d{2}) - (.+)'
    match = re.match(pattern, title)
    if match:
        date, meeting_type = match.groups()
        return date, meeting_type
    return None, None


def group_videos_with_short_addresses(video_details, base_file_url):
    """Groups videos by address."""
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
    try:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            return location['lat'], location['lng']
    except Exception as e:
        print(f"Geocoding failed for {address}: {e}")
    return None, None


def create_map_with_meeting_types(address_dict, api_key):
    """Creates a map with markers for each address."""
    m = folium.Map(location=[39.7684, -86.1581], zoom_start=10)
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
        else:
            print(f"Skipping address {address} - Geocoding failed.")
    return m


def fetch_real_video_details(channel_url, cookie_file):
    """Fetch video details using yt-dlp."""
    ydl_opts = {
        'quiet': True,
        'extract_flat': False,
        'force_generic_extractor': True,
        'no_warnings': True,
        'cookies': cookie_file,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(channel_url, download=False)
            videos = result.get('entries', [])
    except Exception as e:
        print(f"Error fetching video details: {e}")
        return []

    video_details = []
    for video in videos:
        if 'description' in video:
            video_details.append({
                "video_id": video['id'],
                "title": video['title'],
                "description": video.get('description', '')
            })

    return video_details


def decode_base64_to_file(base64_data, output_file):
    """Decode a Base64 string and write it to a file."""
    try:
        decoded_data = base64.b64decode(base64_data)
        with open(output_file, "wb") as file:
            file.write(decoded_data)
    except Exception as e:
        raise ValueError(f"Failed to decode Base64 data: {e}")


def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")

    youtube_cookies_base64 = os.getenv("YOUTUBE_COOKIES")
    if not youtube_cookies_base64:
        raise ValueError("YOUTUBE_COOKIES secret is not set")

    cookie_file = "cookies.txt"
    decode_base64_to_file(youtube_cookies_base64, cookie_file)

    base_file_url = "https://github.com/alcho456/fortville-scraper/tree/main/descriptions"
    channel_url = "https://www.youtube.com/channel/UCg4jC3F2rZropkP0rIH241w"

    video_details = fetch_real_video_details(channel_url, cookie_file)
    save_descriptions_to_files(video_details)
    address_dict = group_videos_with_short_addresses(video_details, base_file_url)
    meeting_map = create_map_with_meeting_types(address_dict, api_key)
    meeting_map.save("index.html")
    print("Map created and saved as index.html")


if __name__ == "__main__":
    main()
