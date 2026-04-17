import asyncio
import json
import os
import discord
from discord.ext import commands
import requests
import ollama
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = "config.json"

# .envに書いた名前と同じにする必要があります
token = os.getenv("DISCORD_BOT_TOKEN") 

if not token:
    # config.jsonの中身を確認しに行く
    with open("config.json", "r") as f:
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

# youtube_processor の二重起動防止フラグ
is_processing = False

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')

@bot.command(name="setmodel")
async def setmodel(ctx, model_role: str, model_name: str):
    """
    Update the Ollama model.
    Usage: !setmodel chat gemma2:9b
       or: !setmodel summarize gemma2
    """
    global config
    if model_role == "chat":
        config["chat_model"] = model_name
    elif model_role == "summarize":
        config["summarize_model"] = model_name
    else:
        await ctx.send("無効なロールです。`chat` または `summarize` を指定してください。")
        return
        
    save_config(config)
    await ctx.send(f"✅ {model_role} 用のモデルを `{model_name}` に変更しました！")

@bot.command(name="update")
async def update(ctx):
    """
    最新のYouTube動画を取得・要約してDifyナレッジに登録する。
    Usage: !update
    """
    global is_processing
    if is_processing:
        await ctx.send("⚠️ すでに処理中です。完了まで少々お待ちください。")
        return

    is_processing = True
    await ctx.send(
        "🔄 **YouTube動画の更新を開始します**\n"
        "最新動画の取得 → トランスクリプト → 要約 → Dify登録 を行います。\n"
        "完了まで数分かかる場合があります..."
    )

    try:
        # uv run youtube_processor.py をサブプロセスで実行
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "youtube_processor.py",
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        out_text = stdout.decode("utf-8", errors="replace").strip()
        err_text = stderr.decode("utf-8", errors="replace").strip()
        combined = "\n".join(filter(None, [out_text, err_text]))

        if proc.returncode == 0:
            # 直近10行をDiscordに表示
            lines = [l for l in combined.splitlines() if l.strip()]
            log_snippet = "\n".join(lines[-10:]) if lines else "（出力なし）"
            await ctx.send(
                f"✅ **更新完了！**\n"
                f"新しいYouTube動画の要約をナレッジベースに登録しました。\n"
                f"```\n{log_snippet[:1500]}\n```"
            )
        else:
            snippet = combined[-1200:] if combined else "（詳細なし）"
            await ctx.send(
                f"❌ **処理中にエラーが発生しました**\n"
                f"```\n{snippet}\n```"
            )
    except FileNotFoundError:
        await ctx.send("❌ `uv` コマンドが見つかりません。PATHを確認してください。")
    except Exception as e:
        await ctx.send(f"❌ 処理の起動に失敗しました: {e}")
    finally:
        is_processing = False

def retrieve_from_dify(query):
    api_url = config.get("dify_api_url")
    api_key = config.get("dify_api_key")
    dataset_id = config.get("dify_dataset_id")
    
    if not api_key or api_key == "YOUR_DIFY_DATASET_API_KEY_HERE":
        return "Dify API が未設定です。回答生成は可能ですが、検索拡張は行えません。"

    # Dify retrieve API
    url = f"{api_url}/datasets/{dataset_id}/retrieve"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "retrieval_model": {
            "search_method": "keyword_search",
            "reranking_enable": False,
            "top_k": 3,
            "score_threshold_enabled": False
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            contents = [record["segment"]["content"] for record in records if "segment" in record]
            if not contents:
                print(f"Dify: No matching records for query: {query}")
                return None  # コンテキストなし
            return "\n\n---\n\n".join(contents)
        else:
            print(f"Dify Retrieve Failed ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"Dify Retrieve Error: {e}")
        return None

def generate_answer_with_ollama(query, context):
    model = config.get("chat_model", "gemma2")
    host = config.get("ollama_host", "http://localhost:11434")
    
    if context:
        # ナレッジベースに関連情報がある場合
        prompt = (
            "あなたはAIに関する最新情報を提供するAIアシスタントです。\n"
            "以下のYouTube動画の要約情報（コンテキスト）を参考にして、ユーザーの質問に日本語で回答してください。\n"
            "コンテキストに関連情報が含まれている場合はそれを優先して使用し、不足している場合は自分の知識を補足してください。\n\n"
            "【参考コンテキスト（YouTube要約）】\n"
            f"{context}\n\n"
            "【ユーザーの質問】\n"
            f"{query}"
        )
    else:
        # ナレッジベースに情報がない場合はLLM単体で回答
        prompt = (
            "あなたはAIに関する最新情報を提供するAIアシスタントです。\n"
            "ユーザーの質問に日本語で回答してください。\n"
            "現時点でのあなたの知識を使って、できる限り詳しく回答してください。\n\n"
            "【ユーザーの質問】\n"
            f"{query}"
        )
    
    client = ollama.Client(host=host)
    try:
        response = client.chat(model=model, messages=[
            {
                'role': 'user',
                'content': prompt
            }
        ])
        return response['message']['content']
    except Exception as e:
        return f"Ollamaとの通信エラー: {e}"

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
        
    # Let standard commands pass through
    await bot.process_commands(message)

    # Respond to mentions
    if bot.user in message.mentions:
        query = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if not query:
            return
            
        async with message.channel.typing():
            # 1. Retrieve Knowledge from Dify
            context = retrieve_from_dify(query)
            
            # 2. コンテキストがない場合は先に通知を送る
            if context is None:
                await message.reply(
                    "📚 ナレッジベースに該当する情報が見つかりませんでした。\n"
                    "自分の知識でお答えします 🤖",
                    mention_author=False
                )
            
            # 3. Generate Answer via local Ollama
            answer = generate_answer_with_ollama(query, context)
            
            # 4. Send back
            if len(answer) > 2000:
                answer = answer[:1996] + "..."

            await message.reply(answer, mention_author=False)

if __name__ == "__main__":
    # すでに冒頭で取得済みの token 変数をそのまま使う
    if not token:
        print("Please configure DISCORD_BOT_TOKEN in .env or config.json")
    else:
        bot.run(token)
