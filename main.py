import discord
from discord.ext import commands
import logging

from dotenv import load_dotenv
import os

# 載入環境變數
load_dotenv(dotenv_path="/Users/qkauia/Desktop/Discord_Bot_RaspberryPi/.env")
token = os.getenv("DISCORD_TOKEN")

# 設置日誌文件處理器
handler = logging.FileHandler("discord.log", encoding="utf-8", mode="w")
# 初始化意向，設置成接收訊息和成員相關事件的意向
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 創建 Bot 實例
bot = commands.Bot(command_prefix="!", intents=intents)

secret_role = ["老師", "學員", "管理者", "班長", "副班長"]


# Bot 成功登入後的處理函數
@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user.name}")


# 成員加入伺服器時的處理函數
@bot.event
async def on_member_join(member):
    await member.send(f"歡迎來到 幼獅AioT!, {member.name}!")


# 不雅字眼處理
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # 忽略 Bot 自己發送的消息
    if "shit" in message.content.lower():
        await message.delete()  # 刪除包含 "shit" 的消息
        await message.channel.send(f"{message.author.mention} 禁止不雅字眼")
    await bot.process_commands(message)  # 處理其他命令


# 命令！請假 機器人回應
@bot.command()
async def 請假(ctx):
    await ctx.send("請記得線上請假")


# 分配角色命令
@bot.command()
async def 權限指定(ctx):
    roles = []
    for role_name in secret_role:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            roles.append(role)
    if roles:
        await ctx.author.add_roles(*roles)
        await ctx.send(f"{ctx.author.mention} 已被分配權限")
    else:
        await ctx.send("沒有找到可分配的角色")


@bot.command()
async def 權限移除(ctx):
    roles = []
    for role_name in secret_role:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            roles.append(role)
    if roles:
        await ctx.author.remove_roles(*roles)
        await ctx.send(f"{ctx.author.mention} 的權限已被移除")
    else:
        await ctx.send("沒有找到可移除的角色")


@bot.command()
@commands.has_any_role(*secret_role)
async def secret(ctx):
    await ctx.send("歡迎幼獅AioT！")


@secret.error
async def secret_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send(f"你是誰？你無權限")


bot.run(token, log_handler=handler, log_level=logging.DEBUG)
