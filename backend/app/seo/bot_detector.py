"""
Bot / crawler detector for the prerender pipeline.

Scope: only reputable, whitelisted crawlers get the prerendered HTML.
This is not a security control — it's a serving hint. Anyone can spoof a
User-Agent, but that's fine: bot HTML has the same content the human sees
(no cloaking), just delivered synchronously.

Category legend
---------------
* search_engine — indexing crawlers we WANT on the site once indexing is on.
* social       — link-unfurler bots (build OG/Twitter/Slack/TG cards).
* seo_tool     — Ahrefs/Semrush/etc. Useful for SEO audits.
* ai_crawler   — GPTBot/ClaudeBot/etc. Respect admin's block_ai_crawlers flag.

Public API
----------
* is_bot(user_agent: str) -> bool
* which_bot(user_agent: str) -> BotInfo | None
* BOT_UA_LIST — the raw list (also surfaced via /api/prerender/health).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class BotInfo:
    name: str
    category: str   # search_engine | social | seo_tool | ai_crawler
    pattern: str    # regex fragment matched


# ─── Whitelist (order matters — first match wins) ─────────────────────
# Every entry is a regex fragment. Case-insensitive matched against UA.
BOT_UA_LIST: List[BotInfo] = [
    # Search engines
    BotInfo("Googlebot",         "search_engine", r"googlebot"),
    BotInfo("Googlebot-Image",   "search_engine", r"googlebot-image"),
    BotInfo("Googlebot-News",    "search_engine", r"googlebot-news"),
    BotInfo("Google-InspectionTool", "search_engine", r"google-inspectiontool"),
    BotInfo("AdsBot-Google",     "search_engine", r"adsbot-google"),
    BotInfo("Storebot-Google",   "search_engine", r"storebot-google"),
    BotInfo("Bingbot",           "search_engine", r"bingbot"),
    BotInfo("BingPreview",       "search_engine", r"bingpreview"),
    BotInfo("DuckDuckBot",       "search_engine", r"duckduckbot"),
    BotInfo("YandexBot",         "search_engine", r"yandex(?:bot|images|mobilebot)"),
    BotInfo("Applebot",          "search_engine", r"applebot"),
    BotInfo("MojeekBot",         "search_engine", r"mojeekbot"),
    BotInfo("Baiduspider",       "search_engine", r"baiduspider"),
    BotInfo("Sogou",             "search_engine", r"sogou"),
    BotInfo("Seznam",             "search_engine", r"seznambot"),

    # Social link-unfurl bots
    BotInfo("Facebook",          "social", r"facebookexternalhit|facebot|meta-externalagent|meta-externalfetcher"),
    BotInfo("Twitter",           "social", r"twitterbot"),
    BotInfo("LinkedIn",          "social", r"linkedinbot"),
    BotInfo("Slack",             "social", r"slackbot(?:-linkexpanding)?|slack-imgproxy"),
    BotInfo("Telegram",          "social", r"telegrambot"),
    BotInfo("WhatsApp",          "social", r"whatsapp"),
    BotInfo("Discord",           "social", r"discordbot"),
    BotInfo("Viber",             "social", r"viber(?:url)?bot"),
    BotInfo("Pinterest",         "social", r"pinterestbot|pinterest"),
    BotInfo("Skype",             "social", r"skypeuripreview"),
    BotInfo("Vkontakte",         "social", r"vkshare|vkontakte"),
    BotInfo("Redditbot",         "social", r"redditbot"),
    BotInfo("Embedly",           "social", r"embedly"),
    BotInfo("Nuzzel",            "social", r"nuzzel"),
    BotInfo("Iframely",          "social", r"iframely"),

    # SEO / monitoring tools
    BotInfo("AhrefsBot",         "seo_tool", r"ahrefsbot"),
    BotInfo("SemrushBot",        "seo_tool", r"semrushbot"),
    BotInfo("MJ12bot",           "seo_tool", r"mj12bot"),
    BotInfo("DotBot",            "seo_tool", r"dotbot"),
    BotInfo("PetalBot",          "seo_tool", r"petalbot"),
    BotInfo("Screaming Frog",    "seo_tool", r"screaming\s?frog\s?seo\s?spider|screamingfrogseospider"),
    BotInfo("Sitebulb",          "seo_tool", r"sitebulb"),
    BotInfo("Rogerbot",          "seo_tool", r"rogerbot"),

    # AI crawlers (subject to admin's block_ai_crawlers switch)
    BotInfo("GPTBot",            "ai_crawler", r"gptbot"),
    BotInfo("ChatGPT-User",      "ai_crawler", r"chatgpt-user"),
    BotInfo("OAI-SearchBot",     "ai_crawler", r"oai-searchbot"),
    BotInfo("ClaudeBot",         "ai_crawler", r"claudebot"),
    BotInfo("Claude-Web",        "ai_crawler", r"claude-web"),
    BotInfo("anthropic-ai",      "ai_crawler", r"anthropic-ai"),
    BotInfo("PerplexityBot",     "ai_crawler", r"perplexitybot"),
    BotInfo("CCBot",             "ai_crawler", r"ccbot"),
    BotInfo("Google-Extended",   "ai_crawler", r"google-extended"),
    BotInfo("Bytespider",        "ai_crawler", r"bytespider"),
    BotInfo("Amazonbot",         "ai_crawler", r"amazonbot"),
    BotInfo("YouBot",            "ai_crawler", r"youbot"),
    BotInfo("Diffbot",           "ai_crawler", r"diffbot"),
]

# Compile once at import time — regex OR of all patterns for a fast fast-path.
_ANY_BOT_RE = re.compile(
    "|".join(f"(?P<b{i}>{b.pattern})" for i, b in enumerate(BOT_UA_LIST)),
    re.IGNORECASE,
)

# Generic hint the fast-path uses to reject obvious human UAs quickly.
_GENERIC_BOT_HINT = re.compile(r"bot|crawl|spider|slurp|fetch|preview|whatsapp|linkexpanding|embedly", re.IGNORECASE)


def is_bot(user_agent: Optional[str]) -> bool:
    if not user_agent:
        return False
    if not _GENERIC_BOT_HINT.search(user_agent):
        return False
    return _ANY_BOT_RE.search(user_agent) is not None


def which_bot(user_agent: Optional[str]) -> Optional[BotInfo]:
    """Return the first BotInfo that matches, or None."""
    if not user_agent:
        return None
    m = _ANY_BOT_RE.search(user_agent)
    if not m:
        return None
    for i, info in enumerate(BOT_UA_LIST):
        if m.group(f"b{i}"):
            return info
    return None


def bot_directory() -> List[dict]:
    """Serialisable list of every recognised bot (for /api/prerender/health)."""
    return [{"name": b.name, "category": b.category, "pattern": b.pattern} for b in BOT_UA_LIST]


__all__ = ["is_bot", "which_bot", "bot_directory", "BOT_UA_LIST", "BotInfo"]
