# YouTube 要約 & Discord RAG ボット

このプロジェクトは特定のYouTubeチャンネルの新着動画の字幕を取得し、Ollama (Gemmaなど) を使って要約した後、Difyのナレッジベースに保存してDiscordからRAG (検索拡張生成) による質問応答を行うシステムです。

## 前提条件
- `uv` (Python パッケージマネージャ)
- `Ollama` がローカルで起動しており、指定するモデル（デフォルトは `gemma2`）が pull されていること
- `Dify` が利用可能であり、**空のデータセット（ナレッジベース）** とその **データセットAPIキー** が作成されていること
- Discord Botが作成済みで、サーバーに招待されていること

## セットアップ

1. **設定ファイルの準備**
   `config.json` を開き、必要な設定を入力してください。プレースホルダー (`YOUR_*_HERE`) になっている項目は必須です。
   ```json
   {
       "youtube_channel_url": "https://youtube.com/@airevolutionx",
       "discord_webhook_url": "YOUR_DISCORD_WEBHOOK_URL_HERE",
       "discord_bot_token": "YOUR_DISCORD_BOT_TOKEN_HERE",
       "discord_bot_channel_id": null,
       "dify_api_url": "http://localhost/v1",
       "dify_api_key": "YOUR_DIFY_DATASET_API_KEY_HERE",
       "dify_dataset_id": "YOUR_DIFY_DATASET_ID_HERE",
       "ollama_host": "http://localhost:11434",
       "summarize_model": "gemma2",
       "chat_model": "gemma2"
   }
   ```
   > **Note**: `dify_dataset_id` は Dify側でデータセットを作成した際、URL等から確認できる UUID（ハイフン付きまたは無し）です。

2. **依存関係のインストール**
   ```bash
   uv sync
   ```

## 使い方

### 1. 新着動画の要約とDifyへの登録（定期実行）
以下のスクリプトを実行すると、チャンネルの最新動画をチェック・要約してDiscordのWebhookに通知し、Difyのナレッジとして保存します。
```bash
uv run youtube_processor.py
```
*(Windowsのタスクスケジューラなどで、このコマンドを1日1回・数時間おきなどに定期実行するように設定してください。)*

### 2. Discord RAG ボットの起動
以下のスクリプトを実行してBotを常駐させます。
```bash
uv run bot.py
```

### Discordでの利用方法

- **質問する**
  Botに対してメンションをつけてメッセージを送ります。
  > `@BotName 先日の〇〇というAIツールについて教えて`
  Difyのナレッジから関連情報を検索し、Gemmaモデルが日本語で回答してくれます。

- **LLMモデルの変更**
  以下のコマンドをDiscord上で送信することで、`config.json` 内の利用モデルを動的に変更できます（Ollamaでpull済みのモデル名を指定してください）。
  
  - 質問回答用モデルの変更:
    > `!setmodel chat gemma2:9b`
  - 動画要約用モデルの変更:
    > `!setmodel summarize gemma2`

### docker + difyのセットアップ

Docker Desktop の準備 まだ入っていない場合は、Docker Desktop for Windows をインストールし、起動しておきます。
Difyのソースコードをダウンロード コマンドプロンプトやPowerShellで、Difyを保存したい場所（例: Documents など）を開き、以下のコマンドを順に実行します。
powershell
# 1. フォルダをダウンロード
git clone https://github.com/langgenius/dify.git
# 2. docker フォルダに移動
cd dify\docker
# 3. 環境設定ファイルをコピーして作成
copy .env.example .env
# 4. Difyを起動（初回はダウンロードに少し時間がかかります）
docker compose up -d

ブラウザでアクセス コンソール等でエラーが出ずに起動が終わったら、ブラウザから http://localhost にアクセスします。 初回アクセス時は管理者アカウントの登録画面が出ますので、設定してログインしてください。
起動が確認できたら、あとは先ほどの手順で「ナレッジ」からデータセットを作成し、キーを取得すれば連携完了です！もしDockerのインストールなどで詰まることがあれば教えてください。