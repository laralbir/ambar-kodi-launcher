"""
Servidor local para el launcher tactil del HiFi.

Sirve index.html y expone una API que unifica el estado de
reproduccion de Kodi y de Spotify.
"""

import os
import json
import threading
import sys
import subprocess
from flask import Flask, jsonify, request, send_from_directory, redirect
import requests

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print("Error al guardar config:", e)

# Load configuration initially
app_config = load_config()

KODI_HOST = app_config.get("KODI_HOST") or os.environ.get("KODI_HOST", "localhost")
KODI_PORT = app_config.get("KODI_PORT") or os.environ.get("KODI_PORT", "8080")
KODI_RPC_URL = f"http://{KODI_HOST}:{KODI_PORT}/jsonrpc"

app = Flask(__name__)

sp_oauth = None

def init_spotify():
    global sp_oauth
    client_id = app_config.get("SPOTIFY_CLIENT_ID") or os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = app_config.get("SPOTIFY_CLIENT_SECRET") or os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = app_config.get("SPOTIFY_REDIRECT_URI") or os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:5005/callback")
    
    if SPOTIPY_AVAILABLE and client_id and client_secret:
        sp_oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state user-modify-playback-state",
            cache_path=os.path.join(APP_DIR, ".spotify-cache"),
            open_browser=False,
        )
    else:
        sp_oauth = None

init_spotify()


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

@app.route("/api/system", methods=["POST"])
def api_system():
    body = request.get_json(force=True) or {}
    action = body.get("action")
    
    if action == "fullscreen":
        import webview
        if webview.windows:
            webview.windows[0].toggle_fullscreen()
    elif action == "exit":
        import webview
        if webview.windows:
            webview.windows[0].destroy()
    elif action == "shutdown":
        if sys.platform == "win32":
            os.system("shutdown /s /t 0")
        else:
            os.system("sudo shutdown -h now")
    elif action == "restart":
        if sys.platform == "win32":
            os.system("shutdown /r /t 0")
        else:
            os.system("sudo shutdown -r now")
            
    return jsonify({"ok": True})

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    global app_config, KODI_HOST, KODI_PORT, KODI_RPC_URL
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        app_config.update(data)
        save_config(app_config)
        
        KODI_HOST = app_config.get("KODI_HOST", KODI_HOST)
        KODI_PORT = app_config.get("KODI_PORT", KODI_PORT)
        KODI_RPC_URL = f"http://{KODI_HOST}:{KODI_PORT}/jsonrpc"
        init_spotify()
        return jsonify({"ok": True})
    
    # Return config without secret tokens if preferred, but for this private UI it's fine
    return jsonify({
        "SPOTIFY_CLIENT_ID": app_config.get("SPOTIFY_CLIENT_ID", ""),
        "SPOTIFY_CLIENT_SECRET": app_config.get("SPOTIFY_CLIENT_SECRET", ""),
        "KODI_HOST": app_config.get("KODI_HOST", KODI_HOST),
        "KODI_PORT": app_config.get("KODI_PORT", KODI_PORT)
    })

@app.route("/login")
def login():
    if not sp_oauth:
        return "Configura SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET en Ajustes antes de usar esto."
    return redirect(sp_oauth.get_authorize_url())

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if sp_oauth and code:
        sp_oauth.get_access_token(code, as_dict=False)
        return "Spotify autorizado correctamente. Ya puedes cerrar esta pestana o recargar el kiosko."
    return "Falta configurar Spotify o no se recibio el codigo de autorizacion."


if __name__ == "__main__":
    try:
        import webview
        WEBVIEW_AVAILABLE = True
    except ImportError:
        WEBVIEW_AVAILABLE = False

    server_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": 5005, "debug": False, "use_reloader": False}
    )
    server_thread.daemon = True
    server_thread.start()

    if WEBVIEW_AVAILABLE and "--no-window" not in sys.argv:
        # Modo pantalla completa por defecto
        webview.create_window(
            title="Ámbar",
            url="http://localhost:5005",
            width=1920,
            height=720,
            frameless=True,
            fullscreen=True,
            background_color="#17181a"
        )
        webview.start()
    else:
        print("Servidor corriendo en http://localhost:5005 (sin ventana nativa).")
        server_thread.join()
