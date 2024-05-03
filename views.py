import json
import asyncio
import nextcord

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