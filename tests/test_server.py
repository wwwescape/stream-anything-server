from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Config, ConfigError, Library, load_config, load_or_create_key
from app.main import create_app
from app.security import is_home_network

KEY = "test-key-0123456789"
VIDEO_BYTES = bytes(range(256)) * 40  # 10 KB of known content


@pytest.fixture
def tree(tmp_path: Path) -> dict[str, Path]:
    movies = tmp_path / "Movies"
    (movies / "Holiday 2025").mkdir(parents=True)
    (movies / "Holiday 2025" / "beach day.mp4").write_bytes(VIDEO_BYTES)
    (movies / "film.mkv").write_bytes(b"mkv")
    (movies / "notes.txt").write_text("not a video")
    (movies / ".hidden").mkdir()
    (movies / ".hidden" / "secret.mp4").write_bytes(b"x")
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    return {"movies": movies, "outside": outside, "root": tmp_path}


def make_client(
    tree: dict[str, Path], local_only: bool = False, client_ip: str = "192.168.1.50"
) -> TestClient:
    config = Config(
        name="Test Laptop",
        port=8090,
        libraries=(Library("Movies", tree["movies"].resolve()),),
        access_key=KEY,
        local_only=local_only,
    )
    return TestClient(create_app(config), client=(client_ip, 50000))


def test_health_needs_no_key(tree):
    response = make_client(tree).get("/health")
    assert response.status_code == 200
    assert response.json()["name"] == "Test Laptop"


@pytest.mark.parametrize("key", [None, "wrong", KEY[:-1]])
def test_everything_else_needs_the_key(tree, key):
    params = {"key": key} if key else {}
    client = make_client(tree)
    for path in ("/", "/api/v1/libraries", "/api/v1/browse/Movies", "/media/Movies/film.mkv"):
        assert client.get(path, params=params).status_code == 401, path


def test_key_works_as_query_or_header(tree):
    client = make_client(tree)
    assert client.get("/api/v1/libraries", params={"key": KEY}).status_code == 200
    assert client.get("/api/v1/libraries", headers={"X-Access-Key": KEY}).status_code == 200


def test_only_home_network_clients_are_served(tree):
    assert make_client(tree, local_only=True, client_ip="192.168.1.50").get("/health").status_code == 200
    assert make_client(tree, local_only=True, client_ip="10.0.0.7").get("/health").status_code == 200
    assert make_client(tree, local_only=True, client_ip="203.0.113.9").get("/health").status_code == 403
    assert make_client(tree, local_only=True, client_ip="100.101.102.103").get("/health").status_code == 403


def test_home_network_ranges():
    for host in (
        "192.168.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "172.31.255.255",
        "127.0.0.1",
        "::1",
        "fd00::1",
        "::ffff:192.168.1.2",
    ):
        assert is_home_network(host), host
    for host in ("8.8.8.8", "172.32.0.1", "100.64.0.1", "2001:db8::1", "testclient", "", None):
        assert not is_home_network(host), host


def test_browse_lists_folders_and_videos_only(tree):
    data = make_client(tree).get("/api/v1/browse/Movies", params={"key": KEY}).json()
    names = [(e["name"], e["type"]) for e in data["entries"]]
    assert names == [("Holiday 2025", "folder"), ("film.mkv", "video")]  # no .txt, no hidden folder
    assert data["parent_browse_url"] is None
    video = data["entries"][1]
    assert video["media_url"] == f"http://testserver/media/Movies/film.mkv?key={KEY}"


def test_browse_subfolder_with_spaces(tree):
    client = make_client(tree)
    data = client.get("/api/v1/browse/Movies/Holiday 2025", params={"key": KEY}).json()
    assert data["path"] == "Holiday 2025"
    entry = data["entries"][0]
    assert entry["name"] == "beach day.mp4"
    assert entry["size"] == len(VIDEO_BYTES)
    assert entry["media_url"] == f"http://testserver/media/Movies/Holiday%202025/beach%20day.mp4?key={KEY}"
    assert data["parent_browse_url"] == f"http://testserver/api/v1/browse/Movies?key={KEY}"


def test_media_supports_range_requests_for_seeking(tree):
    client = make_client(tree)
    full = client.get("/media/Movies/Holiday 2025/beach day.mp4", params={"key": KEY})
    assert full.status_code == 200
    assert full.content == VIDEO_BYTES
    assert full.headers["content-type"] == "video/mp4"

    part = client.get(
        "/media/Movies/Holiday 2025/beach day.mp4", params={"key": KEY}, headers={"Range": "bytes=100-199"}
    )
    assert part.status_code == 206
    assert part.content == VIDEO_BYTES[100:200]
    assert part.headers["content-range"] == f"bytes 100-199/{len(VIDEO_BYTES)}"


@pytest.mark.parametrize(
    "path",
    [
        "/media/Movies/../outside.mp4",
        "/media/Movies/%2e%2e/outside.mp4",
        "/media/Movies/..%2Foutside.mp4",
        "/media/Movies/notes.txt",
        "/media/Movies/missing.mp4",
        "/media/Movies/C:/Windows/win.ini",
        "/media/Nope/film.mkv",
        "/api/v1/browse/Movies/..",
        "/api/v1/browse/Movies/film.mkv",
    ],
)
def test_nothing_outside_the_shared_folders_or_non_videos(tree, path):
    response = make_client(tree).get(path, params={"key": KEY})
    assert response.status_code in (404, 400), path


def test_symlink_out_of_the_library_is_refused(tree):
    link = tree["movies"] / "escape.mp4"
    try:
        os.symlink(tree["outside"], link)
    except (OSError, NotImplementedError):
        pytest.skip("creating symlinks needs extra privileges on this system")
    assert make_client(tree).get("/media/Movies/escape.mp4", params={"key": KEY}).status_code == 404


def test_browse_page_escapes_names(tree):
    (tree["movies"] / "<script>x.mp4").write_bytes(b"x") if os.name != "nt" else None
    page = make_client(tree).get("/browse/Movies", params={"key": KEY})
    assert page.status_code == 200
    assert "<script>x" not in page.text
    assert "Holiday 2025" in page.text


def test_browse_page_marks_videos_for_long_press_copy(tree):
    page = make_client(tree).get("/browse/Movies", params={"key": KEY}).text
    assert "<a class='video' href='" in page and "film.mkv" in page
    assert "id='toast'" in page and "execCommand" in page
    # Only videos get long-press-to-copy; folders stay plain links.
    assert page.count("class='video'") == 1


def test_responses_are_not_cached(tree):
    response = make_client(tree).get("/api/v1/libraries", params={"key": KEY})
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_config_loading(tmp_path: Path, tree):
    config_file = tmp_path / "config.toml"
    movies = tree["movies"].as_posix()
    config_file.write_text(
        f'[server]\nname = "Laptop"\nport = 9000\n\n[[libraries]]\nname = "Movies"\npath = "{movies}"\n'
    )
    config = load_config(config_file)
    assert config.port == 9000 and config.library("movies").root == tree["movies"].resolve()
    # The key is created once and then reused.
    assert len(config.access_key) >= 16
    assert load_config(config_file).access_key == config.access_key


@pytest.mark.parametrize(
    "body",
    [
        "",  # no libraries
        '[[libraries]]\nname = "../x"\npath = "."\n',
        '[[libraries]]\nname = "Movies"\npath = "Z:/definitely/not/here"\n',
        '[[libraries]]\nname = "A"\npath = "."\n[[libraries]]\nname = "a"\npath = "."\n',
        '[server]\nport = 70000\n[[libraries]]\nname = "A"\npath = "."\n',
        '[[libraries]]\nname = "A"\npath = "D:\\Downloads\\Videos"\n',  # backslashes in a "string"
    ],
)
def test_bad_configs_are_rejected(tmp_path: Path, body):
    config_file = tmp_path / "config.toml"
    config_file.write_text(body.replace('path = "."', f'path = "{tmp_path.as_posix()}"'))
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_short_or_missing_key_file_is_regenerated(tmp_path: Path):
    key_file = tmp_path / "access_key.txt"
    key_file.write_text("short")
    key = load_or_create_key(key_file)
    assert key != "short" and len(key) >= 16
