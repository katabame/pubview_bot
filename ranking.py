import sqlite3
from typing import Any
import discord
from config import DB_PATH
from rank_helpers import rank_to_value


async def create_ranking_embed(bot: discord.Bot) -> discord.Embed:
    """ランキングのEmbedを作成する"""
    con: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cur: sqlite3.Cursor = con.cursor()
    # DBからランク情報がNULLでないユーザーのみを取得
    cur.execute("SELECT discord_id, game_name, tag_line, tier, rank, league_points FROM users WHERE tier IS NOT NULL AND rank IS NOT NULL")
    registered_users_with_rank: list[tuple[int, str, str, str, str, int]] = cur.fetchall()
    con.close()

    embed: discord.Embed = discord.Embed(title="🏆 ぱぶびゅ！内LoL(Solo/Duo)ランキング 🏆", color=discord.Color.gold())

    description_footer: str = "\n\n**`/register` コマンドであなたもランキングに参加しよう！**"
    description_update_time: str = "（ランキングは毎日正午に自動更新されます）"

    if not registered_users_with_rank:
        embed.description = f"現在ランク情報を取得できるユーザーがいません。\n{description_update_time}{description_footer}"
        return embed

    player_ranks: list[dict[str, Any]] = []
    for discord_id, game_name, tag_line, tier, rank, lp in registered_users_with_rank:
        player_ranks.append({
            "discord_id": discord_id, "game_name": game_name, "tag_line": tag_line,
            "tier": tier, "rank": rank, "lp": lp,
            "value": rank_to_value(tier, rank, lp)
        })

    sorted_ranks: list[dict[str, Any]] = sorted(player_ranks, key=lambda x: x['value'], reverse=True)

    embed.description = f"現在登録されているメンバーのランクです。\n{description_update_time}{description_footer}"

    role_emojis: dict[str, str] = {
        "CHALLENGER": "<:challenger:1407917898445357107>",
        "GRANDMASTER": "<:grandmaster:1407917001401434234>",
        "MASTER": "<:master:1407917005524176948>",
        "DIAMOND": "<:diamond:1407916987518156901>",
        "EMERALD": "<:emerald:1407916989581754458>",
        "PLATINUM": "<:plat:1407917008611184762>",
        "GOLD": "<:gold:1407916997303603303>",
        "SILVER": "<:silver:1407917015884103851>",
        "BRONZE": "<:bronze:1407917860763992167>",
        "IRON": "<:iron:1407917003397795901>",
    }

    # ティアごとにプレイヤーをグループ化
    players_by_tier: dict[str, list[dict[str, Any]]] = {}
    for player in sorted_ranks:
        tier: str = player['tier']
        if tier not in players_by_tier:
            players_by_tier[tier] = []
        players_by_tier[tier].append(player)

    # ティアの順序を定義
    tier_order: list[str] = ["CHALLENGER", "GRANDMASTER", "MASTER", "DIAMOND", "EMERALD", "PLATINUM", "GOLD", "SILVER", "BRONZE", "IRON"]

    # ティアごとにフィールドを追加
    rank_counter: int = 1
    for tier in tier_order:
        if tier in players_by_tier:
            tier_players: list[dict[str, Any]] = players_by_tier[tier]
            field_value: str = ""
            for player in tier_players:
                try:
                    user: discord.User = await bot.fetch_user(player['discord_id'])
                    mention_name: str = user.mention
                except discord.NotFound:
                    # サーバーにいないユーザーは display_name を使う（取得できない場合は'N/A'）
                    try:
                        user: discord.User = await bot.fetch_user(player['discord_id'])
                        mention_name: str = user.display_name
                    except:
                        mention_name: str = "N/A"

                riot_id_full: str = f"{player['game_name']}#{player['tag_line'].upper()}"
                # ランク情報の太字を解除
                field_value += f"{rank_counter}. {mention_name} ({riot_id_full})\n{player['tier']} {player['rank']} / {player['lp']}LP\n"
                rank_counter += 1

            if field_value:
                # フィールドのvalue上限(1024文字)を超えないように調整
                if len(field_value) > 1024:
                    field_value = field_value[:1020] + "..."

                # Tierヘッダーのデザインを調整
                # Tier名の長さに応じて罫線の数を変え、全体の長さを揃える
                base_length: int = 28
                header_core_length: int = len(tier) + 4  # 太字化の** **分
                padding_count: int = max(0, base_length - header_core_length)
                padding: str = "─" * padding_count

                header_text: str = f"{role_emojis[tier]} {tier} {role_emojis[tier]} {padding}"

                embed.add_field(
                    name=f"**{header_text}**",
                    value=field_value,
                    inline=False
                )

    return embed
