import json
import random
import asyncio
import nextcord

from enum import Enum

# PayPay Login Classes
class LoginModal(nextcord.ui.Modal):
    def __init__(self, paypay_class):
        super().__init__(
            title="ログイン",
            timeout=None
        )

        self.paypay_class = paypay_class

        self.phone_number = nextcord.ui.TextInput(
            label="電話番号",
            style=nextcord.TextInputStyle.short,
            min_length=11,
            max_length=11,
            required=True,
            placeholder="PayPayログイン時の電話番号"
        )
        self.add_item(self.phone_number)

        self.password = nextcord.ui.TextInput(
            label="パスワード",
            style=nextcord.TextInputStyle.short,
            max_length=16,
            required=True,
            placeholder="PayPayログイン時のパスワード"
        )
        self.add_item(self.password)

    async def callback(
        self,
        interaction: nextcord.Interaction
    ):
        coro = asyncio.to_thread(self.paypay_class.login_start, self.phone_number.value, self.password.value)

        status_message = await interaction.response.send_message("ログイン中...", ephemeral=True)
        
        try:
            await coro
        except:
            await status_message.edit("ログインに失敗しました")
            return
        
        await status_message.edit("OTP(二段階認証URL)を送信しました", view=LoginProcess(self.paypay_class, status_message))

class LoginProcess(nextcord.ui.View):
    def __init__(self, paypay_class, status_message_obj):
        super().__init__(
            timeout=None
        )

        self.paypay_class = paypay_class
        self.status_message_obj = status_message_obj

    @nextcord.ui.button(label="OTPを入力", style=nextcord.ButtonStyle.green)
    async def callback(
        self,
        button: nextcord.ui.Button,
        interaction: nextcord.Interaction
    ):
        await interaction.response.send_modal(LoginOTPModal(self.paypay_class, self.status_message_obj))

class LoginOTPModal(nextcord.ui.Modal):
    def __init__(self, paypay_class, status_message_obj):
        super().__init__(
            title="ログイン - OTP",
            timeout=None
        )

        self.paypay_class = paypay_class
        self.status_message_obj = status_message_obj

        self.otp = nextcord.ui.TextInput(
            label="OTPコード",
            style=nextcord.TextInputStyle.short,
            min_length=4,
            max_length=4,
            required=True,
            placeholder="4桁のワンタイムコード"
        )
        self.add_item(self.otp)

    async def callback(
        self,
        interaction: nextcord.Interaction
    ):
        coro = asyncio.to_thread(self.paypay_class.login_confirm, self.otp.value)

        await self.status_message_obj.edit("ログインを続行中...", view=None)
        status_message = await interaction.response.send_message("ログイン中...", ephemeral=True)

        try:
            token = await coro
            with open("cache.json", "w", encoding="utf-8", errors="ignore") as file:
                json.dump({"paypay_token": token}, file, indent=4)
        except:
            await status_message.edit("ログインに失敗しました")
            return

        await status_message.edit("ログインしました")

# Set StakeID Class
class StakeIDModal(nextcord.ui.Modal):
    def __init__(self, stake_class):
        super().__init__(
            title="StakeID 設定",
            timeout=None
        )

        self.stake_class = stake_class

        self.stake_id = nextcord.ui.TextInput(
            label="ID",
            style=nextcord.TextInputStyle.short,
            required=True,
            placeholder="StakeのID(間違えないように注意してください)"
        )
        self.add_item(self.stake_id)

    async def callback(
        self,
        interaction: nextcord.Interaction
    ):
        status_message = await interaction.response.send_message("設定中...", ephemeral=True)

        coro = asyncio.to_thread(self.stake_class.get_user_meta, self.stake_id.value)

        try:
            result = await coro
            if result["data"]["user"] == None:
                await status_message.edit("指定のStakeIDが見つかりませんでした")
                return
        except:
            await status_message.edit("StakeIDの検索に失敗しました")
            return
        
        with open("ids.json", "r", encoding="utf-8", errors="ignore") as file:
            ids = json.load(file)
        ids[str(interaction.user.id)] = self.stake_id
        with open("ids.json", "w", encoding="utf-8", errors="ignore") as file:
            json.dump(ids, file, indent=4)
        
        await status_message.edit("IDを設定しました")

# LTC Sell(販売) Classes
class SellButtons(nextcord.ui.View):
    def __init__(self, stake_class, cache):
        super().__init__(
            timeout=None
        )

        self.stake_class = stake_class
        self.cache = cache

    @nextcord.ui.button(label="換金", custom_id="sell_start", style=nextcord.ButtonStyle.green)
    async def sell_start(
        self,
        button: nextcord.ui.Button,
        interaction: nextcord.Interaction
    ):
        with open("data.json", "r", encoding="utf-8", errors="ignore") as file:
            data = json.load(file)
        stake_id = data.get(str(interaction.user.id))

        if stake_id == None:
            await interaction.response.send_message("StakeIDが設定されていません", ephemeral=True)
            return
        
        status_message = await interaction.response.send_message("チケットを作成中...", ephemeral=True)

        try:
            random_num = random.randint(1000, 9999)
            ticket_channel = await interaction.guild.create_text_channel(f"sell-{random_num}")
            ticket_channel.set_permissions(interaction.guild.default_role, nextcord.PermissionOverwrite(view_channel=False))
            ticket_channel.set_permissions(interaction.user, nextcord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True))
            self.cache.ticket_data[interaction.channel_id] = {
                "user": interaction.user.id,
                "stake": stake_id,
                "paypay_code": None,
                "paypay_amount": None,
                "phase": SellPhase.LOADING
            }
            await ticket_channel.send(f"StakeIDは「`{stake_id}`」に設定されています。\n本当によろしければ「続行」ボタンを押してください。\n\n**IDミスによる返金は致しかねます!**", view=SellConfirm(self.cache))
            await status_message.edit(f"チケットを作成しました: <#{ticket_channel.id}>")
        except:
            await status_message.edit("チケットの作成に失敗しました")

    @nextcord.ui.button(label="ID設定", custom_id="sell_setting_id", style=nextcord.ButtonStyle.gray)
    async def set_id(
        self,
        button: nextcord.ui.Button,
        interaction: nextcord.Interaction
    ):
        await interaction.response.send_modal(StakeIDModal(self.stake_class))

class SellConfirm(nextcord.ui.View):
    def __init__(self, cache):
        super().__init__(
            timeout=None
        )

        self.cache = cache

    @nextcord.ui.button(label="続行", style=nextcord.ButtonStyle.green)
    async def confirm(
        self,
        button: nextcord.ui.Button,
        interaction: nextcord.Interaction
    ):
        self.cache.ticket_data[interaction.channel_id]["phase"] = SellPhase.WAITING_PAYPAY
        await interaction.response.send_message("PayPayリンクを送信してください")

    @nextcord.ui.button(label="キャンセル", style=nextcord.ButtonStyle.gray)
    async def cancel(
        self,
        button: nextcord.ui.Button,
        interaction: nextcord.Interaction
    ):
        await interaction.channel.delete()

# Phase Enum Classes
class SellPhase(Enum):
    LOADING=0
    WAITING_PAYPAY=1
    WAITING_PAYPAY_PASSCODE=2

class BuyPhase(Enum):
    LOADING=0
    WAITING_LTC=1
    COMPLETE=2