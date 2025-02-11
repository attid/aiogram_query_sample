import asyncio
from os import getenv
from collections import namedtuple
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties

# Constants
TOKEN = getenv("BOT_TOKEN")
API_URL = "https://reqres.in/api/users"

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Named tuple for queue items
UserEmployeeIDs = namedtuple('UserEmployeeIDs', ['user_id', 'employee_id'])

# Initialize dispatcher and queue
dp = Dispatcher()
my_queue = asyncio.Queue()

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command.
    It greets the user and provides instructions.
    """
    await message.answer(f"Hello, {hbold(message.from_user.full_name)}!\n"
                         "Send the employee's ID and get their details.")

@dp.message(Command("all"))
async def get_all_users(message: types.Message) -> None:
    """
    This handler fetches all available user IDs from the Reqres API
    and sends them to the user as a comma-separated list.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    users = data.get("data", [])
                    available_ids = [str(user["id"]) for user in users]
                    await message.answer(f"Available IDs: {', '.join(available_ids)}")
                else:
                    await message.answer("Failed to fetch user data. Please try again later.")
    except Exception as e:
        logging.error(f"Error fetching all users: {e}")
        await message.answer("An error occurred while fetching user data. Please try again later.")

@dp.message(F.text)
async def get_message_with_id(message: types.Message) -> None:
    """
    This handler processes text messages.
    If the message contains a valid numeric ID, it adds the ID to the queue.
    Otherwise, it prompts the user to send a valid ID.
    """
    if message.text.isdigit():
        await my_queue.put(UserEmployeeIDs(user_id=message.from_user.id, employee_id=int(message.text)))
    else:
        await message.answer("Please send a valid employee ID.")

async def on_startup(bot: Bot):
    """
    This function is called when the bot starts.
    It initializes background tasks, such as the queue worker.
    """
    dp['task_list'] = [asyncio.create_task(queue_worker(bot=bot))]

async def on_shutdown(bot: Bot):
    """
    This function is called when the bot shuts down.
    It cancels all background tasks to ensure graceful termination.
    """
    for task in dp['task_list']:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logging.info("Task cancelled successfully.")

async def queue_worker(bot: Bot):
    """
    This function continuously processes items from the queue.
    It fetches user details from the Reqres API and sends them to the user.
    """
    while True:  # Infinite loop for processing the queue
        queue_item: UserEmployeeIDs = await my_queue.get()
        try:
            # Forming URL for Reqres API request
            url = f"{API_URL}/{queue_item.employee_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        user_data = data.get("data", {})
                        if not user_data:
                            await bot.send_message(
                                chat_id=queue_item.user_id,
                                text="User not found. Try /all to see available IDs."
                            )
                            continue

                        # Extracting user details
                        first_name = user_data.get("first_name")
                        last_name = user_data.get("last_name")
                        email = user_data.get("email")
                        avatar_url = user_data.get("avatar")

                        # Preparing the message
                        message_text = f"Name: {first_name} {last_name}\nEmail: {email}"

                        # Sending photo if available
                        if avatar_url:
                            await bot.send_photo(
                                chat_id=queue_item.user_id,
                                photo=avatar_url,
                                caption=message_text
                            )
                        else:
                            await bot.send_message(
                                chat_id=queue_item.user_id,
                                text=message_text
                            )
                    else:
                        # Handle non-200 status codes
                        await bot.send_message(
                            chat_id=queue_item.user_id,
                            text=f"Failed to fetch data for user with ID {queue_item.employee_id}.\n"
                                 f"Status code: {response.status}\n"
                                 f"Try /all to see available IDs."
                        )
        except Exception as e:
            # Log errors with context
            logging.error(f"Error processing queue item (user_id={queue_item.user_id}, "
                          f"employee_id={queue_item.employee_id}): {e}")
        finally:
            # Mark the task as done
            my_queue.task_done()

async def main() -> None:
    """
    The main entry point of the bot.
    Initializes the bot instance and starts polling.
    """
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
