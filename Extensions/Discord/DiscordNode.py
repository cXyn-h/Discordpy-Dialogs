import typing
from src.DialogNodes.BaseType import BaseNode, BaseGraphNode
import src.utils.SessionData as SessionData
from datetime import datetime, timedelta
from Extensions.Discord.DiscordUtils import NodetionDCMenuInfo

class DiscordGraphNode(BaseGraphNode):
    VERSION="1.0.0"
    ADDED_FIELDS = '''
options: []'''
    TYPE="Discord"
    SCHEMA = ''

    def activate_node(self, session:typing.Union[None, SessionData.SessionData]=None) -> "BaseNode":
        return DiscordNode(self, session, timeout_duration=timedelta(seconds=self.TTL))
    
class DiscordNode(BaseNode):
    def __init__(self, graph_node:BaseGraphNode, session:typing.Union[None, SessionData.SessionData]=None, timeout_duration:timedelta=None) -> None:
        super().__init__(graph_node, session, timeout_duration)

        self.menu_messages_info:dict[str,NodetionDCMenuInfo] = {}
        # a discord node can have multiple menus so there's less worrying about how many send messages there are in callback section
        self.managed_replies_info:typing.Set[NodetionDCMenuInfo] = set()

    def record_menu_message(self, menu_name, message_info:NodetionDCMenuInfo):
        self.menu_messages_info[menu_name] = message_info

    def record_reply_message(self, message_info:NodetionDCMenuInfo):
        self.managed_replies_info.add(message_info)

    async def delete_menu_message(self, menu_name):
        if menu_name in self.menu_messages_info:
            message_info = self.menu_messages_info[menu_name]
            if message_info.view is not None:
                message_info.view.stop()
            if not message_info.deleted:
                await message_info.message.delete()
            message_info.deleted = True
            del self.menu_messages_info[menu_name]

    async def delete_reply(self, message_id):
        # go find message to delete
        for reply in self.managed_replies_info:
            if reply.message.id == message_id:
                if not reply.deleted:
                    # to prevent exception
                    await reply.message.delete()
                # mark deleted and remove
                reply.deleted = True
                self.managed_replies_info.remove(reply)
                # only one will match and only want to delete one
                break

    async def close_all_menus(self):
        for menu in list(self.menu_messages_info.keys()):
            await self.delete_menu_message(menu)

    async def delete_all_replies(self):
        for reply in list(self.managed_replies_info):
            await self.delete_reply(reply)

    def check_tracking(self, message_id):
        for message_info in self.menu_messages_info.values():
            if message_info.message.id == message_id:
                return "menu"
        for message_info in self.managed_replies_info:
            if message_info.message.id == message_id:
                return "reply"

    def close(self):
        super().close()
        for message_info in self.menu_messages_info.values():
            if message_info.view is not None:
                message_info.view.stop()
        for message_info in self.managed_replies_info:
            if message_info.view is not None:
                message_info.view.stop()