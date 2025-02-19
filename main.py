import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import jwt
import time
import json

# Spotify API credentials
SPOTIFY_CLIENT_ID = "your_spotify_client_id"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret"
SPOTIFY_REDIRECT_URI = "http://localhost:8888/callback"

# Apple Music API credentials
APPLE_MUSIC_TEAM_ID = "your_team_id"
APPLE_MUSIC_KEY_ID = "your_key_id"
APPLE_MUSIC_PRIVATE_KEY_PATH = "AuthKey_XXXXXX.p8"  # Path to Apple private key file

# Apple Music User Token (must be obtained manually from an Apple device)
APPLE_MUSIC_USER_TOKEN = "your_apple_music_user_token"

# Initialize Spotify API
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-library-read"
))

# Generate Apple Music Developer Token
def generate_apple_music_token():
    try:
        with open(APPLE_MUSIC_PRIVATE_KEY_PATH, "r") as f:
            private_key = f.read()

        headers = {
            "alg": "ES256",
            "kid": APPLE_MUSIC_KEY_ID
        }

        payload = {
            "iss": APPLE_MUSIC_TEAM_ID,
            "iat": int(time.time()),
            "exp": int(time.time()) + 15777000  # Valid for ~6 months
        }

        token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

        # Decode for older versions of PyJWT (only needed if jwt.encode() returns bytes)
        if isinstance(token, bytes):
            token = token.decode('utf-8')

        return token
    except Exception as e:
        print(f"Error generating Apple Music token: {e}")
        return None

APPLE_MUSIC_DEV_TOKEN = generate_apple_music_token()

if not APPLE_MUSIC_DEV_TOKEN:
    print("Failed to generate Apple Music token. Exiting.")
    exit(1)

# Fetch Liked Songs from Spotify
def get_spotify_liked_songs():
    songs = []
    results = sp.current_user_saved_tracks(limit=50)
    
    while results:
        for item in results["items"]:
            track = item["track"]
            songs.append({"name": track["name"], "artist": track["artists"][0]["name"]})
        
        # Get the next page of results
        results = sp.next(results) if results["next"] else None

    return songs

# Search for a song in Apple Music
def search_apple_music(song_name, artist_name):
    url = "https://api.music.apple.com/v1/catalog/us/search"
    headers = {
        "Authorization": f"Bearer {APPLE_MUSIC_DEV_TOKEN}",
        "Music-User-Token": APPLE_MUSIC_USER_TOKEN
    }
    params = {
        "term": f"{song_name} {artist_name}",
        "types": "songs",
        "limit": 1
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        try:
            data = response.json()
            if "songs" in data.get("results", {}):
                return data["results"]["songs"]["data"][0]["id"]
        except json.JSONDecodeError:
            print(f"Error parsing Apple Music response for {song_name} by {artist_name}.")
    else:
        print(f"Apple Music API error: {response.status_code} - {response.text}")

    return None

# Add song to Apple Music Library
def add_song_to_apple_music(song_id):
    url = "https://api.music.apple.com/v1/me/library"
    headers = {
        "Authorization": f"Bearer {APPLE_MUSIC_DEV_TOKEN}",
        "Music-User-Token": APPLE_MUSIC_USER_TOKEN,
        "Content-Type": "application/json"
    }
    data = {
        "data": [{"id": song_id, "type": "songs"}]  # Correct format for Apple Music API
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 202:
        return True
    else:
        print(f"Failed to add song {song_id}: {response.status_code} - {response.text}")
        return False

# Main function to sync Spotify liked songs with Apple Music
def sync_songs():
    print("Fetching liked songs from Spotify...")
    spotify_songs = get_spotify_liked_songs()
    print(f"Found {len(spotify_songs)} liked songs on Spotify.")

    for song in spotify_songs:
        print(f"Processing: {song['name']} by {song['artist']}...")

        # Search for the song in Apple Music
        song_id = search_apple_music(song["name"], song["artist"])
        if song_id:
            success = add_song_to_apple_music(song_id)
            if success:
                print(f"✅ Added: {song['name']} by {song['artist']} to Apple Music.")
            else:
                print(f"❌ Failed to add: {song['name']} by {song['artist']}.")
        else:
            print(f"🔍 No match found for: {song['name']} by {song['artist']}.")

sync_songs()
