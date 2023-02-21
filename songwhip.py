from typing import Optional, Dict, Any, Pattern
import re

from yarl import URL
from mautrix.types import EventType, MessageType

from maubot import Plugin, MessageEvent
from maubot.handlers import event, command

url_pattern = re.compile(r"https?://\w+.\w+.(?:[a-z]{1,3}|co\.uk)/.+")
spotify_pattern = re.compile(r"/(?:album|artist|track)/(?:.+)")
apple_pattern = re.compile(r"/(?:[a-z]{2}/)?(?:album|artist)/.+?/(?:id)?(?:\d+)")
tidal_pattern = re.compile(r"/(?:browse/)?(?:artist|album|track)/(?:\d+)")
yandex_pattern = re.compile(r"/(?:artist|album)/(?:\d+/track/)?(\d+[^/?#]+)")
amazon_pattern = re.compile(r"/albums/.+")
anything = re.compile(".+")

allowed_domains: Dict[str, Pattern] = {
    "open.spotify.com": spotify_pattern,
    "play.spotify.com": spotify_pattern,
    "itunes.apple.com": apple_pattern,
    "music.apple.com": apple_pattern,
    "itun.es": anything,
    "deezer.com": re.compile(r"/(?:\w{2}/)?(?:album|artist|track)/(?:.+)"),
    "play.google.com": re.compile(r"/music/.+/[BAT][a-z0-9]+"),
    "youtube.com": re.compile(r"/watch"),
    "youtu.be": anything,
    "tidal.com": tidal_pattern,
    "listen.tidal.com": tidal_pattern,
    "music.yandex.com": yandex_pattern,
    "music.yandex.ru": yandex_pattern,
    "soundcloud.com": re.compile(r"/\w+?/.+"),
}


def check_url(url: str) -> bool:
    parsed_url = URL(url)
    if parsed_url.scheme not in ("http", "https"):
        return False
    host = parsed_url.host
    if host.startswith("www."):
        host = host[len("www."):]
    if host.startswith("music.amazon.") and len(host) <= len("music.amazon.co.uk"):
        path_pattern = amazon_pattern
    else:
        try:
            path_pattern = allowed_domains[host]
        except KeyError:
            return False
    if path_pattern is anything:
        return True
    return bool(path_pattern.match(parsed_url.path))


class SongwhipBot(Plugin):
    async def get_meta(self, url: str) -> Optional[Dict[str, Any]]:
        async with self.http.post("https://songwhip.com/api/songwhip/create", json={"country": "N/A", "url": url}) as resp:
            if resp.status == 400:
                return None
            resp.raise_for_status()
            return await resp.json()

    @command.new("songwhip", aliases=("song",))
    @command.argument("url", pass_raw=True)
    async def on_command(self, evt: MessageEvent, url: str) -> None:
        if not url_pattern.fullmatch(url):
            await evt.reply("That doesn't look like a URL 🧐")
            return
        elif not check_url(url):
            await evt.reply("That doesn't look like a supported music URL 🤔")
            return
        await evt.mark_read()
        meta = await self.get_meta(url)
        if not meta or "url" not in meta:
            await evt.reply("Didn't find Songwhip metadata for that URL 😿")
            return
        await evt.reply(meta["url"])

    @event.on(EventType.ROOM_MESSAGE)
    async def on_message(self, evt: MessageEvent) -> None:
        if evt.content.msgtype != MessageType.TEXT or evt.content.body.startswith("!"):
            return
        for url in url_pattern.findall(evt.content.body):
            if check_url(url):
                await evt.mark_read()
                meta = await self.get_meta(url)
                if not meta or meta.get("status") != "success":
                    continue
                path = meta.get("data", {}).get("item", {}).get("path")
                if not path:
                    continue
                await evt.reply(f"https://songwhip.com/{path}")
                break
