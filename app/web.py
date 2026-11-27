"""Tavily search/extract and polite image fetching."""
import io
import os

import httpx

_client = httpx.AsyncClient(timeout=40, follow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 (haelt-das hackathon prototype)"})


def _auth():
    return {"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"}


async def search(query, *, max_results=5, images=False, country=None, depth="basic", include_domains=None):
    payload = {"query": query, "max_results": max_results, "search_depth": depth,
               "include_images": images, "include_image_descriptions": images}
    if country:
        payload["country"] = country
    if include_domains:
        payload["include_domains"] = include_domains
    r = await _client.post("https://api.tavily.com/search", json=payload, headers=_auth())
    r.raise_for_status()
    return r.json()


async def extract(url):
    r = await _client.post("https://api.tavily.com/extract", json={"urls": [url], "include_images": True},
                           headers=_auth())
    r.raise_for_status()
    data = r.json()
    res = data.get("results") or []
    return res[0] if res else None


async def image_hash(url):
    """Perceptual hash of an image, or None if it cannot be fetched."""
    try:
        import imagehash
        from PIL import Image
        r = await _client.get(url)
        if r.status_code != 200:
            return None
        with Image.open(io.BytesIO(r.content)) as src:
            return imagehash.phash(src.convert("RGB"))
    except Exception:  # noqa: BLE001 - third-party images fail in many ways; a missing hash is fine
        return None
