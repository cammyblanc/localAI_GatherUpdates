import json
import os
import sys
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
import ollama

CONFIG_PATH = "config.json"
PROCESSED_VIDEOS_PATH = "processed_videos.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("config.json not found. Please create one based on the template.")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_processed_videos():
    if not os.path.exists(PROCESSED_VIDEOS_PATH):
        return []
    with open(PROCESSED_VIDEOS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_processed_videos(video_ids):
    with open(PROCESSED_VIDEOS_PATH, "w", encoding="utf-8") as f:
        json.dump(video_ids, f, ensure_ascii=False, indent=4)

def get_latest_videos(channel_url, max_downloads=3):
    # Ensure channel_url gets videos instead of tabs if it's an @channel URL
    if '@' in channel_url and not channel_url.endswith('/videos') and not channel_url.endswith('/shorts'):
        channel_url = channel_url.rstrip('/') + '/videos'
        
    print(f"Fetching latest videos from {channel_url}...")
    ydl_opts = {
        'extract_flat': True,
        'playlist_items': f'1-{max_downloads}',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(channel_url, download=False)
        if 'entries' in result:
            videos = []
            for entry in result['entries']:
                if 'entries' in entry:
                    for sub in entry['entries']:
                        if sub.get('id'): videos.append(sub)
                elif entry.get('id'):
                    videos.append(entry)
            
            # Remove incorrectly captured channel tabs (channel IDs start with UC and are 24 chars)
            videos = [v for v in videos if not (len(v['id']) == 24 and v['id'].startswith('UC'))]
            return videos[:max_downloads]
        return []

def get_transcript(video_id):
    try:
        # Try to fetch transcript, preferring Japanese, then English
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        # Try to find a playable transcript, fallback to auto-generated
        try:
            transcript = transcript_list.find_transcript(['ja', 'en'])
        except Exception:
            # Fallback to any transcript
            transcript = transcript_list.find_generated_transcript(['en', 'ja'])
        
        full_text = " ".join([entry.text if hasattr(entry, 'text') else entry['text'] for entry in transcript.fetch()])
        return full_text
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return None

def summarize_with_ollama(transcript, model, host):
    client = ollama.Client(host=host)
    prompt = (
        "以下のYouTube動画のトランスクリプトを注意深く読み、内容をトピックごとに分類してそれぞれ日本語で要約してください。\n\n"
        "【要約のルール】\n"
        "1. 見出しは「## トピック名」とする\n"
        "2. 各トピックの内容は箇条書きを交えて分かりやすく記載する\n"
        "3. 全体は日本語で出力する\n\n"
        f"トランスクリプト:\n{transcript}"
    )
    
    # We may need to truncate the transcript if it's too long, but we'll try sending as is
    # Gemma handles typical 8k context, which is roughly 10-20 min speech.
    print(f"Calling Ollama with model: {model}")
    try:
        response = client.chat(model=model, messages=[
            {
                'role': 'user',
                'content': prompt
            }
        ])
        return response['message']['content']
    except Exception as e:
        print(f"Ollama error: {e}")
        return None

def send_to_discord(webhook_url, title, video_url, summary):
    if webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE" or not webhook_url:
        print("Discord webhook URL not configured.")
        return
    
    # Discord limitation of 2000 chars per message, might need splitting or sending as embed
    content = f"**【新着要約】{title}**\n{video_url}\n\n{summary}"
    
    if len(content) > 1900:
        content = content[:1900] + "\n... (以降省略)"
    
    payload = {
        "content": content
    }
    requests.post(webhook_url, json=payload)

def push_to_dify(config, title, video_id, summary):
    api_url = config.get("dify_api_url")
    api_key = config.get("dify_api_key")
    dataset_id = config.get("dify_dataset_id")
    indexing_technique = config.get("dify_indexing_technique", "economy")
    
    if not api_key or api_key == "YOUR_DIFY_DATASET_API_KEY_HERE":
        print("Dify API key not configured. Skipping Dify push.")
        return
    if not dataset_id or not api_url:
        print("Dify dataset_id or api_url not configured. Skipping Dify push.")
        return
        
    url = f"{api_url}/datasets/{dataset_id}/document/create_by_text"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # We combine title and summary as the knowledge content
    doc_text = f"Title: {title}\nVideo URL: https://youtube.com/watch?v={video_id}\n\nSummary:\n{summary}"
    
    payload = {
        "name": f"YouTube - {title}",
        "text": doc_text,
        "indexing_technique": indexing_technique,
        "process_rule": {
            "mode": "automatic"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code in (200, 201):
            doc_id = response.json().get("document", {}).get("id", "unknown")
            print(f"Successfully uploaded to Dify. doc_id={doc_id}")
        else:
            print(f"Failed to upload to Dify (HTTP {response.status_code}): {response.text}")
    except requests.exceptions.ConnectionError as e:
        print(f"Dify connection error: {e}")
    except Exception as e:
        print(f"Dify upload error: {e}")


def process_latest_videos():
    config = load_config()
    processed_videos = load_processed_videos()
    
    videos = get_latest_videos(config["youtube_channel_url"])
    
    for video in videos:
        video_id = video['id']
        title = video['title']
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        if video_id in processed_videos:
            continue
            
        print(f"Processing new video: {title} ({video_id})")
        
        # 1. Get Transcript
        transcript = get_transcript(video_id)
        if not transcript:
            continue
            
        # 2. Summarize
        summary = summarize_with_ollama(
            transcript=transcript, 
            model=config.get("summarize_model", "gemma2"),
            host=config.get("ollama_host", "http://localhost:11434")
        )
        
        if not summary:
            continue
            
        # 3. Send to Discord Webhook (optional, but good for active push)
        send_to_discord(config.get("discord_webhook_url"), title, video_url, summary)
        
        # 4. Push to Dify Database
        push_to_dify(config, title, video_id, summary)
        
        # Mark as processed
        processed_videos.append(video_id)
        save_processed_videos(processed_videos)

if __name__ == "__main__":
    process_latest_videos()
