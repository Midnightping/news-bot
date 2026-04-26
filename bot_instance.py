import telebot
import config

# Single instance of the bot shared by everyone
bot = telebot.TeleBot(config.NOTIFIER_BOT_TOKEN)
