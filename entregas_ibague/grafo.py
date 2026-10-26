"""Calles de Ibagué: descarga el mapa de OpenStreetMap y lo convierte en un grafo."""
import glob
import math
import os
import pickle
import shutil

from datos import CENTRO, MAX_SNAP_M, RADIO_M

CARPETA = os.path.dirname(os.path.abspath(__file__))        # carpeta donde está este archivo
ARCHIVO = os.path.join(CARPETA, "ibague_grafo_v4.pkl")      # el mapa guardado
SERVIDORES = [                                              # servidores de OpenStreetMap (se prueban en orden)
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def _buscar_guardado():
    """Si el mapa no está en esta carpeta, lo busca en carpetas vecinas (por ejemplo, versiones anteriores)."""
    for patron in ("../*/ibague_grafo_v4.pkl", "../../*/entregas_ibague/ibague_grafo_v4.pkl", "../../*/ibague_grafo_v4.pkl"):
        for ruta in glob.glob(os.path.join(CARPETA, patron)):
            return ruta
    return None


def _usar_servidor(ox, url):
    """Le dice a osmnx qué servidor usar (el ajuste se llama distinto según la versión)."""
    if hasattr(ox.settings, "overpass_url"):            # osmnx 2.x
        ox.settings.overpass_url = url
    else:                                               # osmnx 1.x
        ox.settings.overpass_endpoint = url.rsplit("/", 1)[0]
    ox.settings.overpass_rate_limit = False


def cargar():
    """Devuelve (nodos, ady).
    nodos[id] = (lat, lon)  -> cada esquina
    ady[u][v] = {"m": metros, "tipo": tipo de vía, "geom": puntos de la calle}  -> cada calle de u a v"""
    if not os.path.exists(ARCHIVO):
        vecino = _buscar_guardado()
        if vecino:
            shutil.copy(vecino, ARCHIVO)
            print(f"Mapa guardado encontrado en {vecino}; se copió a esta carpeta.")

    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, "rb") as f:
            nodos, ady = pickle.load(f)[:2]
        return nodos, ady

    import networkx as nx
    import osmnx as ox
    print("Descargando calles de Ibagué (solo la primera vez, puede tardar varios minutos)...")
    ox.settings.requests_timeout = 120
    G = None
    for url in SERVIDORES:
        print(f"  Probando {url} ...")
        _usar_servidor(ox, url)
        try:
            G = ox.graph_from_point(CENTRO, dist=RADIO_M, network_type="drive")
            break
        except Exception as e:
            print(f"  No respondió ({type(e).__name__}).")
    if G is None:
        raise SystemExit(
            "\nNo se pudo descargar el mapa: ningún servidor respondió.\n"
            f"- Si tienes el archivo ibague_grafo_v4.pkl, cópialo en: {CARPETA}\n"
            "- Si no, prueba con otra red (por ejemplo el hotspot del celular, sin VPN) y vuelve a correr python app.py"
        )
    # Nos quedamos solo con la red conectada, para que siempre exista ruta entre dos esquinas
    G = G.subgraph(max(nx.strongly_connected_components(G), key=len))

    nodos = {n: (d["y"], d["x"]) for n, d in G.nodes(data=True)}
    ady = {n: {} for n in nodos}
    for u, v, d in G.edges(data=True):
        tipo = d.get("highway")
        tipo = tipo[0] if isinstance(tipo, list) else tipo
        geom = [(la, lo) for lo, la in d["geometry"].coords] if "geometry" in d else [nodos[u], nodos[v]]
        if u != v and (v not in ady[u] or d["length"] < ady[u][v]["m"]):
            ady[u][v] = {"m": d["length"], "tipo": tipo, "geom": geom}

    with open(ARCHIVO, "wb") as f:
        pickle.dump((nodos, ady), f)
    return nodos, ady


def limite_mapa(nodos):
    """Rectángulo que encierra todas las esquinas: sirve para delimitar el mapa."""
    lats = [p[0] for p in nodos.values()]
    lons = [p[1] for p in nodos.values()]
    sur, norte, oeste, este = min(lats), max(lats), min(lons), max(lons)
    return [(sur, oeste), (sur, este), (norte, este), (norte, oeste)]


def _metros(p, q):
    """Distancia aproximada en metros entre dos puntos (lat, lon)."""
    return math.hypot((q[0] - p[0]) * 110574, (q[1] - p[1]) * 111320 * math.cos(math.radians(p[0])))


def nodo_cercano(nodos, lat, lon):
    """Esquina más cercana a un punto."""
    return min(nodos, key=lambda n: _metros((lat, lon), nodos[n]))


def punto_cercano(nodos, lat, lon):
    """Esquina más cercana al clic, o None si está a más de MAX_SNAP_M metros."""
    n = nodo_cercano(nodos, lat, lon)
    d = _metros((lat, lon), nodos[n])
    if d > MAX_SNAP_M:
        return None
    return {"u": n, "lat": nodos[n][0], "lon": nodos[n][1], "dist": round(d)}
