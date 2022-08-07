import argparse
import json
import logging
from os import wait
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Set, Union

from telegram import File, Update, Message, PhotoSize
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    PicklePersistence,
    Updater,
)
import yadisk


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


ID_SIZE = 10


AnyPath = Union[str, Path]


class YaDisk:
    def __init__(self, config: Dict[Any, Any]) -> None:
        self.api = yadisk.YaDisk(token=config["token"])
        self.root_dir = Path(config["root_dir"])
        self.public_url = config.get("public_url")

    def save_file(self, file: BinaryIO, path: str) -> Optional[str]:
        dst_path = self.root_dir / path
        self._mkdir_if_not_exists(dst_path.parent)
        logging.info(f"Uploading to '{path}'")
        self.api.upload(path_or_file=file, dst_path=dst_path)

        if self.public_url is None:
            return

        return f"{self.public_url}/{path}"

    def _mkdir_if_not_exists(self, dir: AnyPath) -> None:
        if not self.api.exists(str(dir)):
            self.api.mkdir(str(dir))


def get_largest_size(sizes: List[PhotoSize]) -> PhotoSize:
    def get_size(size: PhotoSize) -> int:
        return size.width * size.height

    return max(sizes, key=get_size)


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
            str(src_message.chat_id) + "_" +
            str(src_message.message_id).zfill(ID_SIZE) + ".jpg"
        )
        local_path = self.workdir / filename
        logging.info(f"Downloading to '{local_path}'")
        photo.get_file().download(str(local_path))
        yadisk_path = f"{category}/{filename}"

        with local_path.open("rb") as f:
            try:
                public_url = self.disk.save_file(f, yadisk_path)
            except yadisk.exceptions.PathExistsError:
                logging.error(f"File already exists: '{yadisk_path}'")
                update.message.reply_markdown_v2(
                    f"Could not save becase file already exists: `{yadisk_path}`"
                )
                return
            finally:
                logging.info(f"Deleting '{local_path}'")
                local_path.unlink()

        logging.info("Done")
        if public_url is None:
            update.message.reply_markdown_v2(f"Saved to `{yadisk_path}`")
        else:
            update.message.reply_markdown_v2(f"[Saved]({public_url})", disable_web_page_preview=True)

    def _add_message_to_media_group(self, context: CallbackContext, media_group_id: str, message: Message) -> None:
        if "files_by_media_group_id" not in context.chat_data:
            context.chat_data["files_by_media_group_id"] = dict()
        media_group_files = context.chat_data["files_by_media_group_id"]
        if media_group_id not in media_group_files:
            media_group_files[media_group_id] = []
        media_group_files[media_group_id].append(message)

    def _get_media_group_messages(self, context: CallbackContext, media_group_id: str) -> List[Message]:
        if "files_by_media_group_id" not in context.chat_data:
            context.chat_data["files_by_media_group_id"] = dict()
        media_group_files = context.chat_data["files_by_media_group_id"]
        if media_group_id not in media_group_files:
            media_group_files[media_group_id] = []
        return media_group_files[media_group_id]

    def _add_tag_to_media_group(self, context: CallbackContext, media_group_id: str, tag: str) -> None:
        if "tags_by_media_group_id" not in context.chat_data:
            context.chat_data["tags_by_media_group_id"] = dict()
        tags_by_media_group_id = context.chat_data["tags_by_media_group_id"]
        if media_group_id not in tags_by_media_group_id:
            tags_by_media_group_id[media_group_id] = set()
        tags_by_media_group_id[media_group_id].add(tag)

    def _get_media_group_tags(self, context: CallbackContext, media_group_id: str) -> Set[str]:
        if "tags_by_media_group_id" not in context.chat_data:
            context.chat_data["tags_by_media_group_id"] = dict()
        tags_by_media_group_id = context.chat_data["tags_by_media_group_id"]
        if media_group_id not in tags_by_media_group_id:
            tags_by_media_group_id[media_group_id] = set()
        return tags_by_media_group_id[media_group_id]
    
    def _log_message(self, update: Update, context: CallbackContext) -> None:
        logging.info("Got update:")
        logging.info(update)
        logging.info("Args:")
        logging.info(args := context.args)

        if (media_group_id := update.message.media_group_id) is not None and update.message.photo:
            self._add_message_to_media_group(context, media_group_id, update.message)

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
        if (media_group_id := update.message.media_group_id) is not None and (tags := self._get_media_group_tags(context, media_group_id)):
            for tag in tags:
                self._save_photo_for_tag(update, context, update.message, tag)
            return

        if update.message.caption is None:
            return

        parts = update.message.caption.split()
        if "/save" not in parts:
            return

        if len(parts) != 2 or parts[0] != "/save":
            update.message.reply_markdown_v2("Usage: `/save TAG`")
            return
        
        tag = parts[1]
        if update.message.media_group_id is not None:
            self._add_tag_to_media_group(context, update.message.media_group_id, tag)
            self._save_photo_for_tag(update, context, update.message, tag)
        else:
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

        if (media_group_id := src_message.media_group_id) is not None:
            self._add_tag_to_media_group(context, media_group_id, tag)
            for message in self._get_media_group_messages(context, media_group_id):
                self._save_photo_for_tag(update, context, message, tag)
        else:
            self._save_photo_for_tag(update, context, src_message, tag)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, required=True)
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    spike = Spike(config)
    spike.run()


if __name__ == "__main__":
    main()
