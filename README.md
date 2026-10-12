<p align="center">
  <img src="assets/logo.svg" alt="Stream Anything Server logo" width="120" />
</p>

<h1 align="center">Stream Anything Server</h1>

<p align="center">
  Share video folders from your computer with the <b>Stream Anything</b> app on your phone, tablet, and
  Google TV, over your home Wi-Fi. No cloud, no account, nothing to install on your devices.
</p>

<p align="center">
  <a href="https://github.com/wwwescape/stream-anything-server/releases"><img src="https://img.shields.io/github/v/release/wwwescape/stream-anything-server.svg?style=flat-square" alt="GitHub release" /></a>
  <a href="https://github.com/wwwescape/stream-anything-server/commits/master"><img src="https://img.shields.io/github/last-commit/wwwescape/stream-anything-server.svg?style=flat-square" alt="GitHub last commit" /></a>
  <a href="https://github.com/wwwescape/stream-anything-server"><img src="https://img.shields.io/github/languages/code-size/wwwescape/stream-anything-server.svg?color=red&style=flat-square" alt="GitHub code size" /></a>
</p>

## Features

- **Share several folders** — list each folder you want to share (e.g. `D:/Movies`, your Downloads,
  an external drive) as a named library, so videos scattered across your computer are reachable
  without sharing a whole drive.
- **Videos only** — only video files and folders are listed and served (MP4, MKV, WebM, MOV, AVI,
  TS and more); hidden and system files are skipped.
- **Seeking** — supports HTTP range requests, so you can skip around a film instantly.
- **Browse from your phone** — open the printed address in your phone's browser to browse your
  folders; tap a video to play it, or long-press it to copy its link to the clipboard and paste
  it into Stream Anything.
- **Found automatically** — announces itself on your network (mDNS), so the Stream Anything app
  can find it without you typing an IP address.
- **Private by default** — every request needs the server's access key, only devices on your home
  network are allowed in, and nothing outside your shared folders can be reached.

## How It Works

Run the server on the computer that has your videos. It prints a link like:

```
http://192.168.0.140:8090/?key=Xy7…
```

Each video then has its own link, built from the library name and the file's path inside it:

| File on the computer | Link |
|---|---|
| `D:\Movies\Inception.mkv` (library `Movies` → `D:/Movies`) | `http://192.168.0.140:8090/media/Movies/Inception.mkv?key=…` |
| `C:\Users\Alex\Downloads\Holiday 2025\beach.mp4` (library `Downloads`) | `http://192.168.0.140:8090/media/Downloads/Holiday%202025/beach.mp4?key=…` |

You don't need to build these by hand: the browse page and the JSON API hand them out ready to
paste.

> **Stream Anything support:** Stream Anything plays these links in versions after v0.0.1. The
> app accepts plain `http://` only for home-network IP addresses and stays HTTPS-only everywhere
> else. Paste a link into the app, or share it to the app from the phone's browser.

## Getting Started

Four steps: install once, list the folders you want to share, start the server, then open the
printed link on your phone. The commands below are for Windows; on macOS/Linux use `python3` and
`.venv/bin/` instead of `python` and `.venv/Scripts/`.

### 1. Install (once)

