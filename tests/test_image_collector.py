"""Image collection helpers."""

from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageDraw


def _image(path: Path, color=(120, 180, 80), size=(800, 480)):
    Image.new("RGB", size, color).save(path, "JPEG")


def _orchard_like_image(path: Path, size=(800, 480)):
    img = Image.new("RGB", size, (92, 154, 76))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 300, size[0], size[1]), fill=(108, 82, 48))
    for x in range(80, size[0], 160):
        draw.ellipse((x - 55, 85, x + 65, 245), fill=(48, 118, 50))
        draw.rectangle((x - 8, 210, x + 8, 330), fill=(92, 58, 34))
        draw.ellipse((x + 25, 160, x + 50, 185), fill=(226, 111, 37))
    img.save(path, "JPEG", quality=92)


def _similar_color_different_structure(path: Path, size=(800, 480)):
    img = Image.new("RGB", size, (92, 154, 76))
    draw = ImageDraw.Draw(img)
    for i in range(0, size[0], 32):
        fill = (70 + i % 70, 140 + i % 40, 70)
        draw.rectangle((i, 0, i + 16, size[1]), fill=fill)
    draw.rectangle((0, 300, size[0], size[1]), fill=(108, 82, 48))
    img.save(path, "JPEG", quality=92)


def test_similarity_same_image_high(tmp_path):
    from xhgan.core import image_collector as ic

    ref = tmp_path / "ref.jpg"
    _image(ref)
    img = Image.open(ref)
    assert ic.image_similarity(ref, img) >= 99


def test_similarity_resized_same_subject_high(tmp_path):
    from xhgan.core import image_collector as ic

    ref = tmp_path / "ref.jpg"
    _orchard_like_image(ref)
    candidate = Image.open(ref).resize((700, 420))
    assert ic.image_similarity(ref, candidate) >= 90


def test_similarity_similar_color_different_structure_low(tmp_path):
    from xhgan.core import image_collector as ic

    ref = tmp_path / "ref.jpg"
    other = tmp_path / "other.jpg"
    _orchard_like_image(ref)
    _similar_color_different_structure(other)
    score = ic.image_similarity(ref, Image.open(other))
    assert score < 90


def test_manifest_hash_and_url_roundtrip(tmp_path):
    from xhgan.core import image_collector as ic

    local = tmp_path / "raw" / "red_mite" / "a.jpg"
    local.parent.mkdir(parents=True)
    _image(local)
    ic.append_manifest(
        root=tmp_path,
        local_path=local,
        class_id=5,
        keyword="柑橘红蜘蛛",
        source_url="https://example.com/a.jpg",
        source_page="https://example.com",
        width=800,
        height=480,
        sha256="abc",
        similarity=95.5,
    )
    assert "abc" in ic.load_manifest_hashes(tmp_path)
    assert "https://example.com/a.jpg" in ic.load_manifest_urls(tmp_path)


def test_collect_candidate_without_reference_or_size_limit(tmp_path, monkeypatch):
    from xhgan.core import image_collector as ic

    raw_img = tmp_path / "tiny.jpg"
    _image(raw_img, size=(120, 80))
    raw = raw_img.read_bytes()
    monkeypatch.setattr(ic, "_download", lambda _url: raw)

    result = ic.collect_candidate(
        ic.CandidateImage("https://example.com/tiny.jpg"),
        keyword="廉江红橙 红蜘蛛",
        root=tmp_path,
    )

    assert result.saved is True
    assert result.width == 120
    assert result.local_path is not None
    assert result.local_path.exists()
    assert result.local_path.parent.name.startswith("search_")


def test_parse_bing_image_urls_from_html_entities():
    from xhgan.core import image_collector as ic

    direct = "https://example.com/image-a.jpg"
    media = "https://example.com/image-b.jpg"
    encoded_media = quote(media, safe="")
    page = (
        '<a class="iusc" m="{&quot;purl&quot;:&quot;https://example.com/page&quot;,'
        f'&quot;murl&quot;:&quot;{direct}&quot;}}"></a>'
        f'<a href="/images/search?view=detailV2&amp;mediaurl={encoded_media}&amp;expw=800"></a>'
    )

    urls = [candidate.url for candidate in ic._parse_bing_image_urls(page)]

    assert direct in urls
    assert media in urls


def test_parse_google_image_urls_from_payload():
    from xhgan.core import image_collector as ic

    direct = "https://example.com/orange-leaf.jpg"
    escaped = "https:\\/\\/example.com\\/orange-fruit.webp"
    page = (
        f'AF_initDataCallback({{"ou":"{direct}"}});'
        f'["{escaped}",800,600]'
        'imgurl=https%3A%2F%2Fexample.com%2Forange-flower.png&imgrefurl='
    )

    urls = [candidate.url for candidate in ic._parse_google_image_urls(page)]

    assert direct in urls
    assert "https://example.com/orange-fruit.webp" in urls
    assert "https://example.com/orange-flower.png" in urls


def test_search_images_merges_engines_and_dedupes(monkeypatch):
    from xhgan.core import image_collector as ic

    monkeypatch.setattr(
        ic,
        "search_bing_images",
        lambda *_args, **_kwargs: [
            ic.CandidateImage("https://example.com/lianjiang-orange-a.jpg", title="廉江红橙"),
            ic.CandidateImage("https://example.com/lianjiang-orange-shared.jpg", title="廉江红橙"),
        ],
    )
    monkeypatch.setattr(
        ic,
        "search_google_images",
        lambda *_args, **_kwargs: [
            ic.CandidateImage("https://example.com/lianjiang-orange-shared.jpg", title="廉江红橙"),
            ic.CandidateImage("https://example.com/lianjiang-orange-b.jpg", title="廉江红橙"),
        ],
    )
    monkeypatch.setattr(
        ic,
        "search_baidu_images",
        lambda *_args, **_kwargs: [
            ic.CandidateImage("https://example.com/lianjiang-orange-b.jpg", title="廉江红橙"),
            ic.CandidateImage("https://example.com/lianjiang-orange-c.jpg", title="廉江红橙"),
        ],
    )

    urls = [candidate.url for candidate in ic.search_images("廉江红橙", engine="all")]

    assert urls == [
        "https://example.com/lianjiang-orange-a.jpg",
        "https://example.com/lianjiang-orange-shared.jpg",
        "https://example.com/lianjiang-orange-b.jpg",
        "https://example.com/lianjiang-orange-c.jpg",
    ]


def test_search_images_filters_unrelated_chinese_candidates(monkeypatch):
    from xhgan.core import image_collector as ic

    monkeypatch.setattr(
        ic,
        "search_bing_images",
        lambda *_args, **_kwargs: [ic.CandidateImage("https://example.com/dress.jpg", title="red orange dress")],
    )

    assert ic.search_images("廉江红橙", engine="bing") == []


def test_parse_baidu_image_urls_from_json():
    from xhgan.core import image_collector as ic

    page = (
        '{"data":['
        '{"thumbURL":"https://example.com/thumb.jpg","middleURL":"https://example.com/middle.webp"},'
        '{"replaceUrl":[{"ObjURL":"https%3A%2F%2Fexample.com%2Foriginal.png"}]}'
        ']}'
    )

    urls = [candidate.url for candidate in ic._parse_baidu_image_urls(page)]

    assert "https://example.com/thumb.jpg" in urls
    assert "https://example.com/middle.webp" in urls
    assert "https://example.com/original.png" in urls


def test_parse_google_async_image_urls():
    from xhgan.core import image_collector as ic

    page = (
        r')]}\' {"ischj":{"results":"[{\"tu\":\"https://encrypted-tbn0.gstatic.com/images?q\\u003dtbn:abc\\u0026s\",'
        r'\"ru\":\"https://example.com/page\"}]"} }'
    )

    urls = [candidate.url for candidate in ic._parse_google_async_image_urls(page)]

    assert "https://encrypted-tbn0.gstatic.com/images?q=tbn:abc&s" in urls


def test_dataset_raw_images_include_class_subdirs(tmp_path):
    from xhgan.core import dataset_manager as dm

    img = tmp_path / "dataset" / "raw" / "red_mite" / "a.jpg"
    img.parent.mkdir(parents=True)
    _image(img)
    images = dm.list_raw_images(tmp_path / "dataset")
    assert img in images
    assert dm.label_path_for_image(img, tmp_path / "dataset") == img.with_suffix(".txt")
