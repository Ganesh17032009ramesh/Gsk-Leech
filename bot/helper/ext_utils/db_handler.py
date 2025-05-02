import inspect
from importlib import import_module
from time import time as get_time

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from bot import LOGGER, qbit_options, rss_dict, user_data
from bot.core.aeon_client import TgClient
from bot.core.config_manager import Config

try:
    from bot.helper.ext_utils.gc_utils import smart_garbage_collection
except ImportError:
    smart_garbage_collection = None


class DbManager:
    def __init__(self):
        self._return = True
        self._conn = None
        self.db = None

    async def connect(self):
        try:
            if self._conn is not None:
                try:
                    await self._conn.close()
                except Exception as e:
                    LOGGER.error(f"Error closing previous DB connection: {e}")
            self._conn = AsyncIOMotorClient(
                Config.DATABASE_URL,
                server_api=ServerApi("1"),
                maxPoolSize=10,  # Limit connection pool size
                minPoolSize=1,
                maxIdleTimeMS=30000,  # Close idle connections after 30 seconds
                connectTimeoutMS=5000,  # 5 second connection timeout
                socketTimeoutMS=10000,  # 10 second socket timeout
            )
            self.db = self._conn.luna
            self._return = False
            LOGGER.info("Successfully connected to database")
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self.db = None
            self._return = True
            self._conn = None

    async def disconnect(self):
        self._return = True
        if self._conn is not None:
            try:
                await self._conn.close()
                LOGGER.info("Database connection closed successfully")
            except Exception as e:
                LOGGER.error(f"Error closing database connection: {e}")
        self._conn = None
        self.db = None

        # Force garbage collection after database operations
        if smart_garbage_collection is not None:
            smart_garbage_collection(aggressive=True)

    async def update_deploy_config(self):
        if self._return:
            return
        settings = import_module("config")
        config_file = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
        await self.db.settings.deployConfig.replace_one(
            {"_id": TgClient.ID},
            config_file,
            upsert=True,
        )

    async def update_config(self, dict_):
        if self._return:
            return
        await self.db.settings.config.update_one(
            {"_id": TgClient.ID},
            {"$set": dict_},
            upsert=True,
        )

    async def update_aria2(self, key, value):
        if self._return:
            return
        await self.db.settings.aria2c.update_one(
            {"_id": TgClient.ID},
            {"$set": {key: value}},
            upsert=True,
        )

    async def update_qbittorrent(self, key, value):
        if self._return:
            return
        await self.db.settings.qbittorrent.update_one(
            {"_id": TgClient.ID},
            {"$set": {key: value}},
            upsert=True,
        )

    async def save_qbit_settings(self):
        if self._return:
            return
        await self.db.settings.qbittorrent.update_one(
            {"_id": TgClient.ID},
            {"$set": qbit_options},
            upsert=True,
        )

    async def update_private_file(self, path):
        if self._return:
            return
        db_path = path.replace(".", "__")
        if await aiopath.exists(path):
            try:
                async with aiopen(path, "rb+") as pf:
                    pf_bin = await pf.read()
                await self.db.settings.files.update_one(
                    {"_id": TgClient.ID},
                    {"$set": {db_path: pf_bin}},
                    upsert=True,
                )
                if path == "config.py":
                    await self.update_deploy_config()

                # Force garbage collection after handling large files
                if (
                    len(pf_bin) > 1024 * 1024
                    and smart_garbage_collection is not None
                ):  # 1MB
                    smart_garbage_collection(aggressive=False)

                # Explicitly delete large binary data
                del pf_bin
            except Exception as e:
                LOGGER.error(f"Error updating private file {path}: {e}")
        else:
            await self.db.settings.files.update_one(
                {"_id": TgClient.ID},
                {"$unset": {db_path: ""}},
                upsert=True,
            )

    async def update_nzb_config(self):
        if self._return:
            return
        async with aiopen("sabnzbd/SABnzbd.ini", "rb+") as pf:
            nzb_conf = await pf.read()
        await self.db.settings.nzb.replace_one(
            {"_id": TgClient.ID},
            {"SABnzbd__ini": nzb_conf},
            upsert=True,
        )

    async def update_user_data(self, user_id):
        if self._return:
            return
        data = user_data.get(user_id, {})
        data = data.copy()
        for key in (
            "THUMBNAIL",
            "RCLONE_CONFIG",
            "TOKEN_PICKLE",
            "USER_COOKIES",
            "TOKEN",
            "TIME",
        ):
            data.pop(key, None)
        pipeline = [
            {
                "$replaceRoot": {
                    "newRoot": {
                        "$mergeObjects": [
                            data,
                            {
                                "$arrayToObject": {
                                    "$filter": {
                                        "input": {"$objectToArray": "$$ROOT"},
                                        "as": "field",
                                        "cond": {
                                            "$in": [
                                                "$$field.k",
                                                [
                                                    "THUMBNAIL",
                                                    "RCLONE_CONFIG",
                                                    "TOKEN_PICKLE",
                                                    "USER_COOKIES",
                                                ],
                                            ],
                                        },
                                    },
                                },
                            },
                        ],
                    },
                },
            },
        ]
        await self.db.users.update_one({"_id": user_id}, pipeline, upsert=True)

    async def update_user_doc(self, user_id, key, path=""):
        if self._return:
            return
        if path:
            async with aiopen(path, "rb+") as doc:
                doc_bin = await doc.read()
            await self.db.users.update_one(
                {"_id": user_id},
                {"$set": {key: doc_bin}},
                upsert=True,
            )
        else:
            await self.db.users.update_one(
                {"_id": user_id},
                {"$unset": {key: ""}},
                upsert=True,
            )

    async def rss_update_all(self):
        if self._return:
            return
        for user_id in list(rss_dict.keys()):
            await self.db.rss[TgClient.ID].replace_one(
                {"_id": user_id},
                rss_dict[user_id],
                upsert=True,
            )

    async def rss_update(self, user_id):
        if self._return:
            return
        await self.db.rss[TgClient.ID].replace_one(
            {"_id": user_id},
            rss_dict[user_id],
            upsert=True,
        )

    async def rss_delete(self, user_id):
        if self._return:
            return
        await self.db.rss[TgClient.ID].delete_one({"_id": user_id})

    async def add_incomplete_task(self, cid, link, tag):
        if self._return:
            return
        await self.db.tasks[TgClient.ID].insert_one(
            {"_id": link, "cid": cid, "tag": tag},
        )

    async def get_pm_uids(self):
        if self._return:
            return None
        return [doc["_id"] async for doc in self.db.pm_users[TgClient.ID].find({})]

    async def update_pm_users(self, user_id):
        if self._return:
            return
        if not bool(await self.db.pm_users[TgClient.ID].find_one({"_id": user_id})):
            await self.db.pm_users[TgClient.ID].insert_one({"_id": user_id})
            LOGGER.info(f"New PM User Added : {user_id}")

    async def rm_pm_user(self, user_id):
        if self._return:
            return
        await self.db.pm_users[TgClient.ID].delete_one({"_id": user_id})

    async def update_user_tdata(self, user_id, token, expiry_time):
        if self._return:
            return
        await self.db.access_token.update_one(
            {"_id": user_id},
            {"$set": {"TOKEN": token, "TIME": expiry_time}},
            upsert=True,
        )

    async def update_user_token(self, user_id, token):
        if self._return:
            return
        await self.db.access_token.update_one(
            {"_id": user_id},
            {"$set": {"TOKEN": token}},
            upsert=True,
        )

    async def get_token_expiry(self, user_id):
        if self._return:
            return None
        user_data = await self.db.access_token.find_one({"_id": user_id})
        if user_data:
            return user_data.get("TIME")
        return None

    async def delete_user_token(self, user_id):
        if self._return:
            return
        await self.db.access_token.delete_one({"_id": user_id})

    async def get_user_token(self, user_id):
        if self._return:
            return None
        user_data = await self.db.access_token.find_one({"_id": user_id})
        if user_data:
            return user_data.get("TOKEN")
        return None

    async def delete_all_access_tokens(self):
        if self._return:
            return
        await self.db.access_token.delete_many({})

    async def rm_complete_task(self, link):
        if self._return:
            return
        await self.db.tasks[TgClient.ID].delete_one({"_id": link})

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self._return:
            return notifier_dict
        if await self.db.tasks[TgClient.ID].find_one():
            rows = self.db.tasks[TgClient.ID].find({})
            async for row in rows:
                if row["cid"] in list(notifier_dict.keys()):
                    if row["tag"] in list(notifier_dict[row["cid"]]):
                        notifier_dict[row["cid"]][row["tag"]].append(row["_id"])
                    else:
                        notifier_dict[row["cid"]][row["tag"]] = [row["_id"]]
                else:
                    notifier_dict[row["cid"]] = {row["tag"]: [row["_id"]]}
        await self.db.tasks[TgClient.ID].drop()
        return notifier_dict

    async def trunc_table(self, name):
        if self._return:
            return
        await self.db[name][TgClient.ID].drop()

    async def store_scheduled_deletion(
        self,
        chat_ids,
        message_ids,
        delete_time,
        bot_id=None,
    ):
        """Store messages for scheduled deletion

        Args:
            chat_ids: List of chat IDs
            message_ids: List of message IDs
            delete_time: Timestamp when the message should be deleted
            bot_id: ID of the bot that created the message (default: main bot ID)
        """
        if self.db is None:
            return

        # Default to main bot ID if not specified
        if bot_id is None:
            bot_id = TgClient.ID

        # Storing messages for deletion

        # Store each message individually to avoid bulk write issues
        for chat_id, message_id in zip(chat_ids, message_ids, strict=True):
            try:
                await self.db.scheduled_deletions.update_one(
                    {"chat_id": chat_id, "message_id": message_id},
                    {"$set": {"delete_time": delete_time, "bot_id": bot_id}},
                    upsert=True,
                )
            except Exception as e:
                LOGGER.error(f"Error storing scheduled deletion: {e}")

        # Messages stored for deletion

    async def remove_scheduled_deletion(self, chat_id, message_id):
        """Remove a message from scheduled deletions"""
        if self.db is None:
            return
        await self.db.scheduled_deletions.delete_one(
            {"chat_id": chat_id, "message_id": message_id},
        )

    async def get_pending_deletions(self):
        """Get messages that are due for deletion"""
        if self.db is None:
            return []

        current_time = int(get_time())
        # Get current time for comparison

        # Create index for better performance if it doesn't exist
        await self.db.scheduled_deletions.create_index([("delete_time", 1)])

        # Get all documents for manual processing
        all_docs = [doc async for doc in self.db.scheduled_deletions.find()]

        # Process documents manually to ensure we catch all due messages
        # Include a buffer of 30 seconds to catch messages that are almost due
        buffer_time = 30  # 30 seconds buffer

        # Use list comprehension for better performance and return directly
        # Messages found for deletion
        return [
            (doc["chat_id"], doc["message_id"], doc.get("bot_id", TgClient.ID))
            for doc in all_docs
            if doc.get("delete_time", 0) <= current_time + buffer_time
        ]

    async def clean_old_scheduled_deletions(self, days=1):
        """Clean up scheduled deletion entries that have been processed but not removed

        Args:
            days: Number of days after which to clean up entries (default: 1)
        """
        if self.db is None:
            return 0

        # Calculate the timestamp for 'days' ago
        one_day_ago = int(get_time() - (days * 86400))  # 86400 seconds = 1 day

        # Cleaning up old scheduled deletion entries

        # Get all entries to check which ones are actually old and processed
        entries_to_check = [
            doc async for doc in self.db.scheduled_deletions.find({})
        ]

        # Count entries by type
        current_time = int(get_time())
        past_due = [
            doc for doc in entries_to_check if doc["delete_time"] < current_time
        ]

        # Only delete entries that are more than 'days' old AND have already been processed
        # (i.e., their delete_time is in the past)
        deleted_count = 0
        for doc in past_due:
            # If the entry is more than 'days' old from its scheduled deletion time
            if doc["delete_time"] < one_day_ago:
                result = await self.db.scheduled_deletions.delete_one(
                    {"_id": doc["_id"]},
                )
                if result.deleted_count > 0:
                    deleted_count += 1

        # No need to log cleanup results

        return deleted_count

    async def get_all_scheduled_deletions(self):
        """Get all scheduled deletions for debugging purposes"""
        if self.db is None:
            return []

        cursor = self.db.scheduled_deletions.find({})
        current_time = int(get_time())

        # Return all scheduled deletions
        result = [
            {
                "chat_id": doc["chat_id"],
                "message_id": doc["message_id"],
                "delete_time": doc["delete_time"],
                "bot_id": doc.get("bot_id", TgClient.ID),
                "time_remaining": doc["delete_time"] - current_time
                if "delete_time" in doc
                else "unknown",
                "is_due": doc["delete_time"]
                <= current_time + 30  # 30 seconds buffer
                if "delete_time" in doc
                else False,
            }
            async for doc in cursor
        ]

        # Only log detailed information when called from check_deletion.py
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        if "check_deletion" in caller_name:
            LOGGER.info(f"Found {len(result)} total scheduled deletions in database")
            if result:
                pending_count = sum(1 for item in result if item["is_due"])
                future_count = sum(1 for item in result if not item["is_due"])

                LOGGER.info(
                    f"Pending deletions: {pending_count}, Future deletions: {future_count}",
                )

                # Log some sample entries
                if result:
                    sample = result[:5] if len(result) > 5 else result
                    for entry in sample:
                        LOGGER.info(
                            f"Sample entry: {entry} - Due for deletion: {entry['is_due']}",
                        )

        return result


database = DbManager()
