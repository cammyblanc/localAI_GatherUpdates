import asyncio
import json
import os
import re
import discord
from discord.ext import commands
import requests
from openai import AsyncOpenAI 
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
            "あなたは文章全体から主要なトピックを特定し、各トピックについて重要な論点をまとめる優秀な報告書作成者です。\n"
            "以下のコンテキストを読み、日本語で内容を非常に簡潔に要約してください。\n\n"
            "回答の最大文字数は1800語以内にまとめてください。\n\n"
            "質問の目的により回答のまとめ方が異なります。\n"
            "以下の３つのルールから最も近いものを質問の目的に合わせて選んで回答を作成してください。\n"
            "回答自体にはルールの記載は不要です。\n\n"
            "ルール１-【質問の目的が「リスト作成」の場合】\n"
            "# 回答の対象とするデータ：\n"
            "   - 質問にトピックの指定が含まれる場合はそのトピックに含まれる文章のみを参照し、他のトピックは含まない\n"
            "# 回答の形式：\n"
            "   - 質問に含まれる項目についてのみのリストを箇条書きで作成。\n\n"
            "   - 各トピック自体以外の説明は含まない。\n\n"
            "ルール２-【質問の目的が「要約」の場合】\n"
            "# 回答の対象とするデータ：\n"
            "   - 質問にトピックの指定が含まれる場合はそのトピックに含まれる文章のみを参照し、他のトピックは含まない\n"
            "# 回答の形式：\n"
            "   - 主題（回答の概要を一行で記述）\n"
            "   - 要約（3～5個の箇条書き）\n"
            "   - 参照したトピックのリスト化\n\n"
            "ルール３-【質問の目的に沿ったルールがない場合】\n"
            "# 回答の形式：\n"
            "   - 特定のフォーマットに縛られず、500語以内を目標に回答を作成\n"
            f"【コンテキスト】\n{context}\n\n"
            f"【ユーザーの質問】\n{query}"
        )

    else:
        prompt = (
            "あなたは重要な論点をまとめる優秀な報告書作成者です。日本語で回答してください。\n"
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
            
    elif raw_content.lower().startswith("/add"):
        parts = raw_content.split(maxsplit=1)
        if len(parts) > 1:
            new_url = parts[1].strip()
            if new_url.startswith("http"):
                try:
                    prefix = ""
                    if os.path.exists("list_youtube.txt") and os.path.getsize("list_youtube.txt") > 0:
                        with open("list_youtube.txt", "rb") as f:
                            f.seek(-1, os.SEEK_END)
                            if f.read(1) != b'\n':
                                prefix = "\n"

                    with open("list_youtube.txt", "a", encoding="utf-8") as f:
                        f.write(f"{prefix}{new_url}\n")
                    await message.reply(f"✅ チャンネルリストに追加しました:\n{new_url}")
                except Exception as e:
                    await message.reply(f"❌ 追加中にエラーが発生しました: {e}")
            else:
                await message.reply("⚠️ 有効なURLを指定してください。（httpから始まるもの）")
        else:
            await message.reply("⚠️ URLが指定されていません。`/add <URL>` の形式で送信してください。")

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