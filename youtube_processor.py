import json
import os
import sys
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI  # LM Studio(OpenAI互換)用
import time
from dotenv import load_dotenv


load_dotenv()

CONFIG_PATH = "config.json"
PROCESSED_VIDEOS_PATH = "processed_videos.json"
DiscordWebHook = os.getenv("DISCORD_WEBHOOK_URL") 




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

def get_latest_videos(channel_url, max_downloads=5):
    if '@' in channel_url and not channel_url.endswith('/videos') and not channel_url.endswith('/shorts'):
        channel_url = channel_url.rstrip('/') + '/videos'
        
    print(f"最新動画採ってきます！ ココ--> {channel_url}")
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
            
            videos = [v for v in videos if not (len(v['id']) == 24 and v['id'].startswith('UC'))]
            return videos[:max_downloads]
        return []

def get_transcript(video_id):
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(['ja', 'en'])
        except Exception:
            transcript = transcript_list.find_generated_transcript(['en', 'ja'])
        
        full_text = " ".join([entry.text if hasattr(entry, 'text') else entry['text'] for entry in transcript.fetch()])
        return full_text
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return None

def summarize_with_lmstudio(transcript, model, host):
    """
    lms.exe (LM Studio CLI) が起動したOpenAI互換サーバーを使用して要約を行います。
    localLLM_prep.bat で「lms server start」により起動済みのサーバーに接続します。
    hostの例: http://localhost:1234/v1
    """
    # lms.exe が起動したサーバーはAPIキー不要ですが、クライアント初期化には文字列が必要です
    client = OpenAI(base_url=host, api_key="lm-studio")
    
    prompt = (
        "以下のYouTube動画のトランスクリプトを注意深く読み、内容をトピックごとに分類してそれぞれ日本語で要約してください。\n\n"
        "【要約のルール】\n"
        "1. 見出しは「## トピック名」とする\n"
        "2. 各トピックの内容は箇条書きを交えて分かりやすく記載する\n"
        "3. 全体は日本語で出力する\n\n"
        f"トランスクリプト:\n{transcript}"
    )
    
    print(f"Calling LM Studio with model: {model} at {host}")
    try:
        response = client.chat.completions.create(
            model=model,  # LM Studioでロードしているモデル名、または指定のID
            messages=[
                {"role": "system", "content": "あなたは優秀な要約アシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LM Studio error: {e}")
        return None

def summarize_briefly_with_lmstudio(transcript, model, host):
    """
    Discord投稿用に非常に簡潔な要約を行います。
    """
    client = OpenAI(base_url=host, api_key="lm-studio")
    
    prompt = (
        "以下のYouTube動画のトランスクリプトを読み、内容を非常に簡潔に要約してください。\n\n"
        "回答の最大文字数は1800語以内で非常に簡潔にまとめてください。\n\n"
        "【要約のルール】\n"
        "1. 形式は以下を厳守してください：\n"
        "   - トピック（動画の主要なテーマを一行で）\n"
        "   - 要約（3～5個の箇条書き）\n"
        "2. 全体は日本語で出力してください。\n\n"
        f"トランスクリプト:\n{transcript}"
    )
    
    print(f"Calling LM Studio for brief summary with model: {model}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたは需要な要点を損なわず簡潔に要約を作成するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LM Studio brief error: {e}")
        return None

def send_to_discord(webhook_url, title, video_url, summary):
    if webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE" or not webhook_url:
        print("Discord webhook URL not configured.")
        return
    
    content = f"**【新着要約】{title}**\n{video_url}\n\n{summary}"
    
    if len(content) > 1900:
        content = content[:1900] + "\n... (以降省略)"
    
    payload = {"content": content}
    requests.post(webhook_url, json=payload)

def push_to_dify(config, title, video_id, summary):
    api_url = config.get("dify_api_url")
    api_key = config.get("dify_api_key")
    dataset_id = config.get("dify_dataset_id")
    indexing_technique = config.get("dify_indexing_technique", "economy")
    
    if not api_key or not api_url or not dataset_id:
        print("🔴 Dify configuration missing.")
        return
        
    url = f"{api_url}/datasets/{dataset_id}/document/create_by_text"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    doc_text = f"Title: {title}\nVideo URL: https://youtube.com/watch?v={video_id}\n\nSummary:\n{summary}"
    payload = {
        "name": f"YouTube - {title}",
        "text": doc_text,
        "indexing_technique": indexing_technique,
        "process_rule": {"mode": "automatic"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code in (200, 201):
            print(f"🟢 Successfully uploaded to Dify.")
            return True
        else:
            print(f"🔴 Dify API failed: {response.text}")
    except Exception as e:
        print(f"❌ Dify error: {e}")

    return False

def process_latest_videos():
    config = load_config()
    processed_videos = load_processed_videos()
    
    check_updates = []
    videos = get_latest_videos(config["youtube_channel_url"])
    
    for video in videos:
        video_id = video['id']
        title = video['title']
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        if video_id in processed_videos:
            check_updates = '最新動画の追加なしでした！'
            continue
            
        print(f"Processing new video: {title} ({video_id})")
        
        transcript = get_transcript(video_id)
        if not transcript:
            continue
            
        # Dify用の詳細な要約
        summary_detailed = summarize_with_lmstudio(
            transcript=transcript,
            model=config.get("chat_model", "google/gemma-4-e4b"),
            host=config.get("llm_host", "http://localhost:1234/v1")
        )
        
        # Discord用の簡潔な要約
        summary_brief = summarize_briefly_with_lmstudio(
            transcript=transcript,
            model=config.get("chat_model", "google/gemma-4-e4b"),
            host=config.get("llm_host", "http://localhost:1234/v1")
        )
        
        if not summary_detailed or not summary_brief:
            continue
            
        send_to_discord(DiscordWebHook, title, video_url, summary_brief)
        push_to_dify(config, title, video_id, summary_detailed)
        
        processed_videos.append(video_id)
        save_processed_videos(processed_videos)
    print(check_updates)

if __name__ == "__main__":
    process_latest_videos()
