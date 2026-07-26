"""
Servidor local para el launcher tactil del HiFi.
Implementa WebSockets y APIs de Biblioteca Nativa (Kodi + Spotify).
"""

import eventlet
eventlet.monkey_patch()

import os
import json
import threading
import time
import sys
import subprocess
import requests
import websocket
from urllib.parse import quote

from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_socketio import SocketIO

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

app_config = load_config()

KODI_HOST = app_config.get("KODI_HOST") or os.environ.get("KODI_HOST", "localhost")
KODI_PORT = app_config.get("KODI_PORT") or os.environ.get("KODI_PORT", "8080")
KODI_RPC_URL = f"http://{KODI_HOST}:{KODI_PORT}/jsonrpc"
KODI_WS_URL = f"ws://{KODI_HOST}:9090/jsonrpc"

app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

sp_oauth = None
last_playback_state = None

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
            scope="user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative user-library-read",
            cache_path=os.path.join(APP_DIR, ".spotify-cache"),
            open_browser=False,
        )
    else:
        sp_oauth = None

init_spotify()


# ---------- KODI JSON-RPC ----------

def kodi_rpc(method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params
    try:
        r = requests.post(KODI_RPC_URL, json=payload, timeout=2)
        return r.json().get("result")
    except Exception:
        return None

def get_kodi_state():
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
        art = "/api/art?path=" + quote(thumb, safe="")
    return {
        "source": "kodi",
        "playing": bool(props and props.get("speed", 0) != 0),
        "title": info.get("title") or info.get("label") or "Pista sin titulo",
        "artist": ", ".join(info.get("artist", [])) or "CD / biblioteca local",
        "album": info.get("album", ""),
        "art": art,
        "progress": (props or {}).get("percentage", 0),
    }


# ---------- SPOTIFY API ----------

def get_spotify_state():
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


# ---------- EMISION DE ESTADO (SOCKETIO) ----------

def emit_playback_update():
    global last_playback_state
    state = get_kodi_state() or get_spotify_state()
    if not state:
        state = {"source": None, "playing": False, "title": "", "artist": "", "album": "", "art": None, "progress": 0}
    
    # Send only if state has meaningful changes (or just send every time event triggers)
    socketio.emit("playback_update", state)
    last_playback_state = state


# ---------- HILOS DE BACKGROUND (WEBSOCKETS + POLLING) ----------

def kodi_ws_thread():
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect(KODI_WS_URL, timeout=3)
            # Fetch initial state
            eventlet.spawn(emit_playback_update)
            while True:
                msg = ws.recv()
                if msg:
                    data = json.loads(msg)
                    method = data.get("method", "")
                    if method.startswith("Player.On") or method == "Playlist.OnAdd":
                        eventlet.spawn(emit_playback_update)
        except Exception:
            time.sleep(5) # Reconnect loop if Kodi is down

def spotify_polling_thread():
    while True:
        try:
            if sp_oauth and (not last_playback_state or last_playback_state.get("source") != "kodi"):
                # Poll spotify every 3s to not abuse API
                state = get_spotify_state()
                if state:
                    socketio.emit("playback_update", state)
        except Exception:
            pass
        time.sleep(3)


# ---------- RUTAS Y APIS (FRONTEND + CONTROL) ----------

@app.route("/")
def index():
    return send_from_directory(APP_DIR, "index.html")

@app.route("/api/now-playing")
def now_playing():
    state = get_kodi_state() or get_spotify_state()
    if not state:
        state = {"source": None, "playing": False, "title": "", "artist": "", "album": "", "art": None, "progress": 0}
    return jsonify(state)

@app.route("/api/art")
def art_proxy():
    path = request.args.get("path", "")
    img_url = f"http://{KODI_HOST}:{KODI_PORT}/image/{path}"
    try:
        r = requests.get(img_url, timeout=3)
        return r.content, r.status_code, {"Content-Type": r.headers.get("Content-Type", "image/jpeg")}
    except Exception:
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
        try:
            import webview
            if webview.windows: webview.windows[0].toggle_fullscreen()
        except: pass
    elif action == "exit":
        try:
            import webview
            if webview.windows: webview.windows[0].destroy()
        except: pass
    elif action == "shutdown":
        os.system("shutdown /s /t 0" if sys.platform == "win32" else "sudo shutdown -h now")
    elif action == "restart":
        os.system("shutdown /r /t 0" if sys.platform == "win32" else "sudo shutdown -r now")
    return jsonify({"ok": True})

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    global app_config, KODI_HOST, KODI_PORT, KODI_RPC_URL, KODI_WS_URL
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        app_config.update(data)
        save_config(app_config)
        
        KODI_HOST = app_config.get("KODI_HOST", KODI_HOST)
        KODI_PORT = app_config.get("KODI_PORT", KODI_PORT)
        KODI_RPC_URL = f"http://{KODI_HOST}:{KODI_PORT}/jsonrpc"
        KODI_WS_URL = f"ws://{KODI_HOST}:9090/jsonrpc"
        init_spotify()
        return jsonify({"ok": True})
    return jsonify({
        "SPOTIFY_CLIENT_ID": app_config.get("SPOTIFY_CLIENT_ID", ""),
        "SPOTIFY_CLIENT_SECRET": app_config.get("SPOTIFY_CLIENT_SECRET", ""),
        "KODI_HOST": app_config.get("KODI_HOST", KODI_HOST),
        "KODI_PORT": app_config.get("KODI_PORT", KODI_PORT)
    })

# ---------- APIS DE BIBLIOTECA NATIVA ----------

@app.route("/api/library/kodi/artists")
def kodi_artists():
    res = kodi_rpc("AudioLibrary.GetArtists", {"properties": ["thumbnail"]})
    return jsonify(res.get("artists", []) if res else [])

@app.route("/api/library/kodi/albums")
def kodi_albums():
    artist_id = request.args.get("artist_id", type=int)
    params = {"properties": ["thumbnail", "year", "artist"]}
    if artist_id is not None:
        params["filter"] = {"artistid": artist_id}
    res = kodi_rpc("AudioLibrary.GetAlbums", params)
    return jsonify(res.get("albums", []) if res else [])

@app.route("/api/library/kodi/songs")
def kodi_songs():
    album_id = request.args.get("album_id", type=int)
    params = {"properties": ["duration", "track", "thumbnail"]}
    if album_id is not None:
        params["filter"] = {"albumid": album_id}
    res = kodi_rpc("AudioLibrary.GetSongs", params)
    return jsonify(res.get("songs", []) if res else [])

@app.route("/api/library/kodi/directory")
def kodi_directory():
    path = request.args.get("path", "sources://music/")
    res = kodi_rpc("Files.GetDirectory", {"directory": path, "media": "music", "properties": ["thumbnail", "file", "mimetype"]})
    return jsonify(res.get("files", []) if res else [])

@app.route("/api/library/kodi/play", methods=["POST"])
def kodi_play():
    body = request.get_json(force=True) or {}
    item = {}
    if "songid" in body: item["songid"] = body["songid"]
    elif "albumid" in body: item["albumid"] = body["albumid"]
    elif "file" in body: item["file"] = body["file"]
    
    # Clear playlist and play item
    kodi_rpc("Playlist.Clear", {"playlistid": 0})
    kodi_rpc("Playlist.Add", {"playlistid": 0, "item": item})
    kodi_rpc("Player.Open", {"item": {"playlistid": 0}})
    return jsonify({"ok": True})

@app.route("/api/library/spotify/playlists")
def spot_playlists():
    if not sp_oauth: return jsonify([])
    token_info = sp_oauth.get_cached_token()
    if not token_info: return jsonify([])
    sp = spotipy.Spotify(auth=token_info["access_token"])
    try:
        res = sp.current_user_playlists()
        return jsonify(res.get("items", []))
    except:
        return jsonify([])

@app.route("/api/library/spotify/play", methods=["POST"])
def spot_play():
    body = request.get_json(force=True) or {}
    context_uri = body.get("context_uri")
    if not sp_oauth or not context_uri: return jsonify({"ok": False})
    token_info = sp_oauth.get_cached_token()
    sp = spotipy.Spotify(auth=token_info["access_token"])
    try:
        sp.start_playback(context_uri=context_uri)
    except: pass
    return jsonify({"ok": True})

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
    eventlet.spawn(kodi_ws_thread)
    eventlet.spawn(spotify_polling_thread)

    try:
        import webview
        WEBVIEW_AVAILABLE = True
    except ImportError:
        WEBVIEW_AVAILABLE = False

    def start_webview():
        time.sleep(1) # wait for server
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

    if WEBVIEW_AVAILABLE and "--no-window" not in sys.argv:
        threading.Thread(target=start_webview, daemon=True).start()

    # Flask-SocketIO usa eventlet bajo el capó gracias al async_mode="eventlet"
    print("Servidor corriendo en http://localhost:5005")
    socketio.run(app, host="0.0.0.0", port=5005, debug=False, use_reloader=False)
