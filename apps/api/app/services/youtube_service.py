"""Thin YouTube Data API v3 adapter (S3).

Covers only what discovery needs: mostPopular, search, video, channel,
categories. Returns normalized dicts matching the Source model — never raw
API blobs. Quota costs follow Google's documented unit model
(search ≈ 100 units, everything else here ≈ 1 unit).

No retries, no hammering: one HTTP call per method. Tests inject an
httpx.Client with MockTransport so CI never touches the network.
"""

import structlog
import httpx

log = structlog.get_logger()

BASE_URL = "https://www.googleapis.com/youtube/v3"

# Quota units per operation (documented YouTube Data API cost model).
COST_MOST_POPULAR = 1
COST_SEARCH = 100
COST_VIDEO = 1
COST_CHANNEL = 1
COST_CATEGORIES = 1


class YouTubeAPIError(RuntimeError):
    pass


def _stats(item: dict) -> dict:
    s = item.get("statistics", {})
    to_int = lambda v: int(v) if str(v).isdigit() else 0  # noqa: E731
    return {
        "view_count": to_int(s.get("viewCount", 0)),
        "like_count": to_int(s.get("likeCount", 0)),
        "comment_count": to_int(s.get("commentCount", 0)),
    }


def normalize_video(item: dict) -> dict:
    """Map a videos.list item (or search item with snippet) to Source fields."""
    vid = item.get("id", "")
    video_id = vid.get("videoId", "") if isinstance(vid, dict) else vid
    snippet = item.get("snippet", {})
    content = item.get("contentDetails", {})
    duration = 0.0
    if isinstance(content.get("duration"), str):
        duration = _parse_iso8601_duration(content["duration"])
    return {
        "provider": "youtube",
        "external_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "title": snippet.get("title", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_name": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt"),
        "duration": duration,
        "category": str(item.get("categoryId", snippet.get("categoryId", ""))),
        "description": snippet.get("description", ""),
        "thumbnail_url": (
            (snippet.get("thumbnails", {}).get("medium")
             or snippet.get("thumbnails", {}).get("default") or {}).get("url", "")
        ),
        **_stats(item),
    }


def _parse_iso8601_duration(value: str) -> float:
    """Parse PT#H#M#S to seconds (best-effort, 0.0 on failure)."""
    import re

    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not m:
        return 0.0
    h, mins, s = (int(g) if g else 0 for g in m.groups())
    return float(h * 3600 + mins * 60 + s)


class YouTubeService:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise YouTubeAPIError("youtube api key is not configured")
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=15.0)

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self.api_key}
        try:
            resp = self.client.get(f"{BASE_URL}/{path}", params=params)
        except httpx.HTTPError as e:
            raise YouTubeAPIError(f"youtube request failed: {e}") from e
        if resp.status_code != 200:
            raise YouTubeAPIError(
                f"youtube api error {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    def get_most_popular(
        self, region: str = "US", category_id: str = "", max_results: int = 25
    ) -> tuple[list[dict], int]:
        params: dict = {
            "part": "snippet,statistics,contentDetails",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": max(1, min(max_results, 50)),
        }
        if category_id:
            params["videoCategoryId"] = category_id
        log.info("yt_most_popular", region=region, max_results=max_results)
        data = self._get("videos", params)
        return [normalize_video(i) for i in data.get("items", [])], COST_MOST_POPULAR

    def search_videos(
        self, query: str, region: str = "US", max_results: int = 25
    ) -> tuple[list[dict], int]:
        params: dict = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "regionCode": region,
            "maxResults": max(1, min(max_results, 50)),
        }
        log.info("yt_search", query=query, region=region)
        data = self._get("search", params)
        return [normalize_video(i) for i in data.get("items", [])], COST_SEARCH

    def get_video(self, video_id: str) -> tuple[dict, int]:
        data = self._get(
            "videos",
            {"part": "snippet,statistics,contentDetails", "id": video_id},
        )
        items = data.get("items", [])
        if not items:
            raise YouTubeAPIError(f"video not found: {video_id}")
        return normalize_video(items[0]), COST_VIDEO

    def get_channel(self, channel_id: str) -> tuple[dict, int]:
        data = self._get(
            "channels", {"part": "snippet,statistics", "id": channel_id}
        )
        items = data.get("items", [])
        if not items:
            raise YouTubeAPIError(f"channel not found: {channel_id}")
        item = items[0]
        snippet = item.get("snippet", {})
        return {
            "channel_id": channel_id,
            "channel_name": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            **_stats(item),
        }, COST_CHANNEL

    def get_categories(self, region: str = "US") -> tuple[list[dict], int]:
        data = self._get(
            "videoCategories",
            {"part": "snippet", "regionCode": region},
        )
        cats = [
            {"id": i.get("id", ""), "title": i.get("snippet", {}).get("title", "")}
            for i in data.get("items", [])
        ]
        return cats, COST_CATEGORIES
