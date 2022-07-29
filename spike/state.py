from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Set

from telegram.ext import CallbackContext


@dataclass
class State:
    categories: Set[str]
    category_by_tag: Dict[str, str]

    @staticmethod
    def from_context(context: CallbackContext) -> State:
        return State(
            categories=context.bot_data["categories"],
            category_by_tag=context.chat_data["category_by_tag"]
        )

    def dump_to_context(self, context: CallbackContext) -> None:
        context.bot_data["categories"] = self.categories
        context.chat_data["category_by_tag"] = self.category_by_tag

    def add_category(self, category: str) -> bool:
        if category in self.categories:
            return False
        self.categories.add(category)
        return True

    def map_tag_to_category(self, tag: str, category: str) -> Optional[str]:
        previous_category = self.category_by_tag.get(tag)
        self.category_by_tag[tag] = category
        return previous_category
    
    def get_category_by_tag(self, tag: str) -> Optional[str]:
        self.category_by_tag.get(tag)

