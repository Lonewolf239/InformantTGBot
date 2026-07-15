from bot.utils.database import db


class BotStats:
    @property
    async def total_messages(self):
        return await db.get_total_messages()

    @total_messages.setter
    def total_messages(self, value):
        pass

    @property
    async def auto_replies_sent(self):
        return await db.get_stats().get("auto_replies_sent", 0)

    @auto_replies_sent.setter
    def auto_replies_sent(self, value):
        pass

    @property
    async def rp_actions_used(self):
        return await db.get_stats().get("rp_actions_used", 0)

    @rp_actions_used.setter
    def rp_actions_used(self, value):
        pass

    @property
    async def jokes_sent(self):
        return await db.get_stats().get("jokes_sent", 0)

    @jokes_sent.setter
    def jokes_sent(self, value):
        pass

    @property
    async def memes_sent(self):
        return await db.get_stats().get("memes_sent", 0)

    @memes_sent.setter
    def memes_sent(self, value):
        pass

    @property
    async def commands_used(self):
        return await db.get_stats().get("commands_used", 0)

    @commands_used.setter
    def commands_used(self, value):
        pass

    @property
    async def away_mode_toggled(self):
        return await db.get_stats().get("away_mode_toggled", 0)

    @away_mode_toggled.setter
    def away_mode_toggled(self, value):
        pass

    @property
    async def start_time(self):
        uptime = await db.get_uptime_seconds()
        from datetime import datetime, timedelta

        return datetime.now() - timedelta(seconds=uptime)


stats = BotStats()
