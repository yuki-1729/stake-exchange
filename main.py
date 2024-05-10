import time
start_time = time.time()

import os
import json
import asyncio
import nextcord

from paypay import PayPay
from dotenv import load_dotenv
from nextcord.ext import commands
from stake import Stake, StakeSocket
from views import LoginModal, SellButtons, BuyButtons, SellPhase, BuyPhase

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

class Cache:
    def __init__(self):
        self.ticket_data = {}
        self.buy_data = {}
cache = Cache()

@stake_socks.event()
async def on_data_received(data):
    base = data["notifications"]["data"]

    currency = base["currency"]
    amount = base["amount"]
    created = base["sendBy"]

    if cache.buy_data.get(created) == None:
        return
    
    guild = bot.get_guild(cache.buy_data[created]["guild"])
    if guild == None:
        return
    
    ticket_channel = guild.get_channel(cache.buy_data[created]["channel"])
    if ticket_channel == None:
        return
    
    if currency != "ltc":
        await ticket_channel.send("送信された通貨はLTCではないようです。")
        return

    cache.ticket_data[ticket_channel.id]["phase"] = BuyPhase.LOADING
    await ticket_channel.send(f"Stakeで{amount}LTC受け取りました。\n処理を開始しますのでお待ちください。")

    ltc_rate = None

    coro = asyncio.to_thread(stake.get_currency_rate)
    rate = await coro
    for currency_data in rate["data"]["info"]["currencies"]:
        if currency_data["name"] == "ltc":
            ltc_rate = currency_data["jpy"]

    send_amount = ((int(os.getenv("BUY_RATE")) / 100) * amount) * ltc_rate

    coro = asyncio.to_thread(paypay.create_link(send_amount, "1234"))
    result = await coro 

    link = result["payload"]["link"]

    await ticket_channel.send(f"換金が完了しました。\n\n**リンク:** {link}\n**パスコード:** 1234\n\n**このリンクをこのままLTC販売へ渡さないでください！**")
    return

@bot.event
async def on_ready():
    bot.add_view(SellButtons(stake, cache))
    bot.add_view(BuyButtons(stake, cache))

    end_time = time.time()
    total_time = round(end_time - start_time, 2)

    print(f"Done ({total_time}s)")

@bot.event
async def on_message(message):
    ticket_data = cache.ticket_data.get(message.channel.id)
    if ticket_data == None:
        return
    elif ticket_data["phase"] == SellPhase.LOADING:
        return
    elif ticket_data["phase"] == BuyPhase.LOADING or ticket_data == BuyPhase.WAITING_LTC:
        return
    
    # Sell(販売) IF Statement
    if ticket_data["phase"] == SellPhase.WAITING_PAYPAY:
        cache.ticket_data[message.channel.id]["phase"] = SellPhase.LOADING

        await message.channel.send("受け取り中...")

        coro = asyncio.to_thread(paypay.get_link, message.content.replace("https://pay.paypay.ne.jp/", ""))

        try:
            result = await coro
            cache.ticket_data[message.channel.id]["paypay_link"] = message.content.replace("https://pay.paypay.ne.jp/", "")
            cache.ticket_data[message.channel.id]["paypay_amount"] = result["payload"]["amount"]
            if result["payload"]["pendingP2PInfo"]["isSetPasscode"]:
                cache.ticket_data[message.channel.id]["phase"] = SellPhase.WAITING_PAYPAY_PASSCODE
                await message.channel.send("パスコードを送信してください")
        except:
            await message.channel.send("処理中にエラーが発生しました")
    elif ticket_data["phase"] == SellPhase.WAITING_PAYPAY_PASSCODE:
        cache.ticket_data[message.channel.id]["phase"] = SellPhase.LOADING

        await message.channel.send("受け取り中...")

        code = cache.ticket_data[message.channel.id]["paypay"]
        passcode = message.content
        coro = asyncio.to_thread(paypay.accept_link, code, passcode)

        try:
            await coro
        except:
            await message.channel.send("処理中にエラーが発生しました")
            return
        await message.channel.send("送金中...")

        ltc_rate = None

        coro = asyncio.to_thread(stake.get_currency_rate)
        rate = await coro
        for currency_data in rate["data"]["info"]["currencies"]:
            if currency_data["name"] == "ltc":
                ltc_rate = currency_data["jpy"]

        send_amount = ((int(os.getenv("SELL_RATE")) / 100) * cache.ticket_data[message.channel.id]["paypay_amount"]) / ltc_rate

        coro = asyncio.to_thread(stake.send_tip(ticket_data["stake"], "ltc", send_amount))

        try:
            await coro
            await message.channel.send("送金完了")
        except:
            await message.channel.send("処理中にエラーが発生しました")
            return
        
        await message.channel.send("換金が完了しました")



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

@bot.slash_command(
    name="panel",
    description="買取または販売のパネルを設置します"
)
async def panel_command(
    interaction: nextcord.Interaction
):
    pass

@panel_command.subcommand(
    name="sell",
    description="販売パネルを設置します"
)
async def panel_sub_sell_command(
    interaction: nextcord.Interaction
):
    if str(interaction.user.id) != os.getenv("OWNER"):
        await interaction.response.send_message("このコマンドを使用する権限がありません", ephemeral=True)
        return
    
    sell_rate = os.getenv("SELL_RATE")
    await interaction.channel.send(f"**=== LTC販売(換金率: {sell_rate}%) ===**", view=SellButtons(stake, cache))

    await interaction.response.send_message("販売パネルを設置しました", ephemeral=True)

bot.run(os.getenv("TOKEN"))