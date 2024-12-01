import spotipy
from spotipy.oauth2 import SpotifyOAuth
import syncedlyrics
import time
import os
import re
from pypresence import Presence
import requests
import yaml

with open('config.yaml') as f:
    cfg = yaml.load(f,Loader=yaml.FullLoader)


SPOTIFY_CLIENT_ID = cfg['spotify']['client_id']
SPOTIFY_CLIENT_SECRET = cfg['spotify']['client_secret']
SPOTIFY_REDIRECT_URI = cfg['spotify']['redirect_uri']
DISCORD_CLIENT_ID = cfg['discord']['client_id']
CACHE_DIR = cfg['cache']['directory']


RPC = Presence(DISCORD_CLIENT_ID, pipe=0)
RPC.connect()

scope = "user-read-playback-state"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=scope
))


def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def parse_lrc(lrc_text):
    lyrics = []
    for line in lrc_text.splitlines():
        if line.startswith("[") and "]" in line:
            timestamp, text = line.split("]", 1)
            timestamp = timestamp.replace("[", "").split(":")
            seconds = int(timestamp[0]) * 60 + float(timestamp[1])
            lyrics.append((seconds, text.strip()))
    return lyrics

def get_current_lyric(lyrics, elapsed_time):
    for i, (timestamp, lyric) in enumerate(lyrics):
        if timestamp > elapsed_time:
            return lyrics[i - 1][1] if i > 0 else None
    return lyrics[-1][1] if lyrics else None

def fetch_lyrics(song_name, artist_name):
    cache_file = os.path.join(CACHE_DIR, f"{sanitize_filename(song_name)} - {sanitize_filename(artist_name)}.lrc")
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    try:
        lrc = syncedlyrics.search(f"{song_name} {artist_name}", synced_only=True)
        if lrc:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(lrc)
            return lrc
    except requests.exceptions.RequestException as e:
        print(f"Error fetching lyrics: {e}")
    
    return None

def update_rpc(lyric, song_name, artist_name):
    large_image_key = "spotify"
    small_image_key = "lyrics"

    if not lyric:
        lyric = "♫♫♫"

    RPC.update(
        details=f"{song_name} - {artist_name}",
        state=f"{lyric}",
        large_image=large_image_key,
        small_image=small_image_key
    )
def main():
    last_displayed_lyric = None
    
    while True:
        try:
            current_playback = sp.current_playback()
            if current_playback and current_playback["is_playing"]:
                track = current_playback["item"]
                song_name = track["name"]
                artist_name = ", ".join([artist["name"] for artist in track["artists"]])
                progress_ms = current_playback["progress_ms"]

                lrc = fetch_lyrics(song_name, artist_name)
                if lrc:
                    lyrics = parse_lrc(lrc)
                    elapsed_time = progress_ms / 1000
                    current_lyric = get_current_lyric(lyrics, elapsed_time)

                    if current_lyric != last_displayed_lyric:
                        print(current_lyric)
                        update_rpc(current_lyric, song_name, artist_name)
                        last_displayed_lyric = current_lyric
            time.sleep(0.1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
