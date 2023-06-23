import os
import pickle
import telegram
from telegram.ext import Updater, CommandHandler
import youtube_dl
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import urllib.parse
import time


# Define the scopes required for YouTube Data API access
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


# Constants for Telegram bot token and YouTube API credentials
TELEGRAM_BOT_TOKEN = '6204189517:AAG_nD_RBu58OHZTZSPatXIHgIP6ueKmY1w'
CLIENT_SECRETS_FILE = 'client_secrets.json'
CREDENTIALS_PICKLE_FILE = 'credentials.pickle'

def authenticate():
    creds = None

    # Check if credentials already exist
    if os.path.exists(CREDENTIALS_PICKLE_FILE):
        with open(CREDENTIALS_PICKLE_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(CREDENTIALS_PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def upload_video(chat_id, video_url=None):
    # Authenticate and get the credentials
    credentials = authenticate()

    if video_url:
        # Download the video using youtube-dl
        ydl_opts = {
            'outtmpl': '%(id)s.%(ext)s',  # Use video ID as the filename
            'writeinfojson': True,  # Save video metadata in a JSON file
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_id = info.get('id', None)  # Get the video ID from the info dictionary
            ydl.download([video_url])

        # Get the downloaded video filename from youtube-dl's info JSON file
        metadata_file = f'{video_id}.info.json'
        if os.path.isfile(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            # Extract the video filename from the metadata
            video_filename = metadata['_filename']

            # Read the video metadata from the JSON file
            video_title = metadata['title']
            video_description = metadata['description']
            video_tags = metadata['tags']
    else:
        # Use the previously downloaded video
        video_filename = 'video.mp4'
        metadata_file = 'video.info.json'

        # Read the video metadata from the JSON file
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        video_title = metadata['title']
        video_description = metadata['description']
        video_tags = metadata['tags']

    # Create the request body
    request_body = {
        'snippet': {
            'title': video_title,
            'description': video_description,
            'tags': video_tags,
        },
        'status': {
            'privacyStatus': 'public',  # Change as needed
        }
    }

    # Authenticate and get the credentials
    credentials = authenticate()

    # Build the YouTube service
    youtube = build('youtube', 'v3', credentials=credentials)

    # Execute the upload request
    request = youtube.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=video_filename
    )
    response = request.execute()

    # Get the YouTube video URL
    uploaded_video_id = response['id']
    youtube_url = f'https://youtu.be/{uploaded_video_id}'

    # Delete the metadata file and downloaded video file
    if video_url:
        time.sleep(240)  # 300 seconds = 5 minutes  
        os.remove(metadata_file)
        os.remove(video_filename)

    # Send the YouTube URL via Telegram
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    bot.send_message(chat_id=chat_id, text=youtube_url)

    # Notify in console
    print(f"A new video has been uploaded: {youtube_url}")

def search_videos(chat_id, query):
    # Authenticate and get the credentials
    credentials = authenticate()

    # Build the YouTube service
    youtube = build('youtube', 'v3', credentials=credentials)

    # Search for YouTube Shorts videos matching the query
    try:
        response = youtube.search().list(
            q=query,
            part='id',
            maxResults=2,  # Get top 2 videos
            type='video',
            videoDuration='short',
            order='relevance'
        ).execute()

        # Extract the video IDs from the search results
        video_ids = [item['id']['videoId'] for item in response['items']]

        # Upload the videos
        for video_id in video_ids:
            upload_video(chat_id, video_id)

    except HttpError as e:
        print(f"An error occurred during the YouTube search: {e}")

def handle_command(update, context):
    command = update.message.text
    if command.startswith('/upload'):
        video_url = command.split(' ', 1)[1]
        upload_video(update.effective_chat.id, video_url)
    elif command.startswith('/search'):
        query = command.split(' ', 1)[1]
        search_videos(update.effective_chat.id, query)


def main():
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('upload', handle_command))
    dispatcher.add_handler(CommandHandler('search', handle_command))
    updater.start_polling()
    print("Telegram bot is running...")
    updater.idle()

if __name__ == '__main__':
    main()
