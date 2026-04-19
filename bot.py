import asyncio
import json
import os
import re
import discord
from discord.ext import commands
import requests
# ollama の代わりに openai をインポート
from openai import AsyncOpenAI 
from dotenv import load_dotenv
import time

load_dotenv()

CONFIG_PATH = "config.json"
token = os.getenv("DISCORD_BOT_TOKEN") 

if not token:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        token = config.get("discord_bot_token")

if not token:
    print("Please configure discord_bot_token in config.json or .env")
    exit(1)

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

is_processing = False

# --- Dify関連の関数 (同期処理のまま維持) ---
def retrieve_from_dify(query):
    api_url = config.get("dify_api_url")
    api_key = config.get("dify_api_key")
    dataset_id = config.get("dify_dataset_id")
    
    if not api_url or not api_key or not dataset_id:
        return None

    try:
        base_url = api_url.rstrip('/')
        url = f"{base_url}/datasets/{dataset_id}/retrieve"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "retrieval_model": {
                "search_method": "keyword_search",
                "top_k": 10,
                "reranking_enable": False,        # 追加：リランク機能をオフに設定
                "score_threshold_enabled": False  # 追加：スコア制限をオフに設定
            }
        }

        print(f"🔍 Difyへのリクエストクエリ: '{query}'")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            print(f"📊 取得件数: {len(records)}件")

            contents = []
            for record in records:
                content = record.get("content")
                if not content and "segment" in record:
                    content = record["segment"].get("content")
                if content:
                    contents.append(content)

            return "\n\n---\n\n".join(contents) if contents else None
        else:
            # ここで詳細なエラー内容を表示するようにしておきます
            print(f"❌ Dify APIエラー: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Dify通信例外: {e}")
    return None


async def generate_answer_with_lm_studio(query, context):
    host = config.get("llm_host", "http://localhost:1234/v1")
    model = config.get("chat_model", "loaded-model") # LM Studioでロード中のモデルが使われます

    if context:
        prompt = (
            "あなたはAIに関する最新情報を提供するAIアシスタントです。\n"
            "以下のコンテキストを参考にして、ユーザーの質問に日本語で回答してください。\n\n"
            f"【コンテキスト】\n{context}\n\n"
            f"【ユーザーの質問】\n{query}"
        )
    else:
        prompt = f"あなたはAIアシスタントです。日本語で回答してください。\n\n【ユーザーの質問】\n{query}"
    
    # LM Studio(OpenAI互換)クライアントの初期化
    client = AsyncOpenAI(base_url=host, api_key="lm-studio") # APIキーは任意でOK

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"LM Studioとの通信エラー: {e}"

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # メンションされた場合のみ反応
    if bot.user in message.mentions:
        # 正規表現でメンション部分（<@...>）を完全に除去
        query = re.sub(r'<@!?\d+>', '', message.content).strip()
        
        if not query:
            return
            
        async with message.channel.typing():
            context = retrieve_from_dify(query)
            
            if context is None:
                print("ℹ️ Difyからコンテキストが返されませんでした")
                await message.reply("📚 ナレッジに情報がないため、一般知識で回答します。", mention_author=False)
            
            answer = await generate_answer_with_lm_studio(query, context)
            
            # Discordの文字数制限対策
            if len(answer) > 2000:
                answer = answer[:1996] + "..."

            await message.reply(answer, mention_author=False)

if __name__ == "__main__":
    if not token:
        print("Please configure DISCORD_BOT_TOKEN")
    else:
        bot.run(token)
        