import telebot
from telebot import types

# Use your bot token here
TOKEN = "6579378143:AAG6EdQMWOYmA3cFbDwC9CcxqkGPxk1-dK0"
bot = telebot.TeleBot(TOKEN)


@bot.message_handler(content_types=["new_chat_members"])
def handle_new_member(message):
    new_member = message.new_chat_members[0]
    if new_member.is_bot and new_member.id == bot.get_me().id:
        chat_id = message.chat.id
        bot.send_message(chat_id, f"My Chat ID: {chat_id}")


if __name__ == "__main__":
    bot.polling(none_stop=True)
