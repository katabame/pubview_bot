import os
import discord
from riotwatcher import RiotWatcher, LolWatcher

# --- 設定項目 ---
DISCORD_TOKEN: str | None = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY: str | None = os.getenv('RIOT_API_KEY')
DISCORD_GUILD_ID: int = int(os.getenv('DISCORD_GUILD_ID'))
DB_PATH: str = '/data/lol_bot.db'
NOTIFICATION_CHANNEL_ID: int = 1402091279700983819  # 通知用チャンネルID
HONOR_CHANNEL_ID: int = 1447166222591594607  # 名誉用チャンネルID
RANK_ROLES: dict[str, str] = {
    "IRON": "LoL Iron(Solo/Duo)", "BRONZE": "LoL Bronze(Solo/Duo)", "SILVER": "LoL Silver(Solo/Duo)",
    "GOLD": "LoL Gold(Solo/Duo)", "PLATINUM": "LoL Platinum(Solo/Duo)", "EMERALD": "LoL Emerald(Solo/Duo)",
    "DIAMOND": "LoL Diamond(Solo/Duo)", "MASTER": "LoL Master(Solo/Duo)",
    "GRANDMASTER": "LoL Grandmaster(Solo/Duo)", "CHALLENGER": "LoL Challenger(Solo/Duo)"
}

# --- Botの初期設定 ---
intents: discord.Intents = discord.Intents.default()
intents.members = True

# --- Riot Watcherの初期化 ---
riot_watcher: RiotWatcher = RiotWatcher(RIOT_API_KEY)
lol_watcher: LolWatcher = LolWatcher(RIOT_API_KEY)

my_region_for_account: str = 'asia'
my_region_for_summoner: str = 'jp1'
# ----------------
