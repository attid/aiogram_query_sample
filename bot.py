import asyncio
from os import getenv
from collections import namedtuple
import logging
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties

# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("BOT_TOKEN")

# All handlers should be attached to the Router (or Dispatcher)
dp = Dispatcher()
my_queue = asyncio.Queue()
UserEmployeeIDs = namedtuple('UserEmployeeIDs', ['user_id', 'employee_id'])


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    await message.answer(f"Hello, {hbold(message.from_user.full_name)}!\nSend the employee's ID and get their details.")


@dp.message(F.text)
async def get_message_with_id(message: types.Message) -> None:
    if message.text.isdigit():
        my_queue.put_nowait(UserEmployeeIDs(user_id=message.from_user.id, employee_id=int(message.text)))
    else:
        await message.answer("Send the employee's ID and get their details.")


async def on_startup(bot: Bot):
    dp['task_list'] = [asyncio.create_task(queue_worker(bot=bot)),
                       ]


async def on_shutdown(bot: Bot):
    for task in dp['task_list']:
        task.cancel()


async def queue_worker(bot: Bot):
    while True:  # not queue.empty():
        queue_item: UserEmployeeIDs = await my_queue.get()

        try:
            url = f"https://json.activelava.net/users/{queue_item.employee_id}"

            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()

                name = data.get("name")
                email = data.get("email")

                await bot.send_message(chat_id=queue_item.user_id, text=f"Name: {name}\nEmail: {email}")
            else:
                await bot.send_message(chat_id=queue_item.user_id,
                                       text=f"Failed to fetch data for user with ID {queue_item.employee_id}. "
                                            f"Status code: {response.status_code}")
        except Exception as e:
            # Here we log errors. There shouldn't be any errors in the stream; otherwise, it will freeze.
            logging.error(f'{e}')
        my_queue.task_done()


async def main() -> None:
    # Initialize Bot instance with a default parse mode which will be passed to all API calls
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # And the run events dispatching
    dp['task_list'] = []
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
