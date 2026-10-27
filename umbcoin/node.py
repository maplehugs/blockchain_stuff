"""Nodo UMBCoin: API REST + red de nodos con consenso por cadena mas larga.

Ejecutar:  python node.py --puerto 5000
"""

import argparse
import json
import os
import threading
import urllib.request

from flask import Flask, jsonify, request

from core import DIFICULTAD, Block, Blockchain, _is_address

app = Flask(__name__)
CADENA_JSON = None  # se fija en __main__; sin archivo (tests) la cadena vive solo en memoria
lock = threading.Lock()  # ponytail: un lock global, un nodo de clase no necesita mas
nodos = set()


def cargar():
    try:
        with open(CADENA_JSON) as f:
            bc = Blockchain.from_dicts(json.load(f))
    except FileNotFoundError:
        return Blockchain()
    valida, motivo = bc.is_chain_valid()
    if not valida:
        raise SystemExit(f"{CADENA_JSON} esta corrupta: {motivo}")
    return bc


def guardar():
    if not CADENA_JSON:
        return
    tmp = CADENA_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(bc.to_dicts(), f)
    os.replace(tmp, CADENA_JSON)  # atomico: un corte a mitad de escritura no rompe la cadena


bc = Blockchain()


def http(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, body, {"Content-Type": "application/json",
                                                # Cloudflare bloquea el user-agent por defecto de Python (error 1010)
                                                "User-Agent": "UMBCoin/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:  # ponytail: sin limite de tamano de respuesta
        return json.load(r)


def difundir(ruta, data):
    """Avisa a los nodos conocidos (en segundo plano; si uno esta caido, se ignora)."""
    def enviar(nodo):
        try:
            http(nodo + ruta, data)
        except Exception:
            pass
    for nodo in list(nodos):
        threading.Thread(target=enviar, args=(nodo,), daemon=True).start()


@app.post("/transacciones/nueva")
def nueva_transaccion():
    tx = request.get_json(silent=True)
    with lock:
        error = bc.add_transaction(tx)
    if error:
        return jsonify(error=error), 400
    difundir("/transacciones/nueva", tx)
    return jsonify(mensaje="Transaccion agregada al mempool"), 201


@app.get("/cadena")
def cadena():
    with lock:
        return jsonify(longitud=len(bc.chain), dificultad=DIFICULTAD, cadena=bc.to_dicts())


@app.get("/mempool")
def mempool():
    with lock:
        return jsonify(bc.mempool)


@app.get("/minar")
def minar():
    """Mina en ESTE nodo (CPU del servidor). La recompensa va a ?direccion=."""
    direccion = request.args.get("direccion", "")
    with lock:
        if not _is_address(direccion):
            return jsonify(error="falta ?direccion= (64 hex)"), 400
        bloque = bc.mine_block(direccion)
        guardar()
    difundir("/bloques/nuevo", bloque.to_dict())
    return jsonify(mensaje="Bloque minado", bloque=bloque.to_dict())


@app.post("/bloques/nuevo")
def bloque_nuevo():
    """Recibe un bloque minado afuera (un minero o un nodo vecino)."""
    try:
        bloque = Block.from_dict(request.get_json(silent=True))
    except TypeError:
        return jsonify(error="bloque mal formado"), 400
    with lock:
        error = bc.add_block(bloque)
        if not error:
            guardar()
    if error:
        return jsonify(error=error, longitud=len(bc.chain)), 409
    difundir("/bloques/nuevo", bloque.to_dict())
    return jsonify(mensaje="Bloque aceptado", index=bloque.index), 201


@app.get("/balance/<direccion>")
def balance(direccion):
    with lock:
        return jsonify(direccion=direccion, balance=bc.get_balance(direccion))


@app.post("/nodos/registrar")
def registrar():
    nuevos = (request.get_json(silent=True) or {}).get("nodos", [])
    if not isinstance(nuevos, list) or not all(isinstance(n, str) and n.startswith("http") for n in nuevos):
        return jsonify(error='enviar {"nodos": ["http://host:puerto", ...]}'), 400
    nodos.update(n.rstrip("/") for n in nuevos)
    return jsonify(nodos=sorted(nodos)), 201


@app.get("/nodos/resolver")
def resolver():
    reemplazada = False
    for nodo in list(nodos):
        try:
            otra = Blockchain.from_dicts(http(nodo + "/cadena")["cadena"]).chain
        except Exception:
            continue
        with lock:
            if bc.replace_chain(otra):
                reemplazada = True
                guardar()
    return jsonify(reemplazada=reemplazada, longitud=len(bc.chain))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--puerto", type=int, default=5000)
    p.add_argument("--host", default="127.0.0.1")
    a = p.parse_args()
    CADENA_JSON = os.environ.get("UMBC_CADENA", f"cadena_{a.puerto}.json")
    bc = cargar()
    app.run(host=a.host, port=a.puerto, threaded=True)