1. Install [Python 3.13 or newer](https://www.python.org/downloads/).
2. Download or clone this repository, open a terminal in its folder, and run:

   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install .
   ```

### 2. Choose the folders to share

The folders to share are set in a file called **`config.toml`** in the server's folder.

1. Copy `config.example.toml` to `config.toml` (same folder).
2. Open `config.toml` in a text editor (e.g. Notepad). Add one `[[libraries]]` block per folder,
   and delete the example blocks you don't need:

   ```toml
   [server]
   name = "Living Room PC"   # optional: the name shown in the app
   port = 8090               # optional

   [[libraries]]
   name = "Movies"           # appears in the app and in links
   path = "D:/Movies"        # the folder on this computer

   [[libraries]]
   name = "TV Shows"
   path = "E:/TV Shows"

   [[libraries]]
   name = "Downloads"
   path = "C:/Users/Alex/Downloads"
   ```

   - **`path`** is the folder to share. Everything inside it, including subfolders, is shared;
     nothing outside it is. Use **forward slashes** (`D:/Movies`), or single quotes if you paste
     a path with backslashes (`path = 'D:\Movies'`). Double quotes with backslashes
     (`"D:\Movies"`) don't work, because TOML treats `\` as an escape character there.
   - **`name`** is how the folder appears in the app. Use letters, digits, spaces, `.`, `_` or
     `-`, and give each folder a different name.
   - You need **at least one** `[[libraries]]` block, and every folder must exist, otherwise the
     server stops with an error explaining what to fix.
3. Save the file.

**Changing folders later:** edit `config.toml`, then stop the server (Ctrl+C or close its window)
and start it again. Changes are only read at startup. Files you add *inside* an already shared
folder show up straight away, without a restart.

### 3. Start the server

Double-click **`start-server.cmd`**. It runs the server with the `config.toml` in the same
folder. Or, from a terminal in the server's folder:

```bash
.venv/Scripts/stream-anything-server --config config.toml
```

(`--config` can point to a config file anywhere; the access key is saved next to it.)

The first time, Windows Firewall asks whether to allow it. Allow **Private networks** only.

When it's running, you'll see something like:

```
Stream Anything Server 0.0.1 - Living Room PC

Shared libraries:
  Movies           D:\Movies
  TV Shows         E:\TV Shows
  Downloads        C:\Users\Alex\Downloads

Open on your phone's browser (same Wi-Fi) to browse and copy video links:
  http://192.168.0.140:8090/?key=Xy7...

Access key: Xy7...   (kept in access_key.txt)
Delete that file and restart to issue a new key (old links stop working).

Press Ctrl+C to stop.
```

Keep this window open while you watch. **To stop the server**, press Ctrl+C or close the window.

### 4. Connect

On your phone, tablet or TV (on the same Wi-Fi), open the `http://…/?key=…` link printed above to
browse your folders, or let the Stream Anything app find the server automatically.

The access key is generated on first start and saved in `access_key.txt` next to `config.toml`.
Delete that file and restart to issue a new key (old links stop working).

### Troubleshooting

- **The window closes or shows `Error: …` straight away:** read the message. It usually means
  `config.toml` is missing, a folder in `path` doesn't exist (check the spelling and slashes), or
  a library name is used twice or has unsupported characters.
- **`Not installed yet`** when double-clicking `start-server.cmd`: run step 1 first.
- **The phone can't open the link:** make sure it's on the same Wi-Fi, and that the firewall
  prompt was answered with *Private networks* allowed (and that Windows treats your Wi-Fi as a
  private network).
- **Automatic discovery doesn't work** and the server prints *"Couldn't announce on the network
  (mDNS)"*: your PC's security policy may be blocking `zeroconf`'s compiled module. Reinstall it
  as pure Python, then restart:

  ```bash
  SKIP_CYTHON=1 .venv/Scripts/python -m pip install --force-reinstall --no-deps --no-binary zeroconf zeroconf
  ```

  Everything else works without discovery: use the printed address instead.

## Configuration

All settings in `config.toml` (see [config.example.toml](config.example.toml)). Restart the server
after changing them.

| Setting | Default | What it does |
|---|---|---|
| `server.name` | the computer's name | Shown in the app and on the browse page. |
| `server.port` | `8090` | The port to listen on. |
| `[[libraries]]` `name` / `path` | — | One block per shared folder. The name appears in links (letters, digits, spaces, `.`, `_`, `-`). At least one is required. |
| `media.extra_video_extensions` | `[]` | Extra file extensions to treat as videos. |

Tips:
- **Reserve a fixed IP** for the computer in your router, so links keep working.
- **The computer must stay awake** while you watch.

## Privacy & Security

- **No cloud:** nothing leaves your home network. The server has no account, no analytics, and
  makes no outbound connections.
- **Home network only:** requests from public addresses are refused. VPN addresses like
  Tailscale's (`100.64.0.0/10`) are also refused, so a misconfigured port forward can't expose
  your files.
- **Access key on every request:** without it, nothing is listed or served. The key is never
  included in the network announcement.
- **Read-only, inside your folders only:** `..`, absolute paths, and symlinks or junctions that
  point outside a shared folder are refused. Only video files are served.
- **Plain HTTP:** traffic isn't encrypted, as is usual on a home network. Anyone who can see your
  Wi-Fi traffic could see the key; only use it on a network you trust.

## Development

### Prerequisites

- Python 3.13+

### Run from source

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/stream-anything-server --config config.toml
```

### API

All endpoints except `/health` need the key as `?key=…` or an `X-Access-Key` header.

| Endpoint | Returns |
|---|---|
| `GET /health` | `{"status", "name", "version"}` |
| `GET /api/v1/libraries` | Shared libraries, each with a `browse_url` |
| `GET /api/v1/browse/{library}/{path}` | A folder's subfolders (`browse_url`) and videos (`media_url`, `size`), plus `parent_browse_url` |
| `GET /media/{library}/{path}` | The video file, with range support |
| `GET /`, `GET /browse/{library}/{path}` | The same listings as web pages |

The server announces itself as `_streamanymedia._tcp` with TXT records `name`, `version`, and
`api`.

### Test

```bash
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
.venv/Scripts/python -m pytest
```

### Project layout

```
app/
  cli.py        Command-line entry point: load config, print connection info, run
  config.py     config.toml loading and the access key
  main.py       FastAPI app: guard (home network + key), API, media, browse pages
  library.py    Safe path resolution inside a shared folder, and folder listings
  security.py   Home-network ranges and key checks
  discovery.py  mDNS announcement and LAN address detection
  web.py        Browse page HTML
tests/          pytest suite
assets/         README assets (the Stream Anything logo)
```

## License

GPL-3.0 — see [LICENSE](LICENSE).

## Support

If you find Stream Anything Server useful, consider buying me a coffee:

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="40" />](https://buymeacoffee.com/wwwescape)
