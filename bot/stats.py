from bot.utils.database import db


class BotStats:
    @property
    def total_messages(self):
        return db.get_total_messages()

    @total_messages.setter
    def total_messages(self, value):
        pass

    @property
    def auto_replies_sent(self):
        return db.get_stats().get("auto_replies_sent", 0)

    @auto_replies_sent.setter
    def auto_replies_sent(self, value):
        pass

    @property
    def rp_actions_used(self):
        return db.get_stats().get("rp_actions_used", 0)

    @rp_actions_used.setter
    def rp_actions_used(self, value):
        pass

    @property
    def jokes_sent(self):
        return db.get_stats().get("jokes_sent", 0)

    @jokes_sent.setter
    def jokes_sent(self, value):
        pass

    @property
    def memes_sent(self):
        return db.get_stats().get("memes_sent", 0)

    @memes_sent.setter
    def memes_sent(self, value):
        pass

    @property
    def commands_used(self):
        return db.get_stats().get("commands_used", 0)

    @commands_used.setter
    def commands_used(self, value):
        pass

    @property
    def away_mode_toggled(self):
        return db.get_stats().get("away_mode_toggled", 0)

    @away_mode_toggled.setter
    def away_mode_toggled(self, value):
        pass

    @property
    def start_time(self):
        uptime = db.get_uptime_seconds()
        from datetime import datetime, timedelta
        return datetime.now() - timedelta(seconds=uptime)


stats = BotStats()
