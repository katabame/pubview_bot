import sqlite3
from typing import Any
import discord
from riotwatcher import ApiError
from config import DB_PATH, RANK_ROLES, HONOR_CHANNEL_ID, riot_watcher, my_region_for_account
from rank_helpers import get_rank_by_puuid


# --- UIコンポーネント (View) ---
class DashboardView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="名誉を贈る", style=discord.ButtonStyle.primary, custom_id="dashboard:give_honor")
    async def give_honor_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(GiveHonorModal())

    @discord.ui.button(label="Riot IDの登録", style=discord.ButtonStyle.success, custom_id="dashboard:register")
    async def register_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(RegisterModal())

    @discord.ui.button(label="Riot IDの登録解除", style=discord.ButtonStyle.danger, custom_id="dashboard:unregister")
    async def unregister_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            cur.execute("DELETE FROM users WHERE discord_id = ?", (interaction.user.id,))
            con.commit()

            if con.total_changes > 0:
                await interaction.followup.send("あなたの登録情報を削除しました。", ephemeral=True, delete_after=30.0)
                # ランク連動ロール削除処理
                guild: discord.Guild | None = interaction.guild
                if guild:
                    member: discord.Member | None = await guild.fetch_member(interaction.user.id)
                    if member:
                        role_names_to_remove: list[discord.Role | None] = [discord.utils.get(guild.roles, name=role_name) for role_name in RANK_ROLES.values()]
                        await member.remove_roles(*[role for role in role_names_to_remove if role is not None and role in member.roles])
            else:
                await interaction.followup.send("あなたはまだ登録されていません。", ephemeral=True, delete_after=30.0)

            con.close()
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'unregister_button': {e}")
            await interaction.followup.send("登録解除中に予期せぬエラーが発生しました。", ephemeral=True, delete_after=30.0)

    @discord.ui.button(label="セクションに参加", style=discord.ButtonStyle.primary, custom_id="dashboard:join_section")
    async def get_section_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        guild: discord.Guild | None = interaction.guild
        if not guild:
            return
        con: sqlite3.Connection = sqlite3.connect(DB_PATH)
        cur: sqlite3.Cursor = con.cursor()
        cur.execute("SELECT role_id, section_name FROM sections")
        all_sections: list[tuple[int, str]] = cur.fetchall()
        con.close()

        available_sections: list[tuple[int, str]] = []
        for role_id, section_name in all_sections:
            role: discord.Role | None = guild.get_role(role_id)
            if role and len(role.members) < 35:
                available_sections.append((role_id, section_name))

        if not available_sections:
            await interaction.response.send_message("現在参加可能なセクションはありません。", ephemeral=True, delete_after=60)
            return

        await interaction.response.send_message(content="参加したいセクションを選択してください。", view=SectionSelectView(available_sections), ephemeral=True, delete_after=180)

    @discord.ui.button(label="セクションから退出", style=discord.ButtonStyle.secondary, custom_id="dashboard:leave_section", disabled=False)
    async def remove_section_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        member: discord.Member | discord.User = interaction.user
        if not isinstance(member, discord.Member):
            return
        con: sqlite3.Connection = sqlite3.connect(DB_PATH)
        cur: sqlite3.Cursor = con.cursor()
        cur.execute("SELECT role_id FROM sections")
        managed_role_ids: set[int] = {row[0] for row in cur.fetchall()}
        con.close()

        user_managed_roles: list[discord.Role] = [role for role in member.roles if role.id in managed_role_ids]

        if not user_managed_roles:
            await interaction.response.send_message("退出可能なセクションがありません。", ephemeral=True, delete_after=60)
            return

        await interaction.response.send_message(
            content="退出したいセクションを選択してください。",
            view=RemoveSectionView(user_managed_roles),
            ephemeral=True,
            delete_after=180
        )


class GiveHonorModal(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="名誉を贈る")
        self.add_item(discord.ui.InputText(label="名誉を贈りたいユーザー", required=True))
        self.add_item(discord.ui.InputText(label="名誉を贈りたい理由", required=True))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel: discord.TextChannel | discord.VoiceChannel | discord.Thread | None = interaction.client.get_channel(HONOR_CHANNEL_ID)
        if not channel:
            return
        embed: discord.Embed = discord.Embed(title=f"名誉投票が行われました", color=discord.Color.gold())
        embed.description = f"{interaction.user.mention}が名誉を贈りました"
        embed.add_field(name="名誉を贈りたいユーザー", value=self.children[0].value, inline=False)
        embed.add_field(name="名誉を贈りたい理由", value=self.children[1].value, inline=False)
        await channel.send(embed=embed)
        await interaction.followup.send(f"「{self.children[0].value}」に名誉を贈りました！", ephemeral=True, delete_after=30.0)


class RegisterModal(discord.ui.Modal):
    def __init__(self) -> None:
        super().__init__(title="Riot ID 登録")
        self.add_item(discord.ui.InputText(label="Riot ID (例: TaroYamada)", required=True))
        self.add_item(discord.ui.InputText(label="Tagline (例: JP1) ※#は不要", required=True))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        game_name: str = self.children[0].value
        tag_line: str = self.children[1].value

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
                            (interaction.user.id, puuid, game_name, tag_line, rank_info['tier'], rank_info['rank'], rank_info['leaguePoints']))
            else:
                cur.execute("INSERT OR REPLACE INTO users (discord_id, riot_puuid, game_name, tag_line, tier, rank, league_points) VALUES (?, ?, ?, ?, NULL, NULL, NULL)",
                            (interaction.user.id, puuid, game_name, tag_line))
            con.commit()
            con.close()
            await interaction.followup.send(f"Riot ID「{game_name}#{tag_line}」を登録しました！", ephemeral=True, delete_after=30.0)
        except ApiError as err:
            if err.response.status_code == 404:
                await interaction.followup.send(f"Riot ID「{game_name}#{tag_line}」が見つかりませんでした。", ephemeral=True, delete_after=30.0)
            else:
                await interaction.followup.send("Riot APIでエラーが発生しました。", ephemeral=True, delete_after=30.0)
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'RegisterModal' callback: {e}")
            await interaction.followup.send("登録中に予期せぬエラーが発生しました。", ephemeral=True, delete_after=30.0)


class SectionSelectView(discord.ui.View):
    def __init__(self, available_sections: list[tuple[int, str]]) -> None:
        super().__init__(timeout=180)
        self.add_item(SectionSelect(available_sections))


class SectionSelect(discord.ui.Select):
    def __init__(self, available_sections: list[tuple[int, str]]) -> None:
        options: list[discord.SelectOption] = [
            discord.SelectOption(label=section_name, value=str(role_id)) for role_id, section_name in available_sections
        ]
        if not options:
            options.append(discord.SelectOption(label="参加可能なセクションがありません", value="no_sections", default=True))

        super().__init__(placeholder="参加したいセクションを選択してください", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == "no_sections":
            await interaction.response.edit_message(content="現在参加できるセクションはありません。", view=None)
            return

        role_id: int = int(self.values[0])
        guild: discord.Guild | None = interaction.guild
        if not guild:
            return
        section_role: discord.Role | None = guild.get_role(role_id)

        if not section_role:
            await interaction.response.edit_message(content="指定されたセクション（ロール）が見つかりませんでした。", view=None)
            return

        member: discord.Member = await guild.fetch_member(interaction.user.id)
        if section_role in member.roles:
            await interaction.response.edit_message(content=f"あなたは既にセクション「{section_role.name}」に参加しています。", view=None)
            return

        try:
            await member.add_roles(section_role)

            con: sqlite3.Connection = sqlite3.connect(DB_PATH)
            cur: sqlite3.Cursor = con.cursor()
            cur.execute("SELECT notification_channel_id FROM sections WHERE role_id = ?", (role_id,))
            result: tuple[int] | None = cur.fetchone()
            con.close()

            if result:
                channel_id: int = result[0]
                channel: discord.TextChannel | discord.VoiceChannel | discord.Thread | None = interaction.client.get_channel(channel_id)
                if channel:
                    await channel.send(f"{member.mention}さんがセクション「{section_role.name}」に参加しました！")

            await interaction.response.edit_message(content=f"セクション「{section_role.name}」に参加しました！", view=None)
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'SectionSelect' callback: {e}")
            await interaction.response.edit_message(content="セクションへの参加中にエラーが発生しました。", view=None)


class RemoveSectionView(discord.ui.View):
    def __init__(self, user_roles: list[discord.Role]):
        super().__init__(timeout=180)
        self.add_item(RemoveSectionSelect(user_roles))


class RemoveSectionSelect(discord.ui.Select):
    def __init__(self, user_roles: list[discord.Role]) -> None:
        options: list[discord.SelectOption] = [
            discord.SelectOption(label=role.name, value=str(role.id)) for role in user_roles
        ]
        super().__init__(placeholder="退出したいセクションを選択してください", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        member: discord.Member | discord.User = interaction.user
        if not isinstance(member, discord.Member):
            return
        role_id: int = int(self.values[0])
        role_to_remove: discord.Role | None = interaction.guild.get_role(role_id) if interaction.guild else None

        if not role_to_remove or role_to_remove not in member.roles:
            await interaction.response.edit_message(content="エラー: 対象のセクション（ロール）が見つからないか、参加していません。", view=None)
            return

        try:
            await member.remove_roles(role_to_remove)
            await interaction.response.edit_message(content=f"セクション「{role_to_remove.name}」から退出しました。", view=None)
        except Exception as e:
            print(f"!!! An unexpected error occurred in 'RemoveSectionSelect' callback: {e}")
            await interaction.response.edit_message(content="セクションからの退出中にエラーが発生しました。", view=None)
