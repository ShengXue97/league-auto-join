"""System tray icon (next to the clock) for League Remote."""

import webbrowser


def make_icon(icon_path, local_url, version, startup_on, startup_toggle, update_info, on_quit, update_now=None):
    """Build the tray icon. Call .run() on the main thread; .stop() removes it.
    startup_on() -> bool, startup_toggle(), update_info() -> {"version", "url", "state", "progress"} or None,
    update_now() starts the one-click update (None: just open the release page)."""
    import pystray
    from PIL import Image

    def open_page(icon, item):
        webbrowser.open(local_url)

    def open_setup(icon, item):
        webbrowser.open(local_url + "/setup")

    def update_text(item):
        info = update_info() or {}
        if info.get("state") == "downloading":
            return f"Downloading v{info.get('version')}… {info.get('progress', 0)}%"
        if info.get("state") == "installing":
            return f"Installing v{info.get('version')}…"
        if info.get("state") == "error":
            return f"Update failed - click to retry (v{info.get('version')})"
        return f"Update now to v{info.get('version', '')}" if update_now else f"Update available: v{info.get('version', '')}"

    def do_update(icon, item):
        info = update_info()
        if not info:
            return
        if update_now:
            update_now()
        else:
            webbrowser.open(info["url"])

    def toggle_startup(icon, item):
        startup_toggle()
        icon.update_menu()

    def quit_app(icon, item):
        icon.visible = False
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Open League Remote", open_page, default=True),  # also on double-click
        pystray.MenuItem("Phone setup (QR codes)", open_setup),
        pystray.MenuItem(update_text, do_update, visible=lambda item: bool(update_info())),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", toggle_startup, checked=lambda item: startup_on()),
        pystray.MenuItem(f"League Remote v{version}", None, enabled=False),
        pystray.MenuItem("Quit", quit_app),
    )
    return pystray.Icon("LeagueRemote", Image.open(icon_path), "League Remote", menu)
