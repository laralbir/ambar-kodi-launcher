"""
Servidor local para el launcher tactil del HiFi.

Sirve index.html y expone una API que unifica el estado de
reproduccion de Kodi y de Spotify, para que el navegador del
kiosko solo tenga que hablar con este servidor (evita problemas
de CORS al llamar directamente a Kodi o a Spotify desde el HTML).

INSTALACION
    pip install flask requests spotipy

CONFIGURACION DE SPOTIFY (opcional, solo si quieres ver el
"ahora suena" y los controles tambien para Spotify):
    1. Crea una app en https://developer.spotify.com/dashboard
    2. Anade como Redirect URI: http://localhost:5005/callback
    3. Define estas variables de entorno antes de arrancar:
         SPOTIFY_CLIENT_ID=xxxx
         SPOTIFY_CLIENT_SECRET=xxxx
    4. La primera vez, abre http://localhost:5005/login una vez
       desde un navegador con sesion en tu cuenta de Spotify para
       autorizar la app (solo hace falta una vez, el token se cachea).

Si no configuras Spotify, el launcher sigue funcionando solo con
Kodi (biblioteca FLAC/MP3/CD): el panel de Spotify simplemente no
mostrara datos hasta que lo configures.

ARRANQUE
    python kiosk_server.py
Luego abre http://localhost:5005 en el navegador del kiosko.
"""

import os
import threading
from flask import Flask, jsonify, request, send_from_directory, redirect
import requests

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

APP_DIR = os.path.dirname(os.path.abspath(__file__))
KODI_HOST = os.environ.get("KODI_HOST", "localhost")
KODI_PORT = os.environ.get("KODI_PORT", "8080")
KODI_RPC_URL = f"http://{KODI_HOST}:{KODI_PORT}/jsonrpc"

app = Flask(__name__)

sp_oauth = None
if SPOTIPY_AVAILABLE and os.environ.get("SPOTIFY_CLIENT_ID"):
    sp_oauth = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:5005/callback"),
        scope="user-read-playback-state user-modify-playback-state",
        cache_path=os.path.join(APP_DIR, ".spotify-cache"),
        open_browser=False,
    )


# ---------- Kodi ----------

def kodi_rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params
    try:
        r = requests.post(KODI_RPC_URL, json=payload, timeout=1.5)
        return r.json().get("result")
    except requests.RequestException:
        return None


def kodi_now_playing():
    players = kodi_rpc("Player.GetActivePlayers")
    if not players:
        return None
    player_id = players[0]["playerid"]
    item = kodi_rpc("Player.GetItem", {
        "playerid": player_id,
        "properties": ["title", "artist", "album", "thumbnail"],
    })
    props = kodi_rpc("Player.GetProperties", {
        "playerid": player_id,
        "properties": ["percentage", "speed"],
    })
    if not item or "item" not in item:
        return None
    info = item["item"]
    art = None
    thumb = info.get("thumbnail")
    if thumb:
        art = "/api/art?path=" + requests.utils.quote(thumb, safe="")
    return {
        "source": "kodi",
        "playing": bool(props and props.get("speed", 0) != 0),
        "title": info.get("title") or info.get("label") or "Pista sin titulo",
        "artist": ", ".join(info.get("artist", [])) or "CD / biblioteca local",
        "album": info.get("album", ""),
        "art": art,
        "progress": (props or {}).get("percentage", 0),
    }


# ---------- Spotify ----------

def spotify_now_playing():
    if not sp_oauth:
        return None
    token_info = sp_oauth.get_cached_token()
    if not token_info:
        return None
    sp = spotipy.Spotify(auth=token_info["access_token"])
    try:
        current = sp.current_playback()
    except Exception:
        return None
    if not current or not current.get("item"):
        return None
    item = current["item"]
    images = item.get("album", {}).get("images", [])
    duration = item.get("duration_ms") or 1
    return {
        "source": "spotify",
        "playing": current.get("is_playing", False),
        "title": item.get("name", ""),
        "artist": ", ".join(a["name"] for a in item.get("artists", [])),
        "album": item.get("album", {}).get("name", ""),
        "art": images[0]["url"] if images else None,
        "progress": int(100 * current.get("progress_ms", 0) / duration),
    }


# ---------- Rutas ----------

@app.route("/")
def index():
    return send_from_directory(APP_DIR, "index.html")


@app.route("/api/now-playing")
def now_playing():
    data = kodi_now_playing() or spotify_now_playing()
    if not data:
        data = {"source": None, "playing": False, "title": "", "artist": "",
                 "album": "", "art": None, "progress": 0}
    return jsonify(data)


@app.route("/api/art")
def art_proxy():
    path = request.args.get("path", "")
    img_url = f"http://{KODI_HOST}:{KODI_PORT}/image/{path}"
    try:
        r = requests.get(img_url, timeout=3)
        return r.content, r.status_code, {"Content-Type": r.headers.get("Content-Type", "image/jpeg")}
    except requests.RequestException:
        return "", 404


@app.route("/api/control", methods=["POST"])
def control():
    body = request.get_json(force=True) or {}
    action = body.get("action")
    source = body.get("source")

    if source == "kodi":
        players = kodi_rpc("Player.GetActivePlayers")
        if players:
            pid = players[0]["playerid"]
            if action == "playpause":
                kodi_rpc("Player.PlayPause", {"playerid": pid})
            elif action == "next":
                kodi_rpc("Player.GoTo", {"playerid": pid, "to": "next"})
            elif action == "previous":
                kodi_rpc("Player.GoTo", {"playerid": pid, "to": "previous"})

    elif source == "spotify" and sp_oauth:
        token_info = sp_oauth.get_cached_token()
        if token_info:
            sp = spotipy.Spotify(auth=token_info["access_token"])
            try:
                if action == "playpause":
                    playback = sp.current_playback()
                    if playback and playback.get("is_playing"):
                        sp.pause_playback()
                    else:
                        sp.start_playback()
                elif action == "next":
                    sp.next_track()
                elif action == "previous":
                    sp.previous_track()
            except Exception:
                pass

    return jsonify({"ok": True})


@app.route("/login")
def login():
    if not sp_oauth:
        return "Configura SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET antes de usar esto."
    return redirect(sp_oauth.get_authorize_url())


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if sp_oauth and code:
        sp_oauth.get_access_token(code, as_dict=False)
        return "Spotify autorizado correctamente. Ya puedes cerrar esta pestana."
    return "Falta configurar Spotify o no se recibio el codigo de autorizacion."


if __name__ == "__main__":
    import sys
    try:
        import webview
        WEBVIEW_AVAILABLE = True
    except ImportError:
        WEBVIEW_AVAILABLE = False

    # Arrancar Flask en un hilo en segundo plano
    server_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": 5005, "debug": False, "use_reloader": False}
    )
    server_thread.daemon = True
    server_thread.start()

    if WEBVIEW_AVAILABLE and "--no-window" not in sys.argv:
        # Iniciar la ventana nativa apuntando a Flask
        webview.create_window(
            title="Ámbar",
            url="http://localhost:5005",
            width=1920,
            height=720,
            frameless=True,
            fullscreen=False, # Si prefieres que ocupe todo sin respetar resolución, cambia a True
            background_color="#17181a"
        )
        webview.start()
    else:
        print("Servidor corriendo en http://localhost:5005 (sin ventana nativa).")
        server_thread.join()
