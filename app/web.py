"""The browse pages for a phone's browser: plain HTML with one small inline script, no external assets.

Folder and file names come from the disk and are escaped before going into the page. The script only
adds long-press-to-copy on video links; the pages work without it.
"""

from __future__ import annotations

from html import escape

_STYLE = """
:root { color-scheme: light dark; --accent: #2A7FFF; }
body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; max-width: 760px; margin-inline: auto; }
h1 { font-size: 1.4rem; margin: 8px 0 4px; }
p.hint { opacity: .7; margin: 0 0 16px; font-size: .9rem; }
nav a { color: var(--accent); text-decoration: none; }
ul { list-style: none; padding: 0; margin: 0; }
li a { display: flex; justify-content: space-between; gap: 12px; padding: 14px 16px; margin-bottom: 8px;
       border-radius: 16px; background: color-mix(in srgb, CanvasText 6%, Canvas); color: inherit;
       text-decoration: none; overflow-wrap: anywhere; }
li a:focus, li a:hover { outline: 2px solid var(--accent); }
.size { opacity: .6; white-space: nowrap; font-size: .9rem; }
/* Long-press copies the link (see _SCRIPT), so suppress the browser's own callout and text selection. */
a.video { -webkit-touch-callout: none; -webkit-user-select: none; user-select: none;
          transition: transform .15s; }
a.video.pressed { transform: scale(.97); outline: 2px solid var(--accent); }
#toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); padding: 10px 18px;
         border-radius: 20px; background: CanvasText; color: Canvas; opacity: 0; pointer-events: none;
         transition: opacity .2s; }
#toast.show { opacity: .9; }
"""

# Long-press (touch) on a video copies its link. The page is plain http:// on a home-network address,
# where navigator.clipboard isn't available, so fall back to execCommand("copy"), and if even that is
# refused, show the link in a prompt to copy by hand. The copy runs in touchend, which counts as a user
# gesture; the long-press timer alone wouldn't. Mouse right-click keeps the browser's own menu.
_SCRIPT = """
(() => {
  const toast = document.getElementById("toast");
  const show = (msg) => {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(show.timer);
    show.timer = setTimeout(() => toast.classList.remove("show"), 2000);
  };
  const legacyCopy = (text) => {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;top:0;left:0;opacity:0";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) {}
    area.remove();
    return ok;
  };
  const copy = (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(() => true, () => legacyCopy(text));
    }
    return Promise.resolve(legacyCopy(text));
  };
  for (const link of document.querySelectorAll("a.video")) {
    let timer, touching = false, long = false, x = 0, y = 0;
    const reset = () => { clearTimeout(timer); touching = false; link.classList.remove("pressed"); };
    link.addEventListener("touchstart", (e) => {
      touching = true;
      long = false;
      x = e.touches[0].clientX;
      y = e.touches[0].clientY;
      timer = setTimeout(() => { long = true; link.classList.add("pressed"); }, 500);
    }, { passive: true });
    link.addEventListener("touchmove", (e) => {
      if (Math.hypot(e.touches[0].clientX - x, e.touches[0].clientY - y) > 10) { clearTimeout(timer); }
    }, { passive: true });
    link.addEventListener("touchcancel", reset);
    link.addEventListener("touchend", (e) => {
      reset();
      if (!long) return;
      e.preventDefault();  // a long-press copies; it doesn't also open the video
      copy(link.href).then((ok) => ok ? show("Link copied") : window.prompt("Copy this link:", link.href));
    });
    link.addEventListener("contextmenu", (e) => { if (touching) e.preventDefault(); });
  }
})();
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='referrer' content='no-referrer'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head><body>{body}"
        f"<div id='toast' role='status' aria-live='polite'></div><script>{_SCRIPT}</script></body></html>"
    )


def _size(num: int | None) -> str:
    if num is None:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return ""


def render_libraries(server: str, libraries: list[tuple[str, str]]) -> str:
    items = "".join(f"<li><a href='{escape(href)}'>📁 {escape(name)}</a></li>" for name, href in libraries)
    return _page(
        server,
        f"<h1>{escape(server)}</h1>"
        "<p class='hint'>Shared with Stream Anything. Tap a video to play it, or long-press it to copy its "
        f"link to paste into the app.</p><ul>{items}</ul>",
    )


def render_listing(data: dict, home_url: str) -> str:
    crumbs = f"<a href='{escape(home_url)}'>{escape(data['server'])}</a> / {escape(data['library'])}"
    if data["path"]:
        crumbs += " / " + " / ".join(escape(part) for part in data["path"].split("/"))
    up = (
        f"<li><a href='{escape(data['parent_page_url'])}'>⬆️ ..</a></li>"
        if data["parent_page_url"]
        else f"<li><a href='{escape(home_url)}'>⬆️ ..</a></li>"
    )
    rows = []
    for entry in data["entries"]:
        if entry["type"] == "folder":
            rows.append(f"<li><a href='{escape(entry['page_url'])}'>📁 {escape(entry['name'])}</a></li>")
        else:
            rows.append(
                f"<li><a class='video' href='{escape(entry['media_url'])}'>🎬 {escape(entry['name'])}"
                f"<span class='size'>{_size(entry.get('size'))}</span></a></li>"
            )
    empty = "" if rows else "<p class='hint'>No videos or folders here.</p>"
    return _page(
        f"{data['library']} — {data['server']}",
        f"<nav>{crumbs}</nav><ul>{up}{''.join(rows)}</ul>{empty}",
    )
