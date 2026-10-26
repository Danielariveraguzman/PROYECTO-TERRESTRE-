"""Dijkstra sobre las calles de Ibagué, rutas hasta un destino y armado de los viajes."""
import heapq
import math

from datos import VELOCIDADES
from mochila import mochila, volumen


def dijkstra(ady, origen, costo, destino=None):
    """Mejor costo desde el origen a cada esquina. 'costo' es una función que dice cuánto cuesta cada calle."""
    dist, prev, cola = {origen: 0}, {}, [(0, origen)]
    while cola:
        d, u = heapq.heappop(cola)           # la esquina pendiente más cercana al origen
        if d > dist.get(u, math.inf):        # entrada vieja: ya se encontró un camino mejor
            continue
        if u == destino:                     # ya llegamos al destino, no hace falta seguir
            break
        for v, calle in ady[u].items():
            nd = d + costo(u, v, calle)
            if nd < dist.get(v, math.inf):   # ¿llegar a v por u es mejor que lo que se conocía?
                dist[v], prev[v] = nd, u
                heapq.heappush(cola, (nd, v))
    return dist, prev


def camino(prev, origen, destino):
    """Reconstruye la ruta (lista de esquinas) yendo hacia atrás con 'prev'."""
    if destino != origen and destino not in prev:
        return None                          # no hay ruta
    ruta = [destino]
    while ruta[-1] != origen:
        ruta.append(prev[ruta[-1]])
    return ruta[::-1]


def segundos(calle, veh):
    """Tiempo en segundos de recorrer una calle: distancia / velocidad (según tipo de vía y vehículo)."""
    metros_por_segundo = VELOCIDADES.get(calle["tipo"], 25) * veh["vel"] / 3.6
    return calle["m"] / metros_por_segundo


def describir(nombre, ruta, ady, veh):
    """Convierte una lista de esquinas en kilómetros, minutos y puntos para dibujar en el mapa."""
    metros = seg = 0
    coords = []
    for u, v in zip(ruta, ruta[1:]):
        calle = ady[u][v]
        metros += calle["m"]
        seg += segundos(calle, veh)
        coords += calle["geom"] if not coords else calle["geom"][1:]   # [1:] evita repetir el punto de unión
    return {"nombre": nombre, "km": round(metros / 1000, 1), "min": round(seg / 60), "coords": coords}


def rutas_alternativas(ady, origen, punto, veh, n=4):
    """Hasta n rutas al destino: la más rápida, la más corta y alternativas.
    Las alternativas salen de volver a correr Dijkstra encareciendo las calles que ya se usaron."""
    destino = punto["u"]
    castigo = {}                                 # (u, v) -> multiplicador del costo; 1 = sin castigo

    def en_tiempo(u, v, calle):
        return segundos(calle, veh) * castigo.get((u, v), 1)

    def en_metros(u, v, calle):
        return calle["m"]

    def buscar(costo):
        return camino(dijkstra(ady, origen, costo, destino)[1], origen, destino)

    def parecidas(a, b):                         # comparten más del 85 % de las calles
        tramos_a, tramos_b = set(zip(a, a[1:])), set(zip(b, b[1:]))
        return len(tramos_a & tramos_b) > 0.85 * min(len(tramos_a), len(tramos_b))

    rutas = []

    def agregar(nombre, ruta):                   # guarda la ruta si existe y no repite una anterior
        if ruta and len(ruta) > 1 and not any(parecidas(ruta, r) for _, r in rutas):
            rutas.append((nombre, ruta))
            return True
        return False

    def castigar(ruta):                          # cada calle de la ruta cuesta 1.6 veces más
        for tramo in zip(ruta, ruta[1:]):
            castigo[tramo] = castigo.get(tramo, 1) * 1.6

    agregar("Más rápida", buscar(en_tiempo))
    agregar("Más corta", buscar(en_metros))
    for _, ruta in rutas:
        castigar(ruta)

    numero = 1
    for _ in range(6):                           # hasta 6 intentos de encontrar alternativas
        if len(rutas) >= n:
            break
        ruta = buscar(en_tiempo)
        if not ruta:
            break
        if agregar(f"Alternativa {numero}", ruta):
            numero += 1
        castigar(ruta)
    return [describir(nombre, ruta, ady, veh) for nombre, ruta in rutas]


def despachar(ady, deposito, pedidos, veh):
    """La mochila elige qué paquetes suben en cada viaje; después se visita siempre el más cercano."""
    def en_tiempo(u, v, calle):
        return segundos(calle, veh)

    # Solo los paquetes que caben solos en el vehículo (peso y volumen)
    pendientes = [p for p in pedidos if math.ceil(p["peso"]) <= veh["peso_max"] and volumen(p) <= veh["vol_max"]]
    viajes = []

    while pendientes:
        # 1. Mochila: qué paquetes suben en este viaje
        elegidos = mochila(pendientes, int(veh["peso_max"]), veh["vol_max"])
        if not elegidos:
            break

        # 2. Dijkstra: desde donde estamos, ir al paquete más cercano en tiempo, y repetir
        actual, esquinas, orden, faltan = deposito, [deposito], [], list(elegidos)
        while faltan:
            dist, prev = dijkstra(ady, actual, en_tiempo)
            siguiente = min(faltan, key=lambda p: dist[p["u"]])
            esquinas += camino(prev, actual, siguiente["u"])[1:]
            orden.append(siguiente)
            faltan.remove(siguiente)
            actual = siguiente["u"]

        # 3. Volver a la bodega
        prev = dijkstra(ady, actual, en_tiempo, deposito)[1]
        esquinas += camino(prev, actual, deposito)[1:]

        viaje = describir(f"Viaje {len(viajes) + 1}", esquinas, ady, veh)
        viaje.update(orden=orden, peso=sum(p["peso"] for p in orden),
                     vol=round(sum(volumen(p) for p in orden), 3), valor=sum(p["valor"] for p in orden))
        viajes.append(viaje)
        pendientes = [p for p in pendientes if p not in elegidos]

    llevados = {p["id"] for v in viajes for p in v["orden"]}
    return {"viajes": viajes, "sin_asignar": [p["nombre"] for p in pedidos if p["id"] not in llevados]}
