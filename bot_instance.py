import telebot
import config
import random

# Single instance of the bot shared by everyone
bot = telebot.TeleBot(config.NOTIFIER_BOT_TOKEN)

# Unique ID for this bot instance (Build Trigger v2)
instance_id = random.randint(1000, 9999)
