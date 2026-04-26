import telebot
import config
import random

# Single instance of the bot shared by everyone
bot = telebot.TeleBot(config.NOTIFIER_BOT_TOKEN)

# Track deployment instance
instance_id = f"{random.randint(1000, 9999)}"
