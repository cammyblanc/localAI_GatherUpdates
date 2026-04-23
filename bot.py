import asyncio
import json
import os
import re
import discord
from discord.ext import commands
import requests
# ollama の代わりに openai をインポート
import subprocess
# ... (rest of imports)
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
                "search_method": "semantic_search",  # high_qualityデータセット用（ベクトル検索）
                "top_k": 10,
                "reranking_enable": False,
                "score_threshold_enabled": False
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
            "以下のコンテキストを参考にして、ユーザーの質問に日本語で回答してください。\n"
            "回答は以下の形式を厳守し、回答の最大文字数は1800語以内で非常に簡潔にまとめてください。\n\n"
            "【形式】\n"
            "- トピック（回答の主要なテーマを一行で）\n"
            "- 内容（3～5個の箇条書き）\n\n"
            f"【コンテキスト】\n{context}\n\n"
            f"【ユーザーの質問】\n{query}"
        )
    else:
        prompt = (
            "あなたはAIアシスタントです。日本語で回答してください。\n"
            "回答は以下の形式を厳守し、回答の最大文字数は1800語以内にまとめてください。\n\n"
            "【形式】\n"
            "- トピック（回答の主要なテーマを一行で）\n"
            "- 内容（3～5個の箇条書き）\n\n"
            f"【ユーザーの質問】\n{query}"
        )

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
    # メンションされた場合のみ反応
    if bot.user not in message.mentions:
        return

    raw_content = re.sub(r'<@!?\d+>', '', message.content).strip()

    # コマンド実行のチェック：メッセージが /update で始まるかを確認する。
    COMMAND_TRIGGER = "/update"
    if raw_content.lower().startswith(COMMAND_TRIGGER):
        # 引数を無視し、固定のコマンドを実行する
        command_str = "uv run youtube_processor.py"
        print(f"🚀 受信したコマンド実行リクエスト: {command_str}")
        await message.reply("🤖 ローカルスクリプトを実行中です。少々お待ちください...")

        try:
            # subprocessを使って外部コマンドを非同期で実行する
            result = await asyncio.to_thread(subprocess.run, command_str, shell=True, capture_output=True, text=True, check=True)

            full_output = result.stdout + (f"\n[STDOUT]\n{result.stderr}" if result.stderr else "") # stderrはエラーログとして扱うことが多いが、ここでは出力と合わせて渡す。

            await message.reply(f"✅ コマンド実行が完了しました。\n\n```\n{full_output}\n```")

        except subprocess.CalledProcessError as e:
            error_msg = f"❌ コマンドの実行中にエラーが発生しました (リターンコード {e.returncode}):\n```\n{e.stdout}{e.stderr}\n```"
            await message.reply(error_msg)
        except Exception as e:
            await message.reply(f"❌ スクリプト実行時に予期せぬ例外が発生しました: {e}")
    # 通常のクエリ処理 (元のロジックをここに続ける)
    else:
        raw_query = raw_content

        if not raw_query:
            return

        # 複数のトピックがある場合、カンマや句点、または「など」などの一般的な区切り文字で分割を試みる。
        topics = [t.strip() for t in re.split(r'[,.]|\b(also|and)\s', raw_query) if t and t.strip()]

        if not topics:
            # 分割に失敗した場合、元のクエリ全体を単一のトピックとして扱う
            topics = [raw_query]

        results = []
        for query in topics:
            async with message.channel.typing():
                context = retrieve_from_dify(query)

                if context is None:
                    print(f"ℹ️ Difyからコンテキストが返されませんでした (トピック: {query[:30]}...)")
                    results.append(f"\n\n--- トピック: {query} ---\n📚 ナレッジに情報がないため、一般知識で回答します。")
                else:
                    answer = await generate_answer_with_lm_studio(query, context)

                    # Discordの文字数制限対策
                    if len(answer) > 2000:
                        answer = answer[:1996] + "..."
                    results.append(f"\n\n--- トピック: {query} ---\n{answer}")

        final_response = "\n\n".join(results)
        await message.reply(final_response, mention_author=False)


if __name__ == "__main__":
    if not token:
        print("Please configure DISCORD_BOT_TOKEN")
    else:
        bot.run(token)