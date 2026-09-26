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
    return segno.make(data, error="m").svg_inline(scale=5, dark="#0a0d13", light="#ffffff", border=3)


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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{ --bg:#0a0d13; --surface:#11161f; --surface-2:#171e2a; --surface-3:#1f2837; --line:rgba(255,255,255,.07);
           --line-2:rgba(255,255,255,.12); --text:#e8ecf2; --text-2:#a3adbb; --text-3:#6e7888; --gold:#d9b56c;
           --gold-soft:rgba(217,181,108,.14); --accent:#2ccfbd; --accent-ink:#052521; --accent-soft:rgba(44,207,189,.13);
           --good:#3ddc97; --good-soft:rgba(61,220,151,.13); --warn:#f5b94a; --warn-soft:rgba(245,185,74,.13); }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
         -webkit-font-smoothing:antialiased; }}
  a {{ color:var(--accent); text-decoration:none; }}
  b {{ font-weight:600; }}
  [hidden] {{ display:none !important; }}
  .btn {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:48px; padding:0 18px; border-radius:12px;
         border:1px solid transparent; background:var(--surface-3); color:var(--text); font-family:inherit; font-size:15.5px; font-weight:600;
         cursor:pointer; text-decoration:none; transition:transform .08s, background .15s; }}
  .btn:active {{ transform:scale(.98); }}
  .btn.primary {{ background:var(--accent); color:var(--accent-ink); }}
  .btn.ghost {{ background:transparent; border-color:var(--line-2); }}
  .btn.ok {{ background:var(--good-soft); color:var(--good); border-color:rgba(61,220,151,.35); }}
  .btn.block {{ width:100%; }}
  code {{ background:var(--surface-3); color:var(--gold); padding:6px 10px; border-radius:8px; font:600 15px ui-monospace,SFMono-Regular,Consolas,monospace;
          word-break:break-all; user-select:all; -webkit-user-select:all; }}
  body {{ padding:28px 18px calc(32px + env(safe-area-inset-bottom)); }}
  .wrap {{ max-width:440px; margin:0 auto; }}
  .top {{ text-align:center; margin-bottom:18px; }}
  .top img {{ width:64px; height:64px; border-radius:16px; }}
  h1 {{ font-size:23px; font-weight:800; letter-spacing:-.02em; margin:12px 0 4px; }}
  .lead {{ color:var(--text-2); margin:0; }}
  .step {{ background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:18px; margin-top:12px; }}
  .step h2 {{ display:flex; align-items:center; gap:10px; font-size:16px; font-weight:700; margin:0 0 10px; }}
  .step h2 .n {{ width:26px; height:26px; border-radius:8px; display:grid; place-items:center; background:var(--gold-soft); color:var(--gold); font-size:13px; font-weight:800; flex:none; }}
  .step p, .step li {{ color:var(--text-2); margin:0; }}
  .step .btn {{ margin-top:12px; }}
  .stores {{ display:flex; gap:8px; margin-top:12px; }}
  .stores .btn {{ flex:1; margin:0; }}
  .topic {{ display:flex; justify-content:center; margin:14px 0 2px; }}
  ol {{ padding-left:20px; margin:12px 0 0; line-height:1.7; }}
  .fine {{ color:var(--text-3); font-size:12.5px; margin-top:10px; }}
  #testmsg {{ min-height:1.2em; margin-top:10px !important; font-size:14px; }}
</style></head><body><div class="wrap">
<div class="top">
  <img src="/assets/icon.png" alt="">
  <h1>Get League Remote alerts</h1>
  <p class="lead">Match found, your turn, game over: straight to your phone.</p>
</div>

<div class="step">
  <h2><span class="n">1</span>Install the free ntfy app</h2>
  <p>It shows League Remote's alerts.</p>
  <div class="stores"><a class="btn ghost" href="{PLAY_STORE}">Google Play</a><a class="btn ghost" href="{APP_STORE}">App Store</a></div>
</div>

<div class="step">
  <h2><span class="n">2</span>Subscribe to your alerts</h2>
  <div id="auto">
    <a class="btn primary block" id="sub" href="{e(deep)}">Subscribe in ntfy</a>
    <p class="fine">Didn't open ntfy? Copy your topic and add it by hand:</p>
  </div>
  <p id="manual-title" hidden>Copy your topic, then add it in ntfy:</p>
  <div class="topic"><code id="topic">{e(topic)}</code></div>
  <button class="btn ghost block" id="copy" type="button">Copy topic</button>
  <ol><li>Open <b>ntfy</b> and tap <b>+</b></li>
    <li>Paste the topic (keep the server as <b>ntfy.sh</b>) and tap <b>Subscribe</b></li></ol>
  <p class="fine">Keep the topic private: anyone who knows it can see your alerts.</p>
</div>

<div class="step">
  <h2><span class="n">3</span>Check it works</h2>
  <p>Sends an alert to your phone right now.</p>
  <button class="btn ghost block" id="test" type="button">Send a test alert</button>
  <p id="testmsg"></p>
</div>

<div class="step">
  <h2><span class="n">4</span>You're set</h2>
  <p id="homescreen">Tip: add League Remote to your home screen so it opens like an app.</p>
  <a class="btn primary block" href="/">Open League Remote</a>
</div>
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
document.getElementById("homescreen").innerHTML = ios
  ? "Tip: tap <b>Share</b> → <b>Add to Home Screen</b> after you open it, so it opens like an app."
  : android ? "Tip: tap <b>⋮</b> → <b>Add to Home screen</b> after you open it, so it opens like an app."
  : "Tip: add it to your home screen so it opens like an app.";

document.getElementById("test").onclick = async () => {{
  const m = document.getElementById("testmsg");
  m.textContent = "Sending…";
  try {{
    const r = await fetch("/api/test-notification", {{ method: "POST" }});
    m.textContent = r.ok ? "Sent! It should pop up within a few seconds. Nothing? Check that you subscribed to the topic above."
                         : "Couldn't send it - try again.";
  }} catch (e) {{ m.textContent = "Couldn't reach your PC - is your phone on the same Wi-Fi?"; }}
}};

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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{ --bg:#0a0d13; --surface:#11161f; --surface-2:#171e2a; --surface-3:#1f2837; --line:rgba(255,255,255,.07);
           --line-2:rgba(255,255,255,.12); --text:#e8ecf2; --text-2:#a3adbb; --text-3:#6e7888; --gold:#d9b56c;
           --gold-soft:rgba(217,181,108,.14); --accent:#2ccfbd; --accent-ink:#052521; --accent-soft:rgba(44,207,189,.13);
           --good:#3ddc97; --good-soft:rgba(61,220,151,.13); --warn:#f5b94a; --warn-soft:rgba(245,185,74,.13); }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
         -webkit-font-smoothing:antialiased; }}
  a {{ color:var(--accent); text-decoration:none; }}
  b {{ font-weight:600; }}
  [hidden] {{ display:none !important; }}
  .btn {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:48px; padding:0 18px; border-radius:12px;
         border:1px solid transparent; background:var(--surface-3); color:var(--text); font-family:inherit; font-size:15.5px; font-weight:600;
         cursor:pointer; text-decoration:none; transition:transform .08s, background .15s; }}
  .btn:active {{ transform:scale(.98); }}
  .btn.primary {{ background:var(--accent); color:var(--accent-ink); }}
  .btn.ghost {{ background:transparent; border-color:var(--line-2); }}
  .btn.ok {{ background:var(--good-soft); color:var(--good); border-color:rgba(61,220,151,.35); }}
  .btn.block {{ width:100%; }}
  code {{ background:var(--surface-3); color:var(--gold); padding:6px 10px; border-radius:8px; font:600 15px ui-monospace,SFMono-Regular,Consolas,monospace;
          word-break:break-all; user-select:all; -webkit-user-select:all; }}
  body {{ padding:32px 20px 48px; }}
  .wrap {{ max-width:1000px; margin:0 auto; }}
  header {{ display:flex; align-items:center; gap:16px; margin-bottom:24px; flex-wrap:wrap; }}
  header img {{ width:56px; height:56px; border-radius:14px; }}
  h1 {{ margin:0; font-size:26px; font-weight:800; letter-spacing:-.02em; }}
  .muted {{ color:var(--text-2); font-size:14px; }}
  .steps {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; }}
  .card {{ background:var(--surface); border:1px solid var(--line); border-radius:18px; padding:20px; }}
  .n {{ display:inline-grid; place-items:center; width:26px; height:26px; border-radius:8px; background:var(--gold-soft); color:var(--gold);
       font-size:13px; font-weight:800; margin-right:10px; flex:none; }}
  h2 {{ font-size:17px; font-weight:700; margin:0 0 10px; display:flex; align-items:center; }}
  .qr {{ display:flex; justify-content:center; margin:16px 0 10px; }}
  .qr svg {{ border-radius:12px; max-width:100%; height:auto; }}
  .stores {{ display:flex; gap:8px; margin-top:12px; }}
  .stores a {{ flex:1; }}
  footer {{ margin-top:30px; color:var(--text-3); font-size:12px; line-height:1.6; }}
  #testmsg {{ margin-top:10px; }}
  .tray {{ display:flex; gap:16px; align-items:flex-start; margin-top:16px; }}
  .tray img {{ width:52px; height:52px; border-radius:13px; flex:none; }}
  .warn {{ border-color:rgba(245,185,74,.35); background:linear-gradient(0deg, var(--warn-soft), var(--warn-soft)), var(--surface); margin-bottom:16px; }}
  .warn h2 {{ color:var(--warn); }}
  ol {{ margin:10px 0; padding-left:22px; line-height:1.8; color:var(--text-2); }}
  ol b {{ color:var(--text); }}
</style></head>
<body><div class="wrap">
<header>
  <img src="/assets/icon.png" alt="">
  <div><h1>Set up your phone</h1><div class="muted">League Remote v{e(version)} is running on this PC. Your phone must be on the same Wi-Fi.</div></div>
  <a class="btn primary" href="/" style="margin-left:auto">Open League Remote</a>
</header>
{network_warning(public_networks())}
<div class="steps">
  <div class="card">
    <h2><span class="n">1</span>Get the ntfy app</h2>
    <div class="muted">Free app that shows League Remote's alerts (match found, your turn, game over).</div>
    <div class="stores"><a class="btn ghost" href="{PLAY_STORE}" target="_blank" rel="noopener">Google Play</a><a class="btn ghost" href="{APP_STORE}" target="_blank" rel="noopener">App Store</a></div>
  </div>
  <div class="card">
    <h2><span class="n">2</span>Subscribe to your alerts</h2>
    <div class="qr">{qr(control_url + "/subscribe")}</div>
    <div class="muted">Scan with your phone camera: it opens a page with a <b>Subscribe in ntfy</b> button.<br>
      Or open ntfy, tap <b>+</b> and enter this topic:</div>
    <p><code>{e(topic)}</code></p>
    <div class="muted">Keep the topic private: anyone who knows it can see your alerts.</div>
    <button class="btn ghost" id="test" style="margin-top:12px">Send a test alert</button>
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
