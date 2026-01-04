import datetime
import discord
from discord.ext import tasks
from config import DISCORD_TOKEN, NOTIFICATION_CHANNEL_ID, intents
from database import setup_database
from commands import setup_commands
from ui_components import DashboardView
from ranking import create_ranking_embed
from tasks import check_ranks_periodically_task_logic


# Botの初期化
bot: discord.Bot = discord.Bot(intents=intents)

# タスク関数（botオブジェクトにアクセスできるようにモジュールレベルで定義）
jst: datetime.timezone = datetime.timezone(datetime.timedelta(hours=9))


@tasks.loop(time=datetime.time(hour=12, minute=0, tzinfo=jst))
async def check_ranks_periodically() -> None:
    """定期的にランクをチェックし、更新する"""
    await check_ranks_periodically_task_logic(bot)


@bot.event
async def on_ready() -> None:
    print(f"Bot logged in as {bot.user}")

    # Bot起動時に永続Viewを登録
    bot.add_view(DashboardView())
    # ▼▼▼ 起動時にランキングを投稿する処理を追加 ▼▼▼
    print("--- Posting initial ranking on startup ---")
    channel: discord.TextChannel | discord.VoiceChannel | discord.Thread | None = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel:
        ranking_embed: discord.Embed = await create_ranking_embed(bot)
        if ranking_embed:
            await channel.send("【起動時ランキング速報】", embed=ranking_embed)

    # タスクを開始
    check_ranks_periodically.start()


# コマンドを登録
setup_commands(bot)


def run_bot() -> None:
    """Botを起動する"""
    setup_database()
    bot.run(DISCORD_TOKEN)
