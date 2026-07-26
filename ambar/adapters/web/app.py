from dataclasses import asdict

from flask import Flask, jsonify, redirect, request, send_from_directory


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

    @app.route("/api/library/spotify/play", methods=["POST"])
    def spotify_play():
        body = request.get_json(force=True) or {}
        ok = container.library_service.spotify_play(body.get("context_uri"))
        return jsonify({"ok": ok})

    # ---------- autenticacion Spotify ----------

    @app.route("/login")
    def login():
        url = container.spotify_gateway.get_authorize_url()
        if not url:
            return "Configura SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET en Ajustes antes de usar esto."
        return redirect(url)

    @app.route("/callback")
    def callback():
        code = request.args.get("code")
        if container.spotify_gateway.exchange_code(code):
            return "Spotify autorizado correctamente. Ya puedes cerrar esta pestana o recargar el kiosko."
        return "Falta configurar Spotify o no se recibio el codigo de autorizacion."

    return app
