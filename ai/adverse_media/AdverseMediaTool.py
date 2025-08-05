"""
Comprehensive adverse-media search helper.
Sources are kept minimal here; add/replace with any paid APIs you own.
"""
from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime, timedelta
import os, asyncio, aiohttp

ADVERSE_KEYWORDS = [
    "fraud", "corruption", "scandal", "lawsuit",
    "investigation", "sanction", "money laundering",
    "bribery", "criminal charges", "regulatory action",
    "fine", "penalty", "suspended", "banned"
]

class AdverseMediaTool:
    """Async multi-source adverse news scanner."""

    def __init__(self, cfg):
        self.cfg = cfg
        # Example keys – read from env / cfg
        self.newsapi_key   = cfg.news_api_keys.get("newsapi")
        self.bing_key      = cfg.news_api_keys.get("bing_news")
        self.serper_key    = cfg.news_api_keys.get("serper")

        # pull no older than N days
        self.since = datetime.utcnow() - timedelta(days=cfg.adverse_media_config["search_timeframe_days"])

    # ---------- public -----------------------------------------------------

    async def search(self, entity: str, location: str="") -> Dict[str, Any]:
        """
        Performs concurrent queries and normalises the output.
        """
        tasks = [
            self._search_newsapi(entity),
            self._search_bing(entity),
            self._search_serper(entity)
            # ➕ add more tasks here (regulatory APIs, social, etc.)
        ]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        findings: List[Dict] = [item for sub in gathered if isinstance(sub, list) for item in sub]

        score = self._score(findings)
        return {
            "entity": entity,
            "location": location,
            "search_timestamp": datetime.utcnow().isoformat(),
            "risk_score": score,
            "adverse_findings": findings
        }

    # ---------- private helpers -------------------------------------------

    async def _search_newsapi(self, entity: str) -> List[Dict[str, Any]]:
        if not self.newsapi_key: return []
        url = "https://newsapi.org/v2/everything"
        headers = {"X-Api-Key": self.newsapi_key}
        params  = {"q": entity, "language": "en", "from": self.since.date(), "pageSize": 50}
        return await self._fetch_and_filter(url, params, headers, src="newsapi")

    async def _search_bing(self, entity: str) -> List[Dict[str, Any]]:
        if not self.bing_key: return []
        url = "https://api.bing.microsoft.com/v7.0/news/search"
        headers = {"Ocp-Apim-Subscription-Key": self.bing_key}
        params  = {"q": entity, "freshness": "Month", "textDecorations": False, "count": 50}
        return await self._fetch_and_filter(url, params, headers, src="bing")

    async def _search_serper(self, entity: str) -> List[Dict[str, Any]]:
        if not self.serper_key: return []
        url = "https://google.serper.dev/news"
        headers = {"X-API-KEY": self.serper_key}
        params  = {"q": entity, "gl": "us", "hl": "en"}
        return await self._fetch_and_filter(url, params, headers, src="serper")

    # shared fetch+filter
    async def _fetch_and_filter(self, url, params, headers, src):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=20) as resp:
                    data = await resp.json()
        except Exception:
            return []

        # provider-specific result paths
        articles = (
            data.get("articles") or          # NewsAPI
            data.get("value")    or          # Bing
            data.get("news")     or []       # Serper
        )

        findings = []
        for art in articles:
            txt = f'{art.get("title","")} {art.get("description","")}'.lower()
            if any(kw in txt for kw in ADVERSE_KEYWORDS):
                findings.append({
                    "headline": art.get("title"),
                    "url": art.get("url"),
                    "published": art.get("publishedAt") or art.get("datePublished"),
                    "source": src
                })
        return findings

    @staticmethod
    def _score(findings: List[Dict]) -> int:
        """Very naive risk scoring: more hits ⇒ higher score (cap 10)."""
        n = len(findings)
        return min(10, 1 + n // 3)
