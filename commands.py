import sqlite3
from typing import Any
import discord
from riotwatcher import ApiError
from config import DB_PATH, RANK_ROLES, NOTIFICATION_CHANNEL_ID, DISCORD_GUILD_ID, riot_watcher, my_region_for_account
from rank_helpers import get_rank_by_puuid
from ranking import create_ranking_embed
from ui_components import DashboardView


def setup_commands(bot: discord.Bot) -> None:
    """ボットにコマンドを登録する"""

    @bot.slash_command(name="register", description="あなたのRiot IDをボットに登録します。", guild_ids=[DISCORD_GUILD_ID])
    async def register(ctx: discord.ApplicationContext, game_name: str, tag_line: str) -> None:
        await ctx.defer()
        if tag_line.startswith("#"):
            tag_line = tag_line[1:]
        tag_line = tag_line.upper()
        try:
            account_info: dict[str, Any] = riot_watcher.account.by_riot_id(my_region_for_account, game_name, tag_line)
            puuid: str = account_info['puuid']
            rank_info: dict[str, Any] | None = get_rank_by_puuid(puuid)

            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            if rank_info:
                cur.execute("INSERT OR REPLACE INTO users (discord_id, riot_puuid, game_name, tag_line, tier, rank, league_points) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (ctx.author.id, puuid, game_name, tag_line, rank_info['tier'], rank_info['rank'], rank_info['leaguePoints']))
            else:
                cur.execute("INSERT OR REPLACE INTO users (discord_id, riot_puuid, game_name, tag_line, tier, rank, league_points) VALUES (?, ?, ?, ?, NULL, NULL, NULL)",
                            (ctx.author.id, puuid, game_name, tag_line))
            con.commit()
            con.close()
            await ctx.respond(f"Riot ID「{game_name}#{tag_line}」を登録しました！")
        except ApiError as err:
            if err.response.status_code == 404:
                await ctx.respond(f"Riot ID「{game_name}#{tag_line}」が見つかりませんでした。")
            else:
                await ctx.respond("Riot APIでエラーが発生しました。")
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'register' command: {e}")
            await ctx.respond("登録中に予期せぬエラーが発生しました。")

    @bot.slash_command(name="register_by_other", description="指定したユーザーのRiot IDをボットに登録します。（管理者向け）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def register_by_other(ctx: discord.ApplicationContext, user: discord.Member, game_name: str, tag_line: str) -> None:
        await ctx.defer(ephemeral=True)  # コマンド結果は実行者のみに見える
        if tag_line.startswith("#"):
            tag_line = tag_line[1:]
        tag_line = tag_line.upper()
        try:
            account_info: dict[str, Any] = riot_watcher.account.by_riot_id(my_region_for_account, game_name, tag_line)
            puuid: str = account_info['puuid']
            rank_info: dict[str, Any] | None = get_rank_by_puuid(puuid)

            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            target_discord_id: int = user.id
            if rank_info:
                cur.execute("INSERT OR REPLACE INTO users (discord_id, riot_puuid, game_name, tag_line, tier, rank, league_points) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (target_discord_id, puuid, game_name, tag_line, rank_info['tier'], rank_info['rank'], rank_info['leaguePoints']))
            else:
                cur.execute("INSERT OR REPLACE INTO users (discord_id, riot_puuid, game_name, tag_line, tier, rank, league_points) VALUES (?, ?, ?, ?, NULL, NULL, NULL)",
                            (target_discord_id, puuid, game_name, tag_line))
            con.commit()
            con.close()
            await ctx.respond(f"ユーザー「{user.display_name}」にRiot ID「{game_name}#{tag_line}」を登録しました！")
        except ApiError as err:
            if err.response.status_code == 404:
                await ctx.respond(f"Riot ID「{game_name}#{tag_line}」が見つかりませんでした。")
            else:
                await ctx.respond(f"Riot APIでエラーが発生しました。詳細はログを確認してください。")
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'register_by_other' command: {e}")
            await ctx.respond("登録中に予期せぬエラーが発生しました。")

    @bot.slash_command(name="unregister", description="ボットからあなたの登録情報を削除します。", guild_ids=[DISCORD_GUILD_ID])
    async def unregister(ctx: discord.ApplicationContext) -> None:
        await ctx.defer()
        try:
            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            cur.execute("DELETE FROM users WHERE discord_id = ?", (ctx.author.id,))
            con.commit()
            if con.total_changes > 0:
                await ctx.respond("あなたの登録情報を削除しました。")
            else:
                await ctx.respond("あなたはまだ登録されていません。")
            con.close()

            # --- ランク連動ロール削除処理 ---
            guild: discord.Guild | None = ctx.guild
            if guild:
                member: discord.Member = await guild.fetch_member(ctx.author.id)
                role_names_to_remove: list[discord.Role | None] = [discord.utils.get(guild.roles, name=role_name) for role_name in RANK_ROLES.values()]
                await member.remove_roles(*[role for role in role_names_to_remove if role is not None and role in member.roles])

        except Exception as e:
            await ctx.respond("登録解除中に予期せぬエラーが発生しました。")

    @bot.slash_command(name="ranking", description="サーバー内のLoLランクランキングを表示します。", guild_ids=[DISCORD_GUILD_ID])
    async def ranking(ctx: discord.ApplicationContext) -> None:
        await ctx.defer()
        try:
            ranking_embed: discord.Embed = await create_ranking_embed(bot)
            if ranking_embed:
                await ctx.respond(embed=ranking_embed)
            else:
                await ctx.respond("まだ誰も登録されていないか、ランク情報を取得できるユーザーがいません。")
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'ranking' command: {e}")
            await ctx.respond("ランキングの作成中にエラーが発生しました。")

    # --- 管理者向けコマンド ---
    @bot.slash_command(name="dashboard", description="登録・登録解除用のダッシュボードを送信します。（管理者向け）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def dashboard(ctx: discord.ApplicationContext, channel: discord.TextChannel | None = None) -> None:
        """
        ダッシュボードメッセージを送信します。
        """
        target_channel: discord.TextChannel | discord.VoiceChannel | discord.Thread = channel or ctx.channel
        embed: discord.Embed = discord.Embed(
            title="# ダッシュボード",  # 絵文字は適当なものに置き換えてください
            description=(
                "## 名誉を贈る\n"
                "名誉を贈りたいユーザーと理由を入力してください。\n"
                "## Riot IDの登録\n"
                "あなたのRiot IDをサーバーに登録しましょう！\n"
                f"このボタンからあなたのRiot IDを登録すると、あなたのSolo/Duoランクが24時間ごとに自動でチェックされ、サーバー内のラダーランキング(<#{NOTIFICATION_CHANNEL_ID}>)に反映されます。\n"
                "## Riot IDの登録解除\n"
                "ボットからあなたのRiot ID情報を削除します。\n"
                "## セクションに参加\n"
                "セクションのテキスト、ボイスチャンネルに参加します。\n"
                "セクションの人数上限は35名です。\n"
            ),
            color=discord.Color.blue()
        )

        await target_channel.send(embed=embed, view=DashboardView())
        await ctx.respond("ダッシュボードを送信しました。", ephemeral=True)

    @bot.slash_command(name="add_section", description="参加可能なセクションを登録します。（管理者向け）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def add_section(ctx: discord.ApplicationContext, section_role: discord.Role, notification_channel: discord.TextChannel) -> None:
        await ctx.defer(ephemeral=True)
        try:
            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            cur.execute("INSERT OR REPLACE INTO sections (role_id, section_name, notification_channel_id) VALUES (?, ?, ?)",
                        (section_role.id, section_role.name, notification_channel.id))
            con.commit()
            con.close()
            await ctx.respond(f"セクション（ロール「{section_role.name}」）を、通知チャンネル「{notification_channel.name}」と紐付けて登録しました。")
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'add_section' command: {e}")
            await ctx.respond("セクションの登録中に予期せぬエラーが発生しました。")

    @bot.slash_command(name="remove_section", description="参加可能なセクションを削除します。（管理者向け）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def remove_section(ctx: discord.ApplicationContext, section_role: discord.Role) -> None:
        await ctx.defer(ephemeral=True)
        try:
            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            cur.execute("DELETE FROM sections WHERE role_id = ?", (section_role.id,))
            con.commit()

            if con.total_changes > 0:
                await ctx.respond(f"セクション（ロール「{section_role.name}」）をDBから削除しました。")
            else:
                await ctx.respond(f"指定されたセクション（ロール）はDBに登録されていません。")

            con.close()
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'remove_section' command: {e}")
            await ctx.respond("セクションの削除中に予期せぬエラーが発生しました。")

    @bot.slash_command(name="remove_user_from_section", description="指定したユーザーをセクションから退出させます。（管理者向け）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def remove_user_from_section(ctx: discord.ApplicationContext, user: discord.Member, section_role: discord.Role) -> None:
        await ctx.defer(ephemeral=True)

        # 指定されたロールがセクションとして登録されているか確認
        con: sqlite3.Connection = sqlite3.connect(DB_PATH)
        cur: sqlite3.Cursor = con.cursor()
        cur.execute("SELECT 1 FROM sections WHERE role_id = ?", (section_role.id,))
        is_section: tuple[int] | None = cur.fetchone()
        con.close()

        if not is_section:
            await ctx.respond(f"エラー: ロール「{section_role.name}」はセクションとして登録されていません。")
            return

        if section_role not in user.roles:
            await ctx.respond(f"ユーザー「{user.display_name}」はセクション「{section_role.name}」に参加していません。")
            return

        try:
            await user.remove_roles(section_role)
            await ctx.respond(f"ユーザー「{user.display_name}」をセクション「{section_role.name}」から退出させました。")
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'remove_user_from_section' command: {e}")
            await ctx.respond("セクションからの退出処理中に予期せぬエラーが発生しました。")

    # --- デバッグ用コマンド ---
    @bot.slash_command(name="debug_check_ranks_periodically", description="定期的なランクチェックを手動で実行します。（デバッグ用）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def debug_check_ranks_periodically(ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)
        try:
            await ctx.respond("定期ランクチェック処理を開始します...")
            from tasks import check_ranks_periodically_task_logic
            await check_ranks_periodically_task_logic(ctx.bot)
            await ctx.followup.send("定期ランクチェック処理が完了しました。")
        except Exception as e:
            await ctx.followup.send(f"処理中にエラーが発生しました: {e}")

    @bot.slash_command(name="debug_rank_all_iron", description="登録者全員のランクをIron IVに設定します。（デバッグ用）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def debug_rank_all_iron(ctx: discord.ApplicationContext) -> None:
        await ctx.defer(ephemeral=True)
        try:
            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            # 全ユーザーのランク情報を更新
            cur.execute("UPDATE users SET tier = 'IRON', rank = 'IV', league_points = 0")
            count: int = cur.rowcount
            con.commit()
            con.close()
            await ctx.respond(f"{count}人のユーザーのランクをIron IVに設定しました。")
        except Exception as e:
            await ctx.respond(f"処理中にエラーが発生しました: {e}")

    @bot.slash_command(name="debug_modify_rank", description="特定のユーザーのランクを強制的に変更します。（デバッグ用）", guild_ids=[DISCORD_GUILD_ID])
    @discord.default_permissions(administrator=True)
    async def debug_modify_rank(ctx: discord.ApplicationContext, user: discord.Member, tier: str, rank: str, league_points: int) -> None:
        await ctx.defer(ephemeral=True)
        TIERS: list[str] = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
        RANKS: list[str] = ["I", "II", "III", "IV"]

        if tier.upper() not in TIERS or rank.upper() not in RANKS:
            await ctx.respond(f"無効なTierまたはRankです。\nTier: {', '.join(TIERS)}\nRank: {', '.join(RANKS)}")
            return

        try:
            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            cur.execute("UPDATE users SET tier = ?, rank = ?, league_points = ? WHERE discord_id = ?",
                        (tier.upper(), rank.upper(), league_points, user.id))

            count: int = cur.rowcount
            con.commit()
            con.close()

            if count > 0:
                await ctx.respond(f"ユーザー「{user.display_name}」のランクを {tier.upper()} {rank.upper()} {league_points}LP に設定しました。")
            else:
                await ctx.respond(f"ユーザー「{user.display_name}」は見つかりませんでした。先に/registerで登録してください。")

        except Exception as e:
            await ctx.respond(f"処理中にエラーが発生しました: {e}")
