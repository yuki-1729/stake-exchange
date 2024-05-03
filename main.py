import time
start_time = time.time()

import os
import json
import nextcord

from paypay import PayPay
from views import LoginModal
from dotenv import load_dotenv
from nextcord.ext import commands
from stake import Stake, StakeSocket

load_dotenv(verbose=True)
load_dotenv(".env")

bot = commands.Bot(help_command=None, intents=nextcord.Intents.all())

paypay = PayPay()
stake = Stake(os.getenv("STAKE_TOKEN"), os.getenv("STAKE_TFA"), os.getenv("STAKE_UA"), os.getenv("STAKE_CHUA"), os.getenv("STAKE_CLEARANCE"))
stake_socks = StakeSocket(os.getenv("STAKE_TOKEN"), os.getenv("STAKE_UA"), os.getenv("STAKE_CLEARANCE"))

if os.path.isfile("cache.json"):
    with open("cache.json", "r", encoding="utf-8", errors="ignore") as file:
        cache = json.load(file)
    
    paypay_token = cache["paypay_token"]

    paypay = PayPay(paypay_token)

@stake_socks.event()
async def on_data_received(data):
    return

@bot.event
async def on_ready():
    end_time = time.time()
    total_time = round(end_time - start_time, 2)

    print(f"Done ({total_time}s)")

@bot.slash_command(
    name="login",
    description="PayPayログインを実行します"
)
async def login_command(
    interaction: nextcord.Interaction
):
    if str(interaction.user.id) != os.getenv("OWNER"):
        await interaction.response.send_message("このコマンドを使用する権限がありません", ephemeral=True)
        return

    await interaction.response.send_modal(LoginModal(paypay))

bot.run(os.getenv("TOKEN"))