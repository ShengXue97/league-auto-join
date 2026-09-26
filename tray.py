"""System tray icon (next to the clock) for League Remote."""

import webbrowser


def make_icon(icon_path, local_url, version, startup_on, startup_toggle, update_info, on_quit):
    """Build the tray icon. Call .run() on the main thread; .stop() removes it.
    startup_on() -> bool, startup_toggle(), update_info() -> {"version", "url"} or None."""
    import pystray
    from PIL import Image

    def open_page(icon, item):
        webbrowser.open(local_url)

    def open_setup(icon, item):
        webbrowser.open(local_url + "/setup")

    def open_update(icon, item):
        info = update_info()
        if info:
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
        pystray.MenuItem(lambda item: f"Update available: v{(update_info() or {}).get('version', '')}",
                         open_update, visible=lambda item: bool(update_info())),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start with Windows", toggle_startup, checked=lambda item: startup_on()),
        pystray.MenuItem(f"League Remote v{version}", None, enabled=False),
        pystray.MenuItem("Quit", quit_app),
    )
    return pystray.Icon("LeagueRemote", Image.open(icon_path), "League Remote", menu)
