"""The /setup page: QR codes to connect a phone in under a minute."""

import html
import json
import urllib.parse

import segno

PLAY_STORE = "https://play.google.com/store/apps/details?id=io.heckel.ntfy"
APP_STORE = "https://apps.apple.com/us/app/ntfy/id1625396347"
RIOT_NOTICE = ("League Remote isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games "
               "or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all "
               "associated properties are trademarks or registered trademarks of Riot Games, Inc.")


def json_str(v):
    """Safe JavaScript string literal inside an HTML <script>."""
    return json.dumps(v).replace("<", "\\u003c")


def qr(data):
    return segno.make(data, error="m").svg_inline(scale=5, dark="#010a13", light="#f0e6d2", border=3)


def public_networks():
    """Names of connected networks Windows treats as Public (the phone often can't connect then)."""
    try:
        import autostart
        out = autostart.powershell("Get-NetConnectionProfile | Where-Object NetworkCategory -eq 'Public' "
                                   "| ForEach-Object { $_.Name }")
        return [n for n in out.splitlines() if n.strip()]
    except Exception:
        return []


def network_warning(names):
    if not names:
        return ""
    e = html.escape
    return f"""<div class="card warn">
    <h2>⚠ Your Wi-Fi is set to "Public"</h2>
    <div>Windows treats <b>{e(", ".join(names))}</b> as a public network, so your phone probably can't reach League Remote.
    If this is your home Wi-Fi, set it to <b>Private</b>:</div>
    <ol><li>Open <b>Settings → Network &amp; internet → Wi-Fi</b></li>
      <li>Click <b>{e(names[0])}</b> (or <b>Properties</b>)</li>
      <li>Under <b>Network profile type</b>, choose <b>Private network</b></li></ol>
    <div class="muted">Only do this for your own home network, never for café or school Wi-Fi.</div>
  </div>"""


def subscribe_links(cfg):
    server = cfg["ntfy_server"].rstrip("/")
    host = server.split("://", 1)[-1]
    topic = cfg["ntfy_topic"]
    q = urllib.parse.quote
    path = f"{host}/{q(topic)}?display={q('League Remote')}"
    # ntfy deep link (docs.ntfy.sh, Android). Phone cameras often won't open it from a QR code, and some
    # browsers block it, so on Android we use an intent link: Chrome opens the ntfy app (package
    # io.heckel.ntfy) or, if it isn't installed, the Play Store.
    deep = f"ntfy://{path}"
    intent = (f"intent://{path}#Intent;scheme=ntfy;package=io.heckel.ntfy;"
              f"S.browser_fallback_url={q(PLAY_STORE, safe='')};end")
    return topic, deep, intent


def render_subscribe(cfg):
    """/subscribe - opened on the phone by scanning the QR code."""
    topic, deep, intent = subscribe_links(cfg)
    e = html.escape
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Subscribe to League Remote alerts</title>
<link rel="icon" href="/assets/icon.png">
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#010a13; color:#f0e6d2; font-family:system-ui,-apple-system,"Segoe UI",sans-serif; padding:24px 18px; }}
  .wrap {{ max-width:460px; margin:0 auto; text-align:center; }}
  img {{ width:72px; height:72px; }}
  h1 {{ color:#c8aa6e; font-size:24px; margin:10px 0 6px; }}
  p, li {{ color:#a09b8c; line-height:1.5; }}
  .btn {{ display:block; width:100%; margin:14px 0; padding:18px; border-radius:10px; border:2px solid #0ac8b9; background:#0ac8b922;
          color:#f0e6d2; font:inherit; font-size:19px; font-weight:800; text-decoration:none; cursor:pointer; }}
  .alt {{ border-color:#c8aa6e; background:#c8aa6e22; }}
  .ok {{ border-color:#0acb6e; background:#0acb6e33; }}
  code {{ display:inline-block; background:#1e2328; color:#c8aa6e; padding:8px 12px; border-radius:6px; font-size:18px;
          word-break:break-all; user-select:all; -webkit-user-select:all; }}
  ol {{ text-align:left; padding-left:22px; }}
  a {{ color:#0ac8b9; }}
  [hidden] {{ display:none !important; }}
</style></head><body><div class="wrap">
<img src="/assets/icon.png" alt="">
<h1>Get League Remote alerts</h1>
<p>1. Install the free <b>ntfy</b> app:
  <a href="{PLAY_STORE}">Google Play</a> · <a href="{APP_STORE}">App Store</a></p>

<div id="auto">
  <p>2. Then tap:</p>
  <a class="btn" id="sub" href="{e(deep)}">Subscribe in ntfy</a>
  <p>Didn't open ntfy? Add it by hand instead:</p>
</div>
<div id="manual-title" hidden><p>2. Copy your topic, then add it in ntfy:</p></div>

<p><code id="topic">{e(topic)}</code></p>
<button class="btn alt" id="copy" type="button">Copy topic</button>
<ol><li>Open <b>ntfy</b> and tap <b>+</b></li>
  <li>Paste the topic (keep the server as <b>ntfy.sh</b>) and tap <b>Subscribe</b></li></ol>
<p style="font-size:13px">Keep the topic private: anyone who knows it can see your alerts.</p>
</div>
<script>
const ua = navigator.userAgent;
const android = /Android/i.test(ua);
const ios = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
if (android) document.getElementById("sub").href = {json_str(intent)};  // opens the app, or the Play Store
if (ios) {{  // ntfy only documents subscribe links for Android: go straight to the copy steps
  document.getElementById("auto").hidden = true;
  document.getElementById("manual-title").hidden = false;
}}

// navigator.clipboard only works on https pages; this page is http on your home Wi-Fi,
// so fall back to the older copy command, which works there on Android and iPhone.
function legacyCopy(text) {{
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;font-size:16px";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  ta.setSelectionRange(0, text.length);  // iPhone needs an explicit range
  let ok = false;
  try {{ ok = document.execCommand("copy"); }} catch (e) {{ ok = false; }}
  ta.remove();
  return ok;
}}
async function copyText(text) {{
  if (navigator.clipboard && window.isSecureContext) {{
    try {{ await navigator.clipboard.writeText(text); return true; }} catch (e) {{ /* fall back */ }}
  }}
  return legacyCopy(text);
}}
const btn = document.getElementById("copy");
btn.onclick = async () => {{
  const ok = await copyText(document.getElementById("topic").textContent.trim());
  btn.textContent = ok ? "Copied!" : "Couldn't copy - long-press the topic above";
  btn.classList.toggle("ok", ok);
  clearTimeout(btn._t);
  btn._t = setTimeout(() => {{ btn.textContent = "Copy topic"; btn.classList.remove("ok"); }}, 2500);
}};
</script>
</body></html>"""


def render(cfg, control_url, version):
    server = cfg["ntfy_server"].rstrip("/")
    host = server.split("://", 1)[-1]
    topic = cfg["ntfy_topic"]
    # Android ntfy app: this link opens the app and subscribes (docs.ntfy.sh "deep linking")
    e = html.escape
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>League Remote setup</title>
<link rel="icon" href="/assets/icon.png">
<style>
  :root {{ --bg:#010a13; --panel:#0a1428; --gold:#c8aa6e; --gold-dim:#785a28; --text:#f0e6d2; --muted:#a09b8c; --blue:#0ac8b9; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,"Segoe UI",sans-serif; padding:24px 16px 40px; }}
  .wrap {{ max-width:980px; margin:0 auto; }}
  header {{ display:flex; align-items:center; gap:16px; margin-bottom:22px; }}
  header img {{ width:64px; height:64px; }}
  h1 {{ margin:0; font-size:26px; color:var(--gold); }}
  .muted {{ color:var(--muted); font-size:14px; }}
  .steps {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; }}
  .card {{ background:var(--panel); border:1px solid var(--gold-dim); border-radius:12px; padding:18px; }}
  .n {{ display:inline-grid; place-items:center; width:28px; height:28px; border-radius:50%; background:var(--gold); color:var(--bg); font-weight:800; margin-right:8px; }}
  h2 {{ font-size:18px; margin:0 0 10px; display:flex; align-items:center; }}
  .qr {{ display:flex; justify-content:center; margin:14px 0 8px; }}
  .qr svg {{ border-radius:8px; max-width:100%; height:auto; }}
  code {{ background:#1e2328; padding:3px 7px; border-radius:5px; color:var(--gold); word-break:break-all; font-size:15px; }}
  a {{ color:var(--blue); }}
  .btn {{ display:inline-block; margin-top:8px; padding:12px 16px; border-radius:8px; border:2px solid var(--blue); background:#0ac8b922;
          color:var(--text); font:inherit; font-weight:700; cursor:pointer; text-decoration:none; }}
  .stores a {{ display:inline-block; margin:4px 10px 0 0; }}
  footer {{ margin-top:28px; color:var(--muted); font-size:12px; line-height:1.5; }}
  #testmsg {{ margin-top:8px; }}
  .tray {{ display:flex; gap:16px; align-items:flex-start; margin-top:16px; }}
  .tray img {{ width:56px; height:56px; flex:none; }}
  .warn {{ border-color:#f0b232; margin-bottom:16px; }}
  .warn h2 {{ color:#f0b232; }}
  ol {{ margin:10px 0; padding-left:22px; line-height:1.7; }}
</style></head>
<body><div class="wrap">
<header>
  <img src="/assets/icon.png" alt="">
  <div><h1>Set up your phone</h1><div class="muted">League Remote v{e(version)} is running on this PC. Your phone must be on the same Wi-Fi.</div></div>
</header>
{network_warning(public_networks())}
<div class="steps">
  <div class="card">
    <h2><span class="n">1</span>Get the ntfy app</h2>
    <div class="muted">Free app that shows League Remote's alerts (match found, your turn, game over).</div>
    <div class="stores"><a href="{PLAY_STORE}" target="_blank" rel="noopener">Google Play</a><a href="{APP_STORE}" target="_blank" rel="noopener">App Store</a></div>
  </div>
  <div class="card">
    <h2><span class="n">2</span>Subscribe to your alerts</h2>
    <div class="qr">{qr(control_url + "/subscribe")}</div>
    <div class="muted">Scan with your phone camera: it opens a page with a <b>Subscribe in ntfy</b> button.<br>
      Or open ntfy, tap <b>+</b> and enter this topic:</div>
    <p><code>{e(topic)}</code></p>
    <div class="muted">Keep the topic private: anyone who knows it can see your alerts.</div>
    <button class="btn" id="test">Send a test alert</button>
    <div class="muted" id="testmsg"></div>
  </div>
  <div class="card">
    <h2><span class="n">3</span>Open the control page</h2>
    <div class="qr">{qr(control_url)}</div>
    <div class="muted">Scan with your phone camera, then use <b>Add to Home Screen</b> so it opens like an app.</div>
    <p><code>{e(control_url)}</code></p>
    <div class="muted">If it doesn't load: make sure the phone is on the same Wi-Fi, and allow League Remote for
      <b>Private networks</b> if Windows Firewall asks.</div>
  </div>
</div>
<div class="card tray">
  <img src="/assets/icon.png" alt="">
  <div>
    <h2>Where's League Remote on my PC?</h2>
    <div class="muted" style="color:var(--text)">It has no window: it runs in the <b>notification area</b> next to the clock,
      as this <b>gold bell</b>. Right-click it to open the control page, this setup page, turn <b>Start with Windows</b>
      on or off, or quit.</div>
    <div class="muted" style="margin-top:6px">Don't see it? Click the <b>^</b> arrow next to the clock. Drag the bell onto the
      taskbar to keep it visible. You can also start it again from the Start menu: <b>League Remote</b>.</div>
  </div>
</div>
<footer>
  League Remote only reads data the League client and game already show you, and only acts when you tap a button.
  It never reads game memory or sends keyboard/mouse input.<br><br>{e(RIOT_NOTICE)}
</footer>
</div>
<script>
document.getElementById("test").onclick = async () => {{
  const m = document.getElementById("testmsg");
  try {{
    const r = await fetch("/api/test-notification", {{ method: "POST" }});
    m.textContent = r.ok ? "Sent! It should arrive on your phone within a few seconds." : "Couldn't send it.";
  }} catch (e) {{ m.textContent = "Couldn't reach League Remote."; }}
}};
</script>
</body></html>"""
