import os
import json
import random
import asyncio
import re
from telegram import Update, ReplyKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
)

# === Configuration ===
TOKEN = "7509380154:AAHfwvG42bM6ErN7KBuaKj_xLWl355h5xoA"       # Replace with your bot token
ADMIN_ID = 6769245930               # Replace with your Telegram Admin ID
BALANCE_FILE = "balance.json"

# Referral bonus settings
REFERRAL_BONUS_NEW = 25         # Bonus for new user when referred
REFERRAL_BONUS_REFERRER = 50    # Bonus for the referrer

# === Persistent Storage Functions ===
def load_balances():
    if os.path.exists(BALANCE_FILE):
        try:
            with open(BALANCE_FILE, "r") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except json.JSONDecodeError:
            return {}
    else:
        return {}

def save_balances():
    data = {str(k): v for k, v in users.items()}
    with open(BALANCE_FILE, "w") as f:
        json.dump(data, f)

# Global users dictionary loaded from file.
users = load_balances()

# === Conversation States ===
BETTING = 0
WITHDRAW, UPI = range(1, 3)

# === File Paths for Images ===
TIGER_IMAGE_PATH = "tiger.png"
DRAGON_IMAGE_PATH = "dragon.png"
TIE_IMAGE_PATH = "tie.png"
UPI_QR_IMAGE_PATH = "qr.png"

# === Keyboards ===
main_keyboard = ReplyKeyboardMarkup([
    ["🐉 Dragon", "🐅 Tiger", "⚖️ Tie"],
    ["💰 Balance", "📋 Rules", "💸 Withdraw"],
    ["➕ Add Fund"],
    ["🔗 Refer & Earn"]
], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    ["➕ Add Balance", "➖ Remove Balance"],
    ["🐉 Dragon", "🐅 Tiger", "⚖️ Tie"],
    ["💰 Balance", "📋 Rules", "💸 Withdraw"],
    ["➕ Add Fund", "🔗 Refer & Earn"]
], resize_keyboard=True)

# === Basic Command Handlers ===

async def start(update: Update, context: CallbackContext) -> None:
    """
    /start command.
    Optionally accepts a referral code as an argument.
    If a new user starts with a valid referral code (which is the referrer's Telegram ID),
    both the new user and the referrer receive bonus funds.
    """
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {"balance": 100, "referred_by": None, "referrals": 0}
        if context.args:
            try:
                ref_code = int(context.args[0])
                if ref_code != user_id and ref_code in users:
                    users[user_id]["balance"] += REFERRAL_BONUS_NEW
                    users[user_id]["referred_by"] = ref_code
                    users[ref_code]["balance"] += REFERRAL_BONUS_REFERRER
                    users[ref_code]["referrals"] = users[ref_code].get("referrals", 0) + 1
                    await update.message.reply_text(
                        f"Referral successful! You received a bonus of ₹{REFERRAL_BONUS_NEW} and your referrer received ₹{REFERRAL_BONUS_REFERRER}."
                    )
                else:
                    await update.message.reply_text("Invalid referral code.")
            except ValueError:
                await update.message.reply_text("Invalid referral code format.")
        save_balances()
    keyboard = admin_keyboard if user_id == ADMIN_ID else main_keyboard
    await update.message.reply_text(
        f"Welcome to Dragon Tiger!\nYour balance: ₹{users[user_id]['balance']}\nYour referral code is: {user_id}",
        reply_markup=keyboard
    )

async def balance(update: Update, context: CallbackContext) -> None:
    """Display user's balance."""
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your balance: ₹{users[user_id]['balance']}")

async def rules(update: Update, context: CallbackContext) -> None:
    """Display game rules."""
    await update.message.reply_text(
        "📋 **Dragon Tiger Rules**:\n"
        "- Bet on 🐉 Dragon, 🐅 Tiger, or ⚖️ Tie.\n"
        "- Correct bet: 2x payout\n"
        "- Tie bet win: 8x payout\n"
        "- Minimum balance required to play."
    )

async def add_fund_info(update: Update, context: CallbackContext) -> None:
    """Send UPI details and a QR code image for adding funds."""
    message = (
        "💰 **To add funds, send payment to:**\n"
        "🏦 UPI ID: `example@upi`\n\n"
        "After payment, contact the admin for balance update."
    )
    await update.message.reply_text(message)
    with open(UPI_QR_IMAGE_PATH, "rb") as qr_img:
        await update.message.reply_photo(photo=InputFile(qr_img), caption="Scan this QR code to pay!")

async def refer_info(update: Update, context: CallbackContext) -> None:
    """Send referral information and referral link to the user."""
    user_id = update.effective_user.id
    # Create referral link using bot's username; make sure your bot username is set correctly.
    referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
    message = (
        f"🔗 **Refer & Earn**\n"
        f"Your referral code is: `{user_id}`\n"
        f"Share this link with your friends:\n{referral_link}\n\n"
        f"When a friend starts the bot using your link, you'll earn ₹{REFERRAL_BONUS_REFERRER} and they will earn ₹{REFERRAL_BONUS_NEW} bonus!"
    )
    await update.message.reply_text(message)

# === Conversation Flow for Betting ===

async def place_bet(update: Update, context: CallbackContext) -> int:
    """
    Triggered when the user clicks one of the bet buttons (🐉 Dragon, 🐅 Tiger, or ⚖️ Tie).
    """
    context.user_data["bet_choice"] = update.message.text
    await update.message.reply_text("Enter your bet amount:")
    return BETTING

