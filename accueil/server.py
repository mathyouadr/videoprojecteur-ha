"""Page d'accueil du vidéoprojecteur : relaie quelques données de Home Assistant.

Bibliothèque standard uniquement. Le token HA reste côté serveur : la page ne
voit que /api/data (lecture seule, entités fixées ci-dessous) et /cover.

Variables d'environnement :
  HA_URL    (défaut http://192.168.1.3:8123)
  HA_TOKEN  token longue durée Home Assistant (obligatoire)
  PORT      (défaut 8099)
  TODO      entités todo.* séparées par des virgules
"""
import json
import os
import urllib.error
import urllib.request
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HA_URL = os.environ.get("HA_URL", "http://192.168.1.3:8123").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
PORT = int(os.environ.get("PORT", "8099"))

WEATHER = "weather.forecast_maison"
# Listes de tâches, séparées par des virgules (Google Tasks, Todoist…).
TODO = [t.strip() for t in os.environ.get("TODO", "todo.inbox").split(",") if t.strip()]
MUSIC = "media_player.spotify_math"

STATIC = Path(__file__).with_name("static")


def ha(path, body=None):
    req = urllib.request.Request(
        HA_URL + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.read(), r.headers.get_content_type()


def ha_json(path, body=None):
    return json.loads(ha(path, body)[0])


def section(fn):
    """Une source en panne ne doit pas vider toute la page."""
    try:
        return fn()
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        return {"erreur": type(e).__name__}


def weather():
    cur = ha_json(f"/api/states/{WEATHER}")
    fc = ha_json("/api/services/weather/get_forecasts?return_response",
                 {"entity_id": WEATHER, "type": "daily"})
    days = fc["service_response"][WEATHER]["forecast"][:4]
    return {
        "etat": cur["state"],
        "temperature": cur["attributes"].get("temperature"),
        "jours": [{"date": d["datetime"][:10], "etat": d["condition"],
                   "max": d.get("temperature"), "min": d.get("templow")} for d in days],
    }


def tasks():
    res = ha_json("/api/services/todo/get_items?return_response",
                  {"entity_id": TODO, "status": "needs_action"})
    today = date.today().isoformat()
    items = [i for lst in res["service_response"].values() for i in lst["items"]]
    # Tâches du jour = en retard, du jour, ou sans échéance.
    keep = [i for i in items if not i.get("due") or i["due"][:10] <= today]
    return [{"titre": i["summary"], "echeance": (i.get("due") or "")[:10]} for i in keep]


def music():
    a = ha_json(f"/api/states/{MUSIC}")
    at = a["attributes"]
    return {"etat": a["state"], "titre": at.get("media_title"),
            "artiste": at.get("media_artist"), "pochette": bool(at.get("entity_picture"))}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(STATIC), **kw)

    def send_body(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/data":
            data = {"meteo": section(weather), "taches": section(tasks), "musique": section(music)}
            return self.send_body(200, json.dumps(data, ensure_ascii=False).encode(), "application/json")
        if self.path.startswith("/cover"):
            try:
                pic = ha_json(f"/api/states/{MUSIC}")["attributes"]["entity_picture"]
                body, ctype = ha(pic)
                return self.send_body(200, body, ctype)
            except (urllib.error.URLError, OSError, KeyError):
                return self.send_body(404, b"", "text/plain")
        return super().do_GET()

    def log_message(self, fmt, *args):  # pas de journal par requête (rafraîchissement chaque minute)
        pass


if __name__ == "__main__":
    if not HA_TOKEN:
        raise SystemExit("HA_TOKEN manquant")
    print(f"Accueil projecteur sur http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
