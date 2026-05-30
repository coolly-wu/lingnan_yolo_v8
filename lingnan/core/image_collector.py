"""Public image collection helpers for dataset bootstrap."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import cv2
import numpy as np
import requests
import urllib3
from PIL import Image, ImageOps, UnidentifiedImageError

from .. import config as C


MANIFEST = C.DATASET_DIR / "collection_manifest.csv"


@dataclass(frozen=True)
class CandidateImage:
    url: str
    source_page: str = ""
    title: str = ""


@dataclass(frozen=True)
class CollectedImage:
    saved: bool
    reason: str
    local_path: Path | None = None
    source_url: str = ""
    source_page: str = ""
    width: int = 0
    height: int = 0
    sha256: str = ""
    similarity: float = 0.0


@dataclass
class CollectionStats:
    found: int = 0
    downloaded: int = 0
    duplicate_filtered: int = 0
    failed: int = 0
    saved: int = 0


def search_bing_images(keyword: str, limit: int = 1000, timeout: int = 15) -> list[CandidateImage]:
    """Scrape public Bing image result URLs without requiring an API key."""
    results: list[CandidateImage] = []
    seen: set[str] = set()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    first = 1
    query = quote_plus(keyword)
    while len(results) < limit and first <= max(limit * 2, 1000):
        url = f"https://www.bing.com/images/search?q={query}&form=HDRSC2&first={first}"
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        page = resp.text
        before = len(results)
        for cand in _parse_bing_image_urls(page):
            if cand.url in seen:
                continue
            seen.add(cand.url)
            results.append(cand)
            if len(results) >= limit:
                break
        if len(results) == before:
            break
        first += 35
        time.sleep(0.2)
    return results[:limit]


def search_google_images(keyword: str, limit: int = 1000, timeout: int = 15) -> list[CandidateImage]:
    """Scrape public Google image result URLs without requiring an API key."""
    results: list[CandidateImage] = []
    seen: set[str] = set()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    query = quote_plus(keyword)
    for start in range(0, max(limit * 2, 1000), 20):
        if len(results) >= limit:
            break
        url = f"https://www.google.com/search?tbm=isch&udm=2&q={query}&ijn={start // 100}&start={start}"
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        before = len(results)
        for cand in _parse_google_image_urls(resp.text):
            if cand.url in seen:
                continue
            seen.add(cand.url)
            results.append(cand)
            if len(results) >= limit:
                break
        if len(results) == before:
            for cand in _parse_google_web_image_urls(resp.text):
                if cand.url in seen:
                    continue
                seen.add(cand.url)
                results.append(cand)
                if len(results) >= limit:
                    break
        if len(results) == before and start >= 100:
            break
        time.sleep(0.2)
    if not results:
        results = _search_google_fallback_sites(keyword, limit=limit, timeout=timeout)
    if not results:
        try:
            results = _search_google_async_images(keyword, limit=limit, timeout=timeout)
        except requests.RequestException:
            results = []
    return results[:limit]


def search_baidu_images(keyword: str, limit: int = 1000, timeout: int = 15) -> list[CandidateImage]:
    """Scrape public Baidu image result URLs without requiring an API key."""
    results: list[CandidateImage] = []
    seen: set[str] = set()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://image.baidu.com/",
    }
    query = quote_plus(keyword)
    pn = 0
    while len(results) < limit and pn <= max(limit * 3, 300):
        url = (
            "https://image.baidu.com/search/acjson"
            f"?tn=resultjson_com&ipn=rj&ct=201326592&is=&fp=result&queryWord={query}"
            f"&cl=2&lm=-1&ie=utf-8&oe=utf-8&word={query}&pn={pn}&rn=30"
        )
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        before = len(results)
        for cand in _parse_baidu_image_urls(resp.text):
            if cand.url in seen:
                continue
            seen.add(cand.url)
            results.append(cand)
            if len(results) >= limit:
                break
        if len(results) == before and pn >= 60:
            break
        pn += 30
        time.sleep(0.2)
    return results[:limit]


def search_images(
    keyword: str,
    limit: int = 1000,
    timeout: int = 15,
    engine: str = "all",
) -> list[CandidateImage]:
    """Search public image engines and merge candidates with URL de-duplication.

    Individual engine failures are logged and skipped so that a single
    broken engine (e.g. Baidu SSL issues) does not abort the whole batch.
    """
    engine = (engine or "all").lower()
    engines = ["bing", "google", "baidu"] if engine in {"all", "全部", "mixed", "mix"} else [engine]
    per_engine_limit = limit if len(engines) == 1 else max(limit, (limit + len(engines) - 1) // len(engines))
    results: list[CandidateImage] = []
    seen: set[str] = set()
    for name in engines:
        try:
            if name == "bing":
                candidates = search_bing_images(keyword, limit=per_engine_limit, timeout=timeout)
            elif name == "google":
                candidates = search_google_images(keyword, limit=per_engine_limit, timeout=timeout)
            elif name == "baidu":
                candidates = search_baidu_images(keyword, limit=per_engine_limit, timeout=timeout)
            else:
                continue
        except Exception:
            continue
        for cand in _filter_relevant_candidates(keyword, candidates):
            if cand.url in seen:
                continue
            seen.add(cand.url)
            results.append(cand)
            if len(results) >= limit:
                return results
    return results


def collect_candidate(
    candidate: CandidateImage,
    keyword: str,
    root: Path = C.DATASET_DIR,
    existing_hashes: set[str] | None = None,
    existing_urls: set[str] | None = None,
    class_id: int | None = None,
    reference_path: str | Path | None = None,
    min_width: int | None = None,
    similarity_threshold: float | None = None,
) -> CollectedImage:
    existing_hashes = existing_hashes if existing_hashes is not None else load_manifest_hashes(root)
    existing_urls = existing_urls if existing_urls is not None else load_manifest_urls(root)
    if candidate.url in existing_urls:
        return CollectedImage(False, "URL 重复", source_url=candidate.url)

    try:
        raw = _download(candidate.url)
        sha = hashlib.sha256(raw).hexdigest()
        if sha in existing_hashes:
            return CollectedImage(False, "SHA256 重复", source_url=candidate.url, sha256=sha)

        image = Image.open(BytesIO(raw))
        image.load()
        width, height = image.size
        if min_width is not None and width < min_width:
            return CollectedImage(
                False, f"宽度不足 {width}px", source_url=candidate.url,
                width=width, height=height, sha256=sha,
            )

        similarity = 100.0
        if reference_path is not None and similarity_threshold is not None:
            similarity = image_similarity(reference_path, image)
            if similarity < similarity_threshold:
                return CollectedImage(
                    False, f"相似度不足 {similarity:.1f}%", source_url=candidate.url,
                    width=width, height=height, sha256=sha, similarity=similarity,
                )

        class_key = _collection_key(keyword, class_id)
        out_dir = root / "raw" / class_key
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = _next_filename(out_dir, class_key)
        out_path = out_dir / filename
        rgb = image.convert("RGB")
        rgb.save(out_path, "JPEG", quality=92, optimize=True)
        existing_hashes.add(sha)
        existing_urls.add(candidate.url)
        append_manifest(
            root=root,
            local_path=out_path,
            class_id=class_id,
            keyword=keyword,
            source_url=candidate.url,
            source_page=candidate.source_page,
            width=width,
            height=height,
            sha256=sha,
            similarity=similarity,
        )
        return CollectedImage(
            True, "已收录", local_path=out_path, source_url=candidate.url,
            source_page=candidate.source_page, width=width, height=height,
            sha256=sha, similarity=similarity,
        )
    except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
        return CollectedImage(False, f"下载或解析失败：{exc}", source_url=candidate.url)


def _filter_relevant_candidates(keyword: str, candidates: list[CandidateImage]) -> list[CandidateImage]:
    terms = _keyword_terms(keyword)
    if not terms:
        return candidates
    exact = keyword.strip().lower()
    filtered: list[CandidateImage] = []
    for cand in candidates:
        haystack = " ".join([cand.url, cand.source_page, cand.title]).lower()
        if exact and exact in haystack:
            filtered.append(cand)
            continue
        if all(term in haystack for term in terms):
            filtered.append(cand)
            continue
        if len(terms) >= 2 and sum(1 for term in terms if term in haystack) >= 2:
            filtered.append(cand)
    if filtered:
        return filtered
    if _contains_cjk(keyword):
        return []
    return candidates


def _keyword_terms(keyword: str) -> list[str]:
    text = keyword.strip().lower()
    if not text:
        return []
    parts = [p for p in re.split(r"[\s,，、;；]+", text) if p]
    if len(parts) > 1:
        return parts
    terms: list[str] = []
    if "廉江" in text:
        terms.append("廉江")
    if "红橙" in text:
        terms.append("红橙")
    if terms:
        return terms
    return [text]


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def image_similarity(reference_path: str | Path, image: Image.Image) -> float:
    """Return a stricter 0~100 visual similarity score against the reference image.

    The old collector used mostly color histogram similarity, which could accept
    unrelated field images with similar green/orange tones. This scorer combines
    global perceptual hash, SSIM structure, ORB local feature matching, edge
    layout and a low-weight color histogram.
    """
    with Image.open(reference_path) as ref_src:
        ref = _prepare_similarity_image(ref_src)
    img = _prepare_similarity_image(image)

    ref_arr = np.asarray(ref)
    img_arr = np.asarray(img)
    ref_gray = cv2.cvtColor(ref_arr, cv2.COLOR_RGB2GRAY)
    img_gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)

    phash_score = _phash_similarity(ref_gray, img_gray)
    ssim_score = _ssim_score(ref_gray, img_gray)
    orb_score = _orb_similarity(ref_gray, img_gray)
    edge_score = _edge_similarity(ref_gray, img_gray)
    hist_score = _hsv_hist_similarity(ref_arr, img_arr)

    if orb_score is None:
        score = (
            0.32 * phash_score
            + 0.34 * ssim_score
            + 0.20 * edge_score
            + 0.14 * hist_score
        )
    else:
        score = (
            0.25 * phash_score
            + 0.25 * ssim_score
            + 0.25 * orb_score
            + 0.15 * edge_score
            + 0.10 * hist_score
        )
        if orb_score < 0.08 and ssim_score < 0.70:
            score = min(score, 0.78)

    if phash_score < 0.55 and ssim_score < 0.65 and (orb_score or 0.0) < 0.08:
        score = min(score, 0.70)
    return float(max(0.0, min(1.0, score)) * 100.0)


def load_manifest_hashes(root: Path = C.DATASET_DIR) -> set[str]:
    return {row.get("sha256", "") for row in _read_manifest(root) if row.get("sha256")}


def load_manifest_urls(root: Path = C.DATASET_DIR) -> set[str]:
    return {row.get("source_url", "") for row in _read_manifest(root) if row.get("source_url")}


def append_manifest(
    root: Path,
    local_path: Path,
    class_id: int | None,
    keyword: str,
    source_url: str,
    source_page: str,
    width: int,
    height: int,
    sha256: str,
    similarity: float,
) -> None:
    disease = C.DISEASE_BY_ID.get(class_id) if class_id is not None else None
    manifest = root / "collection_manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    exists = manifest.exists()
    fields = [
        "local_path", "class_id", "class_key", "class_name_cn", "keyword",
        "source_url", "source_page", "width", "height", "sha256",
        "similarity", "collected_at",
    ]
    with manifest.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "local_path": str(local_path),
            "class_id": "" if class_id is None else class_id,
            "class_key": disease["key"] if disease else "unclassified",
            "class_name_cn": disease["name_cn"] if disease else "未分类",
            "keyword": keyword,
            "source_url": source_url,
            "source_page": source_page,
            "width": width,
            "height": height,
            "sha256": sha256,
            "similarity": f"{similarity:.2f}",
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })


def _parse_bing_image_urls(page: str) -> list[CandidateImage]:
    candidates: list[CandidateImage] = []
    for raw in re.findall(r"m=(\{.*?\})", page):
        try:
            data = json.loads(html.unescape(raw))
        except json.JSONDecodeError:
            continue
        murl = data.get("murl")
        if murl:
            candidates.append(CandidateImage(str(murl), str(data.get("purl") or ""), str(data.get("t") or "")))
    for raw in re.findall(r'm="(\{.*?\})"', page):
        try:
            data = json.loads(html.unescape(raw))
        except json.JSONDecodeError:
            continue
        murl = data.get("murl")
        if murl:
            candidates.append(CandidateImage(str(murl), str(data.get("purl") or ""), str(data.get("t") or "")))
    for murl in re.findall(r'"murl"\s*:\s*"([^"]+)"', page):
        candidates.append(CandidateImage(html.unescape(murl)))
    for murl in re.findall(r"&quot;murl&quot;\s*:\s*&quot;([^&]+)&quot;", page):
        candidates.append(CandidateImage(html.unescape(murl)))
    for href in re.findall(r'href="([^"]*mediaurl=[^"]+)"', page):
        parsed = urlparse(html.unescape(href))
        media = parse_qs(parsed.query).get("mediaurl", [])
        if media:
            candidates.append(CandidateImage(unquote(media[0])))
    return candidates


def _parse_google_image_urls(page: str) -> list[CandidateImage]:
    candidates: list[CandidateImage] = []
    unescaped = html.unescape(page)

    # Google image pages commonly embed original image URLs in JSON-ish arrays.
    patterns = [
        r'\["(https?://[^"\[]+\.(?:jpg|jpeg|png|webp|bmp)(?:\?[^"]*)?)",\d+,\d+\]',
        r'\["(https?:\\?/\\?/[^"]+\.(?:jpg|jpeg|png|webp|bmp)(?:\?[^"]*)?)",\d+,\d+\]',
        r'"ou"\s*:\s*"(https?://[^"]+)"',
        r'\\"ou\\"\s*:\s*\\"(https?:\\\\/\\\\/[^"]+)\\"',
        r'"imgurl"\s*:\s*"(https?://[^"]+)"',
        r'imgurl=(https?[^&"]+)',
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, unescaped, flags=re.IGNORECASE):
            url = _clean_google_url(raw)
            if _looks_like_image_url(url):
                candidates.append(CandidateImage(url))

    # Fallback for escaped full URLs in script payloads.
    for raw in re.findall(r'https?:\\?/\\?/[^"\\]+?\.(?:jpg|jpeg|png|webp|bmp)(?:\?[^"\\]*)?', unescaped, flags=re.IGNORECASE):
        url = _clean_google_url(raw)
        if _looks_like_image_url(url):
            candidates.append(CandidateImage(url))

    deduped: list[CandidateImage] = []
    seen: set[str] = set()
    for cand in candidates:
        if cand.url in seen:
            continue
        seen.add(cand.url)
        deduped.append(cand)
    return deduped


def _parse_google_web_image_urls(page: str) -> list[CandidateImage]:
    candidates: list[CandidateImage] = []
    unescaped = html.unescape(page)
    for raw in re.findall(r'https?://[^"\s<>]+\.(?:jpg|jpeg|png|webp|bmp)(?:\?[^"\s<>]*)?', unescaped, flags=re.IGNORECASE):
        url = _clean_google_url(raw)
        if _looks_like_image_url(url):
            candidates.append(CandidateImage(url))
    deduped: list[CandidateImage] = []
    seen: set[str] = set()
    for cand in candidates:
        if cand.url in seen:
            continue
        seen.add(cand.url)
        deduped.append(cand)
    return deduped


def _search_google_fallback_sites(keyword: str, limit: int, timeout: int) -> list[CandidateImage]:
    candidates: list[CandidateImage] = []
    seen: set[str] = set()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    # Google's image tab may return a JS-only shell. These site searches still
    # use Google results but target pages that commonly expose direct image URLs.
    queries = [
        f'{keyword} 图片 jpg',
        f'{keyword} filetype:jpg',
        f'{keyword} filetype:png',
    ]
    for q in queries:
        if len(candidates) >= limit:
            break
        url = f"https://www.google.com/search?q={quote_plus(q)}"
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        for cand in _parse_google_web_image_urls(resp.text):
            if cand.url in seen:
                continue
            seen.add(cand.url)
            candidates.append(cand)
            if len(candidates) >= limit:
                break
        time.sleep(0.2)
    return candidates


def _search_google_async_images(keyword: str, limit: int, timeout: int) -> list[CandidateImage]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
    }
    url = (
        "https://www.google.com/search"
        f"?asearch=isch&async=_fmt:json,_id:islrg&q={quote_plus(keyword)}"
    )
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return _parse_google_async_image_urls(resp.text)[:limit]


def _parse_google_async_image_urls(page: str) -> list[CandidateImage]:
    candidates: list[CandidateImage] = []
    unescaped = html.unescape(page)
    titles = re.findall(r'\\"pt\\"\s*:\s*\\"([^"]*)\\"', unescaped)
    pages = re.findall(r'\\"ru\\"\s*:\s*\\"([^"]*)\\"', unescaped)
    for idx, raw in enumerate(re.findall(r'\\"tu\\"\s*:\s*\\"([^"]+)\\"', unescaped)):
        url = _clean_google_url(raw)
        if _looks_like_http_url(url):
            page = _clean_google_url(pages[idx]) if idx < len(pages) else ""
            title = html.unescape(titles[idx]) if idx < len(titles) else ""
            candidates.append(CandidateImage(url, page, title))
    titles2 = re.findall(r'"pt"\s*:\s*"([^"]*)"', unescaped)
    pages2 = re.findall(r'"ru"\s*:\s*"([^"]*)"', unescaped)
    for idx, raw in enumerate(re.findall(r'"tu"\s*:\s*"([^"]+)"', unescaped)):
        url = _clean_google_url(raw)
        if _looks_like_http_url(url):
            page = _clean_google_url(pages2[idx]) if idx < len(pages2) else ""
            title = html.unescape(titles2[idx]) if idx < len(titles2) else ""
            candidates.append(CandidateImage(url, page, title))
    deduped: list[CandidateImage] = []
    seen: set[str] = set()
    for cand in candidates:
        if cand.url in seen:
            continue
        seen.add(cand.url)
        deduped.append(cand)
    return deduped


def _parse_baidu_image_urls(page: str) -> list[CandidateImage]:
    candidates: list[CandidateImage] = []
    try:
        data = json.loads(page)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        for item in data.get("data", []):
            if not isinstance(item, dict):
                continue
            for key in ("thumbURL", "middleURL", "hoverURL", "objURL", "replaceUrl"):
                value = item.get(key)
                if isinstance(value, str):
                    url = _clean_baidu_url(value)
                    if _looks_like_http_url(url):
                        candidates.append(CandidateImage(url, str(item.get("fromURL") or ""), str(item.get("fromPageTitle") or item.get("querySign") or "")))
                elif isinstance(value, list):
                    for entry in value:
                        if isinstance(entry, dict):
                            url = _clean_baidu_url(str(entry.get("ObjURL") or entry.get("FromURL") or ""))
                            if _looks_like_http_url(url):
                                candidates.append(CandidateImage(url))

    unescaped = html.unescape(page)
    for pattern in (
        r'"thumbURL"\s*:\s*"([^"]+)"',
        r'"middleURL"\s*:\s*"([^"]+)"',
        r'"hoverURL"\s*:\s*"([^"]+)"',
        r'"objURL"\s*:\s*"([^"]+)"',
    ):
        for raw in re.findall(pattern, unescaped):
            url = _clean_baidu_url(raw)
            if _looks_like_http_url(url):
                candidates.append(CandidateImage(url))

    deduped: list[CandidateImage] = []
    seen: set[str] = set()
    for cand in candidates:
        if cand.url in seen:
            continue
        seen.add(cand.url)
        deduped.append(cand)
    return deduped


def _clean_google_url(raw: str) -> str:
    url = raw.replace("\\/", "/").replace("\\u003d", "=").replace("\\u0026", "&")
    url = url.replace("\\=", "=").replace("\\&", "&")
    url = unquote(html.unescape(url))
    return url.strip()


def _clean_baidu_url(raw: str) -> str:
    url = raw.replace("\\/", "/").replace("\\u003d", "=").replace("\\u0026", "&")
    url = unquote(html.unescape(url))
    return url.strip()


def _looks_like_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    lowered = parsed.path.lower()
    return lowered.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))


def _looks_like_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _download(url: str, timeout: int = 20, max_bytes: int = 15 * 1024 * 1024) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0"}
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type.lower():
            raise ValueError(f"非图片内容: {content_type}")
        chunks = []
        total = 0
        for chunk in resp.iter_content(8192):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("图片文件过大")
            chunks.append(chunk)
    return b"".join(chunks)


def _next_filename(out_dir: Path, class_key: str) -> str:
    day = datetime.now().strftime("%Y%m%d")
    for i in range(1, 1_000_000):
        name = f"{class_key}_{day}_{i:06d}.jpg"
        if not (out_dir / name).exists():
            return name
    raise RuntimeError("无法生成采集图片文件名")


def _collection_key(keyword: str, class_id: int | None = None) -> str:
    if class_id is not None:
        return C.DISEASE_BY_ID[class_id]["key"]
    text = keyword.strip().lower()
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text, flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        slug = "keyword"
    return f"search_{slug[:48]}"


def _prepare_similarity_image(img: Image.Image, size: int = 320) -> Image.Image:
    prepared = ImageOps.exif_transpose(img).convert("RGB")
    prepared.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (127, 127, 127))
    x = (size - prepared.width) // 2
    y = (size - prepared.height) // 2
    canvas.paste(prepared, (x, y))
    return canvas


def _hsv_hist_similarity(ref_arr: np.ndarray, img_arr: np.ndarray) -> float:
    ref_hsv = cv2.cvtColor(ref_arr, cv2.COLOR_RGB2HSV)
    img_hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
    ref_hist = cv2.calcHist([ref_hsv], [0, 1, 2], None, [24, 24, 12], [0, 180, 0, 256, 0, 256])
    img_hist = cv2.calcHist([img_hsv], [0, 1, 2], None, [24, 24, 12], [0, 180, 0, 256, 0, 256])
    cv2.normalize(ref_hist, ref_hist)
    cv2.normalize(img_hist, img_hist)
    corr = cv2.compareHist(ref_hist, img_hist, cv2.HISTCMP_CORREL)
    return max(0.0, min(1.0, (corr + 1.0) / 2.0))


def _ssim_score(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
    a = a_gray.astype(np.float32)
    b = b_gray.astype(np.float32)
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    kernel = (11, 11)
    sigma = 1.5
    mu_a = cv2.GaussianBlur(a, kernel, sigma)
    mu_b = cv2.GaussianBlur(b, kernel, sigma)
    mu_a_sq = mu_a * mu_a
    mu_b_sq = mu_b * mu_b
    mu_ab = mu_a * mu_b
    sigma_a_sq = cv2.GaussianBlur(a * a, kernel, sigma) - mu_a_sq
    sigma_b_sq = cv2.GaussianBlur(b * b, kernel, sigma) - mu_b_sq
    sigma_ab = cv2.GaussianBlur(a * b, kernel, sigma) - mu_ab
    numerator = (2 * mu_ab + c1) * (2 * sigma_ab + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (sigma_a_sq + sigma_b_sq + c2)
    score = float(np.mean(numerator / (denominator + 1e-12)))
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _phash_similarity(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
    ha = _phash(a_gray)
    hb = _phash(b_gray)
    same = np.count_nonzero(ha == hb)
    return float(same / ha.size)


def _phash(gray: np.ndarray, hash_size: int = 16, highfreq_factor: int = 4) -> np.ndarray:
    size = hash_size * highfreq_factor
    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    low = dct[:hash_size, :hash_size]
    median = np.median(low[1:, 1:])
    return low > median


def _edge_similarity(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
    ea = cv2.Canny(a_gray, 80, 180)
    eb = cv2.Canny(b_gray, 80, 180)
    score = cv2.matchTemplate(ea, eb, cv2.TM_CCOEFF_NORMED)[0][0]
    if np.isnan(score):
        return 0.0
    return max(0.0, min(1.0, (float(score) + 1.0) / 2.0))


def _orb_similarity(a_gray: np.ndarray, b_gray: np.ndarray) -> float | None:
    orb = cv2.ORB_create(nfeatures=800, scaleFactor=1.2, nlevels=8)
    kp_a, des_a = orb.detectAndCompute(a_gray, None)
    kp_b, des_b = orb.detectAndCompute(b_gray, None)
    if des_a is None or des_b is None or not kp_a or not kp_b:
        return None
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = matcher.knnMatch(des_a, des_b, k=2)
    good = []
    for pair in matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < 0.75 * n.distance:
            good.append(m)
    base = max(1, min(len(kp_a), len(kp_b)))
    score = len(good) / base
    if len(good) >= 8:
        src = np.float32([kp_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if mask is not None:
            score *= float(mask.ravel().mean())
    return max(0.0, min(1.0, score * 2.5))


def _ahash_similarity(a: Image.Image, b: Image.Image) -> float:
    ha = _ahash(a)
    hb = _ahash(b)
    same = sum(1 for x, y in zip(ha, hb) if x == y)
    return same / len(ha)


def _ahash(img: Image.Image) -> list[int]:
    gray = img.convert("L").resize((16, 16))
    arr = np.asarray(gray, dtype=np.float32)
    avg = float(arr.mean())
    return [1 if v >= avg else 0 for v in arr.flatten()]


def _read_manifest(root: Path) -> list[dict[str, str]]:
    manifest = root / "collection_manifest.csv"
    if not manifest.exists():
        return []
    with manifest.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