async def process_bet(update: Update, context: CallbackContext) -> int:
    """Process the bet amount entered by the user."""
    user_id = update.effective_user.id
    if "bet_choice" not in context.user_data or \
       context.user_data["bet_choice"] not in ["🐉 Dragon", "🐅 Tiger", "⚖️ Tie"]:
        await update.message.reply_text("❌ You must choose a valid bet option before placing a bet.")
        return ConversationHandler.END

    try:
        bet_amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid amount! Please enter a number.")
        return ConversationHandler.END

    if bet_amount > users[user_id]["balance"]:
        await update.message.reply_text("Insufficient balance!")
        return ConversationHandler.END

    users[user_id]["balance"] -= bet_amount
    save_balances()
    await update.message.reply_text(
        f"✅ Bet placed on {context.user_data['bet_choice']}!\n⏳ Waiting for results... (60s)"
    )

    for remaining in range(50, -1, -10):
        await asyncio.sleep(10)
        await update.message.reply_text(f"⏳ {remaining} seconds remaining...")

    result = random.choice(["🐉 Dragon", "🐅 Tiger", "⚖️ Tie"])
    payout = 0
    if result == context.user_data["bet_choice"]:
        payout = bet_amount * (8 if result == "⚖️ Tie" else 2)
    users[user_id]["balance"] += payout
    save_balances()

    result_message = (
        f"🎲 **Result:** {result}\n"
        f"You {'won' if payout else 'lost'} ₹{payout or bet_amount}!\n"
        f"💰 **New Balance:** ₹{users[user_id]['balance']}"
    )
    await update.message.reply_text(result_message)

    image_path = {
        "🐅 Tiger": TIGER_IMAGE_PATH,
        "🐉 Dragon": DRAGON_IMAGE_PATH,
        "⚖️ Tie": TIE_IMAGE_PATH
    }.get(result)
    if image_path:
        with open(image_path, "rb") as img:
            await update.message.reply_photo(photo=InputFile(img), caption=f"{result} Wins!")
    return ConversationHandler.END

# === Conversation Flow for Withdrawal ===

async def withdraw(update: Update, context: CallbackContext) -> int:
    """Triggered when the user clicks the '💸 Withdraw' button."""
    await update.message.reply_text("Enter withdrawal amount:")
    return WITHDRAW

async def process_withdraw(update: Update, context: CallbackContext) -> int:
    """Collect withdrawal amount and prompt for UPI ID."""
    context.user_data["withdraw_amount"] = update.message.text
    await update.message.reply_text("Enter your UPI ID:")
    return UPI

async def process_upi(update: Update, context: CallbackContext) -> int:
    """Validate UPI ID, process withdrawal, and notify admin."""
    user_id = update.effective_user.id
    upi_id = update.message.text.strip()
    if not re.match(r'^[\w\.-]+@[a-zA-Z]+$', upi_id):
        await update.message.reply_text("Invalid UPI ID format! Please enter a valid UPI ID (e.g., example@upi).")
        return ConversationHandler.END
    try:
        amount = int(context.user_data["withdraw_amount"])
    except ValueError:
        await update.message.reply_text("Invalid amount! Please enter a number.")
        return ConversationHandler.END
    if amount > users[user_id]["balance"]:
        await update.message.reply_text("Insufficient balance!")
        return ConversationHandler.END
    users[user_id]["balance"] -= amount
    save_balances()
    await update.message.reply_text(f"✅ Withdrawal request sent: ₹{amount} to {upi_id}")
    admin_message = (
        f"📩 **New Withdrawal Request**\n"
        f"👤 User ID: `{user_id}`\n"
        f"💸 Amount: ₹{amount}\n"
        f"🏦 UPI ID: {upi_id}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    return ConversationHandler.END

# === Admin Commands ===

async def add_fund_command(update: Update, context: CallbackContext) -> None:
    """Admin command: /addfund <user_id> <amount>."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    try:
        user_id, amount = map(int, context.args)
        users.setdefault(user_id, {"balance": 100, "referred_by": None, "referrals": 0})
        users[user_id]["balance"] += amount
        save_balances()
        await update.message.reply_text(f"✅ Added ₹{amount} to user {user_id}.")
    except Exception:
        await update.message.reply_text("Usage: `/addfund <user_id> <amount>`")

async def remove_fund_command(update: Update, context: CallbackContext) -> None:
    """Admin command: /removefund <user_id> <amount>."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized!")
        return
    try:
        user_id, amount = map(int, context.args)
        if users.get(user_id, {}).get("balance", 0) >= amount:
            users[user_id]["balance"] -= amount
            save_balances()
            await update.message.reply_text(f"✅ Removed ₹{amount} from user {user_id}.")
        else:
            await update.message.reply_text("❌ Insufficient balance!")
    except Exception:
        await update.message.reply_text("Usage: `/removefund <user_id> <amount>`")

# === Main Function ===

def main():
    app = Application.builder().token(TOKEN).build()

    # Basic command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("addfund", add_fund_command))
    app.add_handler(CommandHandler("removefund", remove_fund_command))

    # Button handlers for static commands
    app.add_handler(MessageHandler(filters.Regex("^➕ Add Fund$"), add_fund_info))
    app.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance))
    app.add_handler(MessageHandler(filters.Regex("^📋 Rules$"), rules))
    app.add_handler(MessageHandler(filters.Regex("^🔗 Refer & Earn$"), refer_info))

    # Conversation handler for betting flow (private chats)
    bet_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🐉 Dragon|🐅 Tiger|⚖️ Tie)$") & filters.ChatType.PRIVATE, place_bet)],
        states={
            BETTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bet)]
        },
        fallbacks=[]
    )
    app.add_handler(bet_conv_handler)

    # Conversation handler for withdrawal flow (private chats)
    withdraw_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Withdraw$") & filters.ChatType.PRIVATE, withdraw)],
        states={
            WITHDRAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw)],
            UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_upi)]
        },
        fallbacks=[]
    )
    app.add_handler(withdraw_conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
