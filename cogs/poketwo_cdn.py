import os
import aiohttp
import logging
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

LAST_KNOWN  = 50254
PING_USER   = 1131217949672353832
WEBHOOK_URL = os.environ["POKETWO_WEBHOOK_URL"]
BASE_URL    = "https://cdn.poketwo.net/images/{}.png"
WATCH_IDS   = [LAST_KNOWN + 1, LAST_KNOWN + 2, LAST_KNOWN + 3]


class PoketwoMonitor(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        self.found : set[int] = set()
        self.monitor_loop.start()

    def cog_unload(self):
        self.monitor_loop.cancel()

    @tasks.loop(minutes=1)
    async def monitor_loop(self):
        if self.found >= set(WATCH_IDS):
            self.monitor_loop.cancel()
            return

        async with aiohttp.ClientSession() as session:
            for number in WATCH_IDS:
                if number in self.found:
                    continue

                url  = BASE_URL.format(number)
                live = await self._is_live(session, url)

                if live:
                    self.found.add(number)
                    all_done = self.found >= set(WATCH_IDS)
                    footer   = "\n\n✅ **All 3 found — monitoring stopped.**" if all_done else ""

                    await session.post(WEBHOOK_URL, json={
                        "content"          : f"🟢 `#{number}` just went live!\n{url}{footer}",
                        "username"         : "Poketwo Event Monitor",
                        "avatar_url"       : "https://cdn.poketwo.net/images/50254.png",
                        "allowed_mentions" : {"users": [str(PING_USER)]}
                    })

                    if all_done:
                        self.monitor_loop.cancel()
                        return

    @monitor_loop.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()

    async def _is_live(self, session: aiohttp.ClientSession, url: str) -> bool:
        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"HEAD request failed for {url}: {e}")
            return False


async def setup(bot: commands.Bot):
    await bot.add_cog(PoketwoMonitor(bot))
