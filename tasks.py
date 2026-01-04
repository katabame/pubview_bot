import sqlite3
from typing import Any
import discord
from config import DB_PATH, NOTIFICATION_CHANNEL_ID, RANK_ROLES
from rank_helpers import get_rank_by_puuid, rank_to_value
from ranking import create_ranking_embed


async def check_ranks_periodically_task_logic(bot: discord.Bot) -> None:
    """定期的にランクをチェックし、更新する"""
    print("--- Starting periodic rank check ---")

    channel: discord.TextChannel | discord.VoiceChannel | discord.Thread | None = bot.get_channel(NOTIFICATION_CHANNEL_ID)

    con: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cur: sqlite3.Cursor = con.cursor()
    cur.execute("SELECT discord_id, riot_puuid, tier, rank, game_name, tag_line FROM users")
    registered_users: list[tuple[int, str, str | None, str | None, str, str]] = cur.fetchall()
    if not registered_users:
        con.close()
        return

    if not channel:
        print(f"Error: Notification channel with ID {NOTIFICATION_CHANNEL_ID} not found.")
        con.close()
        return

    promoted_users: list[dict[str, Any]] = []
    for discord_id, puuid, old_tier, old_rank, game_name, tag_line in registered_users:
        try:
            new_rank_info: dict[str, Any] | None = get_rank_by_puuid(puuid)
            guild: discord.Guild | None = channel.guild
            if not guild:
                continue
            member: discord.Member | None = await guild.fetch_member(discord_id)
            if not member:
                continue

            # --- データベース更新 ---
            if new_rank_info:
                cur.execute("UPDATE users SET tier = ?, rank = ?, league_points = ? WHERE discord_id = ?",
                            (new_rank_info['tier'], new_rank_info['rank'], new_rank_info['leaguePoints'], discord_id))
            else:
                cur.execute("UPDATE users SET tier = NULL, rank = NULL, league_points = NULL WHERE discord_id = ?", (discord_id,))

            # --- ランクアップ判定 ---
            if new_rank_info and old_tier and old_rank:
                old_value: int = rank_to_value(old_tier, old_rank, 0)
                new_value: int = rank_to_value(new_rank_info['tier'], new_rank_info['rank'], 0)
                if new_value > old_value:
                    promoted_users.append({
                        "member": member,
                        "game_name": game_name,
                        "tag_line": tag_line,
                        "old_tier": old_tier,
                        "old_rank": old_rank,
                        "new_tier": new_rank_info['tier'],
                        "new_rank": new_rank_info['rank']
                    })

            # --- ランク連動ロール処理 ---
            current_rank_tier: str | None = new_rank_info['tier'].upper() if new_rank_info else None

            # 現在のユーザーが持っているランクロールを確認
            current_rank_role: discord.Role | None = None
            for role_name in RANK_ROLES.values():
                role: discord.Role | None = discord.utils.get(guild.roles, name=role_name)
                if role and role in member.roles:
                    current_rank_role = role
                    break

            # 新しいランクに対応するロールを取得
            new_rank_role: discord.Role | None = None
            if current_rank_tier and current_rank_tier in RANK_ROLES:
                new_rank_role = discord.utils.get(guild.roles, name=RANK_ROLES[current_rank_tier])

            # ロールの変更が必要な場合のみ処理
            if current_rank_role != new_rank_role:
                # 古いランクロールを削除（存在する場合）
                if current_rank_role:
                    await member.remove_roles(current_rank_role)

                # 新しいランクロールを追加（存在する場合）
                if new_rank_role:
                    await member.add_roles(new_rank_role)

        except discord.NotFound:
            print(f"User with ID {discord_id} not found in the server. Skipping.")
            continue
        except Exception as e:
            print(f"Error processing user {discord_id}: {e}")
            continue

    con.commit()
    con.close()

    # --- 定期ランキング速報処理 ---
    if channel:
        ranking_embed: discord.Embed = await create_ranking_embed(bot)
        if ranking_embed:
            await channel.send("【定期ランキング速報】", embed=ranking_embed)

    # --- ランクアップ通知処理 ---
    if channel and promoted_users:
        for user_data in promoted_users:
            riot_id_full: str = f"{user_data['game_name']}#{user_data['tag_line'].upper()}"
            await channel.send(f"🎉 **ランクアップ！** 🎉\nおめでとうございます、{user_data['member'].mention}さん ({riot_id_full})！\n**{user_data['old_tier']} {user_data['old_rank']}** → **{user_data['new_tier']} {user_data['new_rank']}** に昇格しました！")

    print("--- Periodic rank check finished ---")
