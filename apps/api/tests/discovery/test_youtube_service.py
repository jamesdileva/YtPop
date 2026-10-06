"""Adapter tests — httpx MockTransport, never the network."""

import httpx
import pytest

from app.services.youtube_service import (
    COST_MOST_POPULAR,
    COST_SEARCH,
    YouTubeAPIError,
    YouTubeService,
    normalize_video,
)


def _video_item(vid: str = "abc123", views: str = "1000") -> dict:
    return {
        "id": vid,
        "snippet": {
            "title": "T",
            "channelId": "ch1",
            "channelTitle": "Ch",
            "publishedAt": "2026-01-01T00:00:00Z",
            "description": "d",
            "thumbnails": {"medium": {"url": "http://img"}},
        },
        "statistics": {"viewCount": views, "likeCount": "10", "commentCount": "2"},
        "contentDetails": {"duration": "PT1M30S"},
    }


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_most_popular_normalizes_and_costs_one():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["chart"] == "mostPopular"
        return httpx.Response(200, json={"items": [_video_item()]})

    yt = YouTubeService(api_key="k", client=_client(handler))
    items, units = yt.get_most_popular(region="US", max_results=5)
    assert units == COST_MOST_POPULAR == 1
    assert items[0]["external_id"] == "abc123"
    assert items[0]["url"] == "https://www.youtube.com/watch?v=abc123"
    assert items[0]["view_count"] == 1000
    assert items[0]["duration"] == 90.0


def test_search_costs_100_units():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [_video_item("s1")]})

    yt = YouTubeService(api_key="k", client=_client(handler))
    _, units = yt.search_videos(query="osrs")
    assert units == COST_SEARCH == 100


def test_api_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "quota"}})

    yt = YouTubeService(api_key="k", client=_client(handler))
    with pytest.raises(YouTubeAPIError, match="403"):
        yt.get_most_popular()


def test_missing_key_raises_before_network():
    with pytest.raises(YouTubeAPIError, match="not configured"):
        YouTubeService(api_key="")


def test_get_video_404_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": []})

    yt = YouTubeService(api_key="k", client=_client(handler))
    with pytest.raises(YouTubeAPIError, match="not found"):
        yt.get_video("nope")


def test_get_categories():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"items": [{"id": "20", "snippet": {"title": "Gaming"}}]}
        )

    yt = YouTubeService(api_key="k", client=_client(handler))
    cats, _ = yt.get_categories()
    assert cats == [{"id": "20", "title": "Gaming"}]


def test_normalize_search_style_id_dict():
    item = _video_item()
    item["id"] = {"videoId": "xyz"}
    assert normalize_video(item)["external_id"] == "xyz"
