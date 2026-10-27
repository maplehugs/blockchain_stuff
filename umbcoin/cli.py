"""Cliente UMBCoin: wallet, envios y mineria contra cualquier nodo.

La llave privada NUNCA sale de tu PC: se firma aqui y al nodo solo llega la tx firmada.

  python cli.py crear                      # crea wallet.json
  python cli.py saldo [direccion]
  python cli.py enviar <direccion> <monto>
  python cli.py minar [--bloques N]        # minas con TU CPU y le mandas el bloque al nodo
  (--nodo URL o variable UMBC_NODO; por defecto http://localhost:5000)
"""

import argparse
import json
import os
import time
import urllib.error

from ecdsa import SECP256k1, SigningKey

import core
from node import http


def cargar_wallet(archivo):
    with open(archivo) as f:
        return SigningKey.from_string(bytes.fromhex(json.load(f)["privada"]), curve=SECP256k1)


def direccion(sk):
    return core.address_of(sk.get_verifying_key().to_string().hex())


def llamar(url, data=None):
    try:
        return http(url, data)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            raise SystemExit(f"{url}: HTTP {e.code}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nodo", default=os.environ.get("UMBC_NODO", "http://localhost:5000"))
    p.add_argument("--wallet", default="wallet.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crear")
    sub.add_parser("saldo").add_argument("direccion", nargs="?")
    e = sub.add_parser("enviar")
    e.add_argument("para")
    e.add_argument("monto", type=int)
    sub.add_parser("minar").add_argument("--bloques", type=int, default=0, help="0 = sin parar")
    a = p.parse_args()
    nodo = a.nodo.rstrip("/")

    if a.cmd == "crear":
        if os.path.exists(a.wallet):
            raise SystemExit(f"{a.wallet} ya existe; no la piso (perderias tus fondos)")
        sk, _ = core.create_wallet()
        with open(a.wallet, "w") as f:
            json.dump({"privada": sk.to_string().hex(), "direccion": direccion(sk)}, f)
        os.chmod(a.wallet, 0o600)
        print(f"Wallet creada en {a.wallet}\nTu direccion: {direccion(sk)}")

    elif a.cmd == "saldo":
        dir_ = a.direccion or direccion(cargar_wallet(a.wallet))
        print(f"{llamar(f'{nodo}/balance/{dir_}')['balance']} {core.SIMBOLO}")

    elif a.cmd == "enviar":
        tx = core.sign_transaction(cargar_wallet(a.wallet), a.para, a.monto)
        print(llamar(f"{nodo}/transacciones/nueva", tx))

    elif a.cmd == "minar":
        yo = direccion(cargar_wallet(a.wallet))
        minados = 0
        while not a.bloques or minados < a.bloques:
            info = llamar(f"{nodo}/cadena")
            core.DIFICULTAD = info["dificultad"]  # la dificultad la decide la red, no el minero
            bc = core.Blockchain.from_dicts(info["cadena"])
            for tx in llamar(f"{nodo}/mempool"):
                bc.add_transaction(tx)  # se re-validan: no confiamos ciegamente en el nodo
            bloque = bc.build_block(yo)
            t = time.time()
            intentos = bloque.mine()
            r = llamar(f"{nodo}/bloques/nuevo", bloque.to_dict())
            if "error" in r:
                print(f"Bloque {bloque.index} rechazado ({r['error']}); alguien mino primero, reintento")
                continue
            minados += 1
            print(f"Bloque {bloque.index} minado en {time.time() - t:.1f}s ({intentos} intentos) "
                  f"-> +{core.RECOMPENSA} {core.SIMBOLO}")


if __name__ == "__main__":
    main()
