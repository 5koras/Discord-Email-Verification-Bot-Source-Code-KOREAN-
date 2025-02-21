import discord
import random
import json
import smtplib
from email.mime.text import MIMEText
from discord.ext import commands
from discord.ui import Modal, TextInput, View
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
ALLOWED_MAIL = os.getenv("ALLOWED_MAIL").split(", ")
MAIL = os.getenv("MAIL")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
SERVER_ID = os.getenv("SERVER_ID")
ROLE_ID = os.getenv("ROLE_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def load_users():
    try:
        with open("user.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data:
                data["users"] = []
            return data
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {"users": []}

def save_users(data):
    with open("user.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def send_email(email, code):
    msg = MIMEText(f"인증번호: {code}")
    msg["Subject"] = "디스코드 인증번호"
    msg["From"] = MAIL
    msg["To"] = email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(MAIL, MAIL_PASSWORD)
        server.sendmail(MAIL, email, msg.as_string())

class EmailInputModal(Modal, title="이메일 입력"):
    email = TextInput(label="이메일", placeholder="example@gmail.com")

    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        email = self.email.value.strip()
        if not any(email.endswith(f"@{domain}") for domain in ALLOWED_MAIL):
            await interaction.followup.send("❌ 허용된 이메일 도메인이 아닙니다!", ephemeral=True)
            return

        users = load_users()
        for user in users["users"]:
            if user["email"] == email:
                await interaction.followup.send("❌ 이미 인증된 이메일입니다!", ephemeral=True)
                return

        code = "".join(random.choices("0123456789", k=6))
        send_email(email, code)

        date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        users["users"].append({
            "username": interaction.user.name,
            "id": str(interaction.user.id),
            "email": email,
            "code": code,
            "date": date_now
        })
        save_users(users)

        embed = discord.Embed(
            title="인증번호 전송!",
            description="입력하신 이메일로 인증번호가 발송되었습니다.\n인증번호를 확인하고 !인증확인 [ 인증번호 ] 라고 입력해주세요.",
            color=0x00FF00
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class EmailVerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.green)
    async def email_verification_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmailInputModal(interaction))

    async def give_role(self, user: discord.Member, guild: discord.Guild):
        role = discord.utils.get(guild.roles, id=int(ROLE_ID))
        if role:
            try:
                await user.add_roles(role)
                await user.send("✅ 인증이 완료되어 역할이 지급되었습니다!")
            except discord.Forbidden:
                await user.send("❌ 역할 지급에 실패했습니다. 관리자에게 문의하세요.")

@bot.command()
@commands.has_permissions(administrator=True)
async def 인증(ctx):
    embed = discord.Embed(
        title="이메일 인증",
        description="아래 버튼을 눌러 이메일 인증을 진행하세요!",
        color=0x00FF00
    )
    view = EmailVerificationView()
    await ctx.send(embed=embed, view=view)

@bot.command()
async def 인증확인(ctx, code: str):
    users = load_users()
    for user in users["users"]:
        if user["id"] == str(ctx.author.id) and user["code"] == code:
            users["users"].remove(user)
            save_users(users)

            embed = discord.Embed(title="✅ 인증 성공!", description="이메일 인증이 완료되었습니다!", color=0x00FF00)
            await ctx.send(embed=embed)

            guild = bot.get_guild(int(SERVER_ID))
            if guild:
                member = guild.get_member(ctx.author.id)
                if member:
                    role = discord.utils.get(guild.roles, id=int(ROLE_ID))
                    if role:
                        try:
                            await member.add_roles(role)
                            embed_role = discord.Embed(
                                title="✅ 역할 지급 완료!",
                                description=f"{member.mention}님께 역할이 지급되었습니다!",
                                color=0x00FF00
                            )
                            await ctx.send(embed=embed_role)
                        except discord.Forbidden:
                            embed_fail = discord.Embed(
                                title="❌ 역할 지급 실패!",
                                description="역할 지급에 실패했습니다. 관리자에게 문의하세요.",
                                color=0xFF0000
                            )
                            await ctx.send(embed=embed_fail)
            return

    embed = discord.Embed(title="❌ 인증 실패!", description="올바른 인증번호를 입력해주세요.", color=0xFF0000)
    await ctx.send(embed=embed)

bot.run(TOKEN)
