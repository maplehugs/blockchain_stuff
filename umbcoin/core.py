"""UMBCoin (UMBC) - Semanas 2 y 3: wallets, firmas, Proof of Work, mempool y balances.

La cadena de la Semana 1 crece con lo que hace falta para que sea una moneda:
- una wallet es un par de llaves secp256k1; la direccion es SHA-256 de la llave publica.
- cada transaccion va firmada por el emisor y cualquier nodo la verifica con la llave publica.
- un bloque solo es valido si su hash empieza con DIFICULTAD ceros (PoW).
- los saldos no se guardan en ningun lado: se calculan recorriendo toda la cadena.
"""

import hashlib
import json
import os
import time

from ecdsa import SECP256k1, SigningKey, VerifyingKey

NOMBRE_MONEDA = "UMBCoin"
SIMBOLO = "UMBC"
DIFICULTAD = int(os.environ.get("UMBC_DIFICULTAD", 4))
RECOMPENSA = 50
RED = "RED"  # "emisor" de las recompensas de mineria: crea monedas nuevas


def sha256(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def canon(obj):
    """JSON canonico: el mismo objeto siempre serializa igual, en cualquier nodo."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------- wallets y firmas

def create_wallet():
    private_key = SigningKey.generate(curve=SECP256k1)
    return private_key, private_key.get_verifying_key()


def address_of(public_key_hex):
    return sha256(bytes.fromhex(public_key_hex))


def tx_payload(tx):
    """Lo que se firma. La firma no se incluye (no se puede firmar a si misma)."""
    return canon({k: tx[k] for k in ("de", "para", "monto", "ts")})


def tx_id(tx):
    # Sobre el payload y no sobre la firma: una firma ECDSA se puede "maleabilizar"
    # (r, s) -> (r, n-s) sin la llave privada, y con eso se colaria la misma tx dos veces.
    return sha256(tx_payload(tx))


def sign_transaction(private_key, para, monto):
    pub = private_key.get_verifying_key().to_string().hex()
    tx = {"de": address_of(pub), "para": para, "monto": monto, "ts": time.time(), "llave_publica": pub}
    tx["firma"] = private_key.sign(tx_payload(tx).encode(), hashfunc=hashlib.sha256).hex()
    return tx


def verify_transaction(tx) -> bool:
    try:
        if address_of(tx["llave_publica"]) != tx["de"]:
            return False  # la llave publica no corresponde a la direccion que dice gastar
        vk = VerifyingKey.from_string(bytes.fromhex(tx["llave_publica"]), curve=SECP256k1)
        return vk.verify(bytes.fromhex(tx["firma"]), tx_payload(tx).encode(), hashfunc=hashlib.sha256)
    except Exception:
        return False


def _is_address(x):
    return isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdef" for c in x)


def _apply_tx(tx, saldos, vistos):
    """Valida tx contra el estado (saldos, vistos) y la aplica. Devuelve el error o None."""
    if not isinstance(tx, dict) or not verify_transaction(tx):
        return "firma invalida"
    if type(tx["monto"]) is not int or tx["monto"] <= 0:
        return "monto debe ser un entero positivo"
    if not _is_address(tx["para"]):
        return "direccion destino invalida"
    if tx_id(tx) in vistos:
        return "transaccion repetida (replay)"
    if saldos.get(tx["de"], 0) < tx["monto"]:
        return "saldo insuficiente (doble gasto)"
    saldos[tx["de"]] -= tx["monto"]
    saldos[tx["para"]] = saldos.get(tx["para"], 0) + tx["monto"]
    vistos.add(tx_id(tx))
    return None


# ---------------------------------------------------------------- bloques

class Block:
    def __init__(self, index, transactions, previous_hash, nonce=0, timestamp=None, hash=None):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash or self.calculate_hash()

    def calculate_hash(self):
        return sha256(json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }, sort_keys=True))

    def mine(self, dificultad=None):
        """Fuerza bruta sobre el nonce. Devuelve cuantos intentos tomo."""
        dificultad = DIFICULTAD if dificultad is None else dificultad
        intentos = 1
        while not self.hash.startswith("0" * dificultad):
            self.nonce += 1
            self.hash = self.calculate_hash()
            intentos += 1
        return intentos

    def to_dict(self):
        return dict(vars(self))

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


# Timestamp fijo: todos los nodos deben arrancar con EXACTAMENTE el mismo genesis,
# si no sus cadenas nunca coincidirian y no podrian ponerse de acuerdo.
GENESIS = Block(0, [{"info": f"Bloque genesis de {NOMBRE_MONEDA} ({SIMBOLO})"}], "0" * 64, timestamp=0)


def _apply_block(bloque, anterior, saldos, vistos):
    if bloque.hash != bloque.calculate_hash():
        return f"Bloque {bloque.index}: el hash almacenado no coincide con el recalculado"
    if bloque.index != anterior.index + 1 or bloque.previous_hash != anterior.hash:
        return f"Bloque {bloque.index}: no apunta al bloque {anterior.index}"
    if not bloque.hash.startswith("0" * DIFICULTAD):
        return f"Bloque {bloque.index}: no cumple el Proof of Work"
    txs = bloque.transactions
    if not isinstance(txs, list) or not txs:
        return f"Bloque {bloque.index}: sin transaccion de recompensa"
    cb = txs[0]
    if not (isinstance(cb, dict) and set(cb) == {"de", "para", "monto", "bloque"} and cb["de"] == RED
            and cb["monto"] == RECOMPENSA and cb["bloque"] == bloque.index and _is_address(cb["para"])):
        return f"Bloque {bloque.index}: recompensa de mineria invalida"
    for tx in txs[1:]:
        error = _apply_tx(tx, saldos, vistos)
        if error:
            return f"Bloque {bloque.index}: {error}"
    saldos[cb["para"]] = saldos.get(cb["para"], 0) + RECOMPENSA
    return None


def replay(chain):
    """Recorre toda la cadena validandola. Devuelve (saldos, vistos) o lanza ValueError."""
    if not chain or chain[0].to_dict() != GENESIS.to_dict():
        raise ValueError("Bloque genesis invalido")
    saldos, vistos = {}, set()
    for anterior, bloque in zip(chain, chain[1:]):
        error = _apply_block(bloque, anterior, saldos, vistos)
        if error:
            raise ValueError(error)
    return saldos, vistos


class Blockchain:
    def __init__(self, chain=None):
        self.chain = chain or [Block.from_dict(GENESIS.to_dict())]
        self.mempool = []

    @classmethod
    def from_dicts(cls, dicts):
        return cls([Block.from_dict(d) for d in dicts])

    def to_dicts(self):
        return [b.to_dict() for b in self.chain]

    @property
    def last_block(self):
        return self.chain[-1]

    def is_chain_valid(self, chain=None):
        try:
            replay(chain or self.chain)
            return True, "Cadena valida"
        except (ValueError, TypeError, KeyError) as e:
            return False, str(e)

    def get_balance(self, direccion):
        return replay(self.chain)[0].get(direccion, 0)

    def _pending_state(self):
        """Estado confirmado + lo que ya esta en el mempool (para no aceptar doble gasto pendiente)."""
        saldos, vistos = replay(self.chain)
        for tx in self.mempool:
            _apply_tx(tx, saldos, vistos)
        return saldos, vistos

    def add_transaction(self, tx):
        """Valida y mete tx al mempool. Devuelve el error o None."""
        error = _apply_tx(tx, *self._pending_state())
        if not error:
            self.mempool.append(tx)
        return error

    def _prune_mempool(self):
        """Tras un cambio de cadena: saca las tx ya confirmadas o que dejaron de ser validas."""
        pendientes, self.mempool = self.mempool, []
        for tx in pendientes:
            self.add_transaction(tx)

    def build_block(self, miner):
        recompensa = {"de": RED, "para": miner, "monto": RECOMPENSA, "bloque": self.last_block.index + 1}
        return Block(self.last_block.index + 1, [recompensa] + self.mempool, self.last_block.hash)

    def mine_block(self, miner):
        bloque = self.build_block(miner)
        bloque.mine()
        error = self.add_block(bloque)
        assert not error, error
        return bloque

    def add_block(self, bloque):
        """Bloque minado por otro (u otro nodo). Devuelve el error o None."""
        try:
            error = _apply_block(bloque, self.last_block, *replay(self.chain))
        except (TypeError, KeyError, AttributeError) as e:
            error = f"bloque mal formado: {e!r}"
        if not error:
            self.chain.append(bloque)
            self._prune_mempool()
        return error

    def replace_chain(self, chain):
        """Regla de la cadena mas larga: se adopta solo si es mas larga Y valida."""
        if len(chain) <= len(self.chain) or not self.is_chain_valid(chain)[0]:
            return False
        self.chain = chain
        self._prune_mempool()
        return True
