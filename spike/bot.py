import logging
from pathlib import Path
from typing import Any, Dict, List

from telegram import Update, Message, PhotoSize
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    PicklePersistence,
    Updater,
)

from spike.yadisk import YaDisk, PathExistsError


def get_largest_size(sizes: List[PhotoSize]) -> PhotoSize:
    def get_size(size: PhotoSize) -> int:
        return size.width * size.height

    return max(sizes, key=get_size)


ID_SIZE = 10


class Spike:
    def __init__(self, config: Dict[Any, Any]) -> None:
        self.disk = YaDisk(config["yadisk"])
        self.workdir = Path(config["workdir"])
        self.workdir.mkdir(exist_ok=True)
        self.updater = Updater(
            token=config["telegram_token"],
            use_context=True,
            persistence=PicklePersistence(filename=self.workdir / config["database"]),
        )
        dispatcher = self.updater.dispatcher
        dispatcher.add_handler(MessageHandler(Filters.all, self._log_message), group=0)
        dispatcher.add_handler(MessageHandler(Filters.photo, self._save_from_photo), group=1)
        dispatcher.add_handler(CommandHandler("map", self._map), group=1)
        dispatcher.add_handler(CommandHandler("save", self._save_from_reply), group=1)

    def run(self) -> None:
        self.updater.start_polling()

    def _save_photo_for_tag(self, update: Update, context: CallbackContext, src_message: Message, tag: str) -> None:
        chat_data = context.chat_data
        if tag not in chat_data:
            src_message.reply_markdown_v2(f"Unknown tag: `{tag}`")
            return

        category = context.chat_data[tag]
        photo = get_largest_size(src_message.photo)
        filename = (
            str(src_message.message_id).zfill(ID_SIZE) + ".jpg"
        )
        local_path = self.workdir / filename
        logging.info(f"Downloading to '{local_path}'")
        photo.get_file().download(str(local_path))
        yadisk_path = f"{category}/{filename}"

        with local_path.open("rb") as f:
            try:
                public_url = self.disk.save_file(f, yadisk_path)
            except PathExistsError:
                logging.error(f"File already exists: '{yadisk_path}'")
                update.message.reply_markdown_v2(
                    f"Could not save becase file already exists: `{yadisk_path}`"
                )
                return
            finally:
                logging.info(f"Deleting '{local_path}'")
                local_path.unlink()

        logging.info("Done")
        update.message.reply_to_message
        if public_url is None:
            update.message.reply_markdown_v2(f"Saved to `{yadisk_path}`")
        else:
            update.message.reply_markdown_v2(f"[Saved]({public_url})", disable_web_page_preview=True)

    def _log_message(self, update: Update, context: CallbackContext) -> None:
        logging.info("Got update:")
        logging.info(update)
        logging.info("Args:")
        logging.info(args := context.args)

    def _map(self, update: Update, context: CallbackContext) -> None:
        args = context.args

        if len(args) < 2:
            update.message.reply_markdown_v2("Usage: `/map TAG DIRECTORY_NAME`")
            return

        tag = args[0]
        directory_name = " ".join(args[1:])
        context.chat_data[tag] = directory_name
        update.message.reply_markdown_v2(f"Mapped `{tag}` to `{directory_name}`")

    def _save_from_photo(self, update: Update, context: CallbackContext) -> None:
        if update.message.caption is None:
            return

        parts = update.message.caption.split()
        if "/save" not in parts:
            return

        if len(parts) != 2 or parts[0] != "/save":
            update.message.reply_markdown_v2("Usage: `/save TAG`")
            return
        
        tag = parts[1]
        self._save_photo_for_tag(update, context, update.message, tag)

    def _save_from_reply(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        if len(message.photo) > 0:
            src_message = message
        elif message.reply_to_message is not None and len(message.reply_to_message.photo) > 0:
            src_message = message.reply_to_message
        else:
            message.reply_markdown_v2("You must reply to a message with a photo to save it")
            return

        args = context.args

        if len(args) != 1:
            message.reply_markdown_v2("You must provide exactly one tag")
            return

        tag = args[0]
        self._save_photo_for_tag(update, context, src_message, tag)


