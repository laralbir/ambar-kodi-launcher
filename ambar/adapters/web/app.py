from dataclasses import asdict

from flask import Flask, jsonify, redirect, request, send_from_directory


def _auth_page(heading: str, message: str, ok: bool) -> str:
    """Pagina standalone (se ve desde el navegador del movil/PC que autoriza
    Spotify, no dentro del launcher) con la misma estetica ambar/gunmetal del
    resto de la app, en vez de una respuesta de texto plano."""
    accent = "#ffb020" if ok else "#e65a5a"
    icon = "✓" if ok else "✕"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ámbar — Spotify</title>
<style>
  body{{margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:#17181a; color:#f2ede4; font-family:-apple-system,'Inter',sans-serif; padding:2rem;
    box-sizing:border-box; text-align:center;}}
  .card{{max-width:420px;}}
  .icon{{width:64px; height:64px; border-radius:50%; border:2px solid {accent}; color:{accent};
    display:flex; align-items:center; justify-content:center; font-size:2rem; margin:0 auto 1.2rem;}}
  h1{{font-family:'Oswald',sans-serif; text-transform:uppercase; letter-spacing:0.04em;
    font-size:1.3rem; margin:0 0 0.8rem; color:{accent};}}
  p{{color:#9a9a9e; line-height:1.5; margin:0;}}
</style></head>
<body><div class="card">
  <div class="icon">{icon}</div>
  <h1>{heading}</h1>
  <p>{message}</p>
</div></body></html>"""


def create_app(container) -> Flask:
    """Adapter HTTP: define las rutas Flask y delega toda la logica en los
    servicios de aplicacion del container. No conoce Kodi ni Spotify."""
    app = Flask(__name__, static_folder=None)

    @app.route("/")
    def index():
        return send_from_directory(container.app_dir, "index.html")

    @app.route("/api/now-playing")
    def now_playing():
        return jsonify(asdict(container.now_playing_service.get_state()))

    @app.route("/api/now-playing/playlist")
    def now_playing_playlist():
        return jsonify(container.now_playing_service.get_playlist())

    @app.route("/api/now-playing/playlist/play", methods=["POST"])
    def now_playing_playlist_play():
        body = request.get_json(force=True) or {}
        container.playback_control_service.play_playlist_item(
            body.get("source"), body.get("position"), body.get("uri")
        )
        return jsonify({"ok": True})

    @app.route("/api/skins")
    def list_skins():
        return jsonify(container.skin_service.list_skins())

    @app.route("/skins/<path:filename>")
    def skins_static(filename):
        return send_from_directory(container.skins_dir, filename)

    @app.route("/api/art")
    def art_proxy():
        path = request.args.get("path", "")
        content, status, content_type = container.kodi_gateway.art_proxy(path)
        if content_type is None:
            return content, status
        return content, status, {"Content-Type": content_type}

    @app.route("/api/control", methods=["POST"])
    def control():
        body = request.get_json(force=True) or {}
        container.playback_control_service.execute(body.get("source"), body.get("action"))
        return jsonify({"ok": True})

    @app.route("/api/seek", methods=["POST"])
    def seek():
        body = request.get_json(force=True) or {}
        container.playback_control_service.seek(body.get("source"), body.get("percentage"))
        return jsonify({"ok": True})

    @app.route("/api/system/screens")
    def system_screens():
        return jsonify(container.available_screens)

    @app.route("/api/system/volume", methods=["GET", "POST"])
    def system_volume():
        if request.method == "POST":
            body = request.get_json(force=True) or {}
            if "level" in body:
                container.system_service.set_volume_level(body["level"])
            if "muted" in body:
                container.system_service.set_volume_muted(body["muted"])
            return jsonify({"ok": True})
        return jsonify(container.system_service.get_volume())

    @app.route("/api/system", methods=["POST"])
    def api_system():
        body = request.get_json(force=True) or {}
        container.system_service.execute(body.get("action"))
        return jsonify({"ok": True})

    @app.route("/api/config", methods=["GET", "POST"])
    def api_config():
        if request.method == "POST":
            data = request.get_json(force=True) or {}
            container.config_service.update(data)
            return jsonify({"ok": True})
        return jsonify(container.config_service.get_public())

    # ---------- biblioteca ----------

    @app.route("/api/library/kodi/status")
    def kodi_status():
        return jsonify(container.library_service.kodi_status())

    @app.route("/api/library/spotify/status")
    def spotify_status():
        return jsonify(container.library_service.spotify_status())

    @app.route("/api/library/kodi/artists")
    def kodi_artists():
        return jsonify(container.library_service.kodi_artists())

    @app.route("/api/library/kodi/albums")
    def kodi_albums():
        artist_id = request.args.get("artist_id", type=int)
        return jsonify(container.library_service.kodi_albums(artist_id))

    @app.route("/api/library/kodi/songs")
    def kodi_songs():
        album_id = request.args.get("album_id", type=int)
        return jsonify(container.library_service.kodi_songs(album_id))

    @app.route("/api/library/kodi/directory")
    def kodi_directory():
        path = request.args.get("path", "sources://music/")
        return jsonify(container.library_service.kodi_directory(path))

    @app.route("/api/library/kodi/cd-available")
    def kodi_cd_available():
        return jsonify(container.library_service.kodi_cd_status())

    @app.route("/api/library/kodi/play", methods=["POST"])
    def kodi_play():
        body = request.get_json(force=True) or {}
        container.library_service.kodi_play(body)
        return jsonify({"ok": True})

    @app.route("/api/library/spotify/playlists")
    def spotify_playlists():
        return jsonify(container.library_service.spotify_playlists())

    @app.route("/api/library/spotify/playlist-tracks")
    def spotify_playlist_tracks():
        playlist_id = request.args.get("playlist_id")
        return jsonify(container.library_service.spotify_playlist_tracks(playlist_id))

    @app.route("/api/library/spotify/play", methods=["POST"])
    def spotify_play():
        body = request.get_json(force=True) or {}
        ok = container.library_service.spotify_play(body.get("context_uri"))
        return jsonify({"ok": ok})

    @app.route("/api/library/spotify/play-track", methods=["POST"])
    def spotify_play_track():
        body = request.get_json(force=True) or {}
        ok = container.library_service.spotify_play_track(body.get("uri"))
        return jsonify({"ok": ok})

    # ---------- autenticacion Spotify ----------

    @app.route("/login")
    def login():
        url = container.spotify_gateway.get_authorize_url()
        if not url:
            return _auth_page(
                "Falta configurar Spotify",
                "Introduce el Client ID y el Client Secret en Ajustes del launcher (columna Configuración) y guarda antes de volver a intentarlo.",
                ok=False,
            )
        return redirect(url)

    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if container.spotify_gateway.exchange_code(code):
            return _auth_page(
                "Spotify autorizado",
                "Ya puedes cerrar esta pestaña. El launcher lo detectará solo en unos segundos.",
                ok=True,
            )
        return _auth_page(
            "No se pudo autorizar",
            "Falta configurar Spotify en Ajustes, o no se recibió el código de autorización de Spotify. Vuelve a intentarlo desde el launcher.",
            ok=False,
        )

    return app
