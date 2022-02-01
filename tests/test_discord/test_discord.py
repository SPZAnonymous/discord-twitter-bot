import nextcord
import unittest


class TestWebhook(unittest.TestCase):
    def test_discord(self):
        self.assertEqual(
            nextcord.version_info.major,
            1,
            msg="discord.py rewrite (>=1.0.0) is needed. "
            "You have {}.{}.{}".format(*nextcord.version_info[:3]),
        )
