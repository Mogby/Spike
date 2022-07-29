import logging
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Union

import yadisk
from yadisk.exceptions import PathExistsError


AnyPath = Union[str, Path]


class YaDisk:
    def __init__(self, config: Dict[Any, Any]) -> None:
        self.api = yadisk.YaDisk(token=config["token"])
        self.root_dir = Path(config["root_dir"])
        self.public_url = config.get("public_url")

    def save_file(self, file: BinaryIO, path: str) -> None:
        dst_path = self.root_dir / path
        self._mkdir_if_not_exists(dst_path.parent)
        logging.info(f"Uploading to '{path}'")
        self.api.upload(path_or_file=file, dst_path=dst_path)
    
    def get_path_link(self, path: str) -> Optional[str]:
        if self.public_url is None:
            return None
        return f"{self.public_url}/{path}"

    def _mkdir_if_not_exists(self, dir: AnyPath) -> None:
        if not self.api.exists(str(dir)):
            self.api.mkdir(str(dir))

