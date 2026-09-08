"""UMBCoin (UMBC) - Semana 1: hash, bloque, cadena y validacion de integridad.

Ejecutar:  python blockchain.py
"""

import hashlib
import json
import time

NOMBRE_MONEDA = "UMBCoin"
SIMBOLO = "UMBC"


class Block:
    def __init__(self, index, transactions, previous_hash, nonce=0, timestamp=None):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        contenido = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }, sort_keys=True).encode()
        return hashlib.sha256(contenido).hexdigest()

    def __repr__(self):
        return f"Block(index={self.index}, hash={self.hash[:16]}..., prev={self.previous_hash[:16]}...)"


class Blockchain:
    def __init__(self):
        self.chain = [self._crear_genesis()]

    def _crear_genesis(self):
        # El genesis no tiene bloque anterior: previous_hash convencional de 64 ceros.
        return Block(0, [{"info": f"Bloque genesis de {NOMBRE_MONEDA} ({SIMBOLO})"}], "0" * 64)

    @property
    def last_block(self):
        return self.chain[-1]

    def add_block(self, transactions):
        bloque = Block(self.last_block.index + 1, transactions, self.last_block.hash)
        self.chain.append(bloque)
        return bloque

    def is_chain_valid(self):
        """True si toda la cadena es coherente. Devuelve (valida, motivo)."""
        for i, bloque in enumerate(self.chain):
            if bloque.hash != bloque.calculate_hash():
                return False, f"Bloque {i}: el hash almacenado no coincide con el recalculado"
            if i == 0:
                if bloque.previous_hash != "0" * 64:
                    return False, "Bloque genesis: previous_hash invalido"
            elif bloque.previous_hash != self.chain[i - 1].hash:
                return False, f"Bloque {i}: previous_hash no apunta al hash real del bloque {i - 1}"
        return True, "Cadena valida"


def demo():
    print(f"=== {NOMBRE_MONEDA} ({SIMBOLO}) - Semana 1 ===\n")

    # Efecto avalancha (ejercicio 2.1.1)
    for texto in ("UMB", "UMB."):
        print(f'SHA-256("{texto}") = {hashlib.sha256(texto.encode()).hexdigest()}')
    print()

    bc = Blockchain()
    for i in range(1, 6):
        bc.add_block([{"de": f"ana{i}", "para": f"luis{i}", "monto": 10 * i}])

    print(f"Bloques en la cadena: {len(bc.chain)}")
    for b in bc.chain:
        print(" ", b)

    valida, motivo = bc.is_chain_valid()
    print(f"\nANTES de manipular -> valida={valida} ({motivo})")
    assert valida

    # Prueba de manipulacion (actividad 1.5): alterar el monto de un bloque intermedio.
    print("\n>> Alterando el monto del bloque 3 (50 -> 999999)...")
    bc.chain[3].transactions[0]["monto"] = 999999

    valida, motivo = bc.is_chain_valid()
    print(f"DESPUES de manipular -> valida={valida} ({motivo})")
    assert not valida

    # Ni siquiera recalcular el hash del bloque alterado salva la cadena:
    # el previous_hash del bloque 4 ya no coincide.
    print("\n>> El atacante recalcula el hash del bloque 3 para disimular...")
    bc.chain[3].hash = bc.chain[3].calculate_hash()
    valida, motivo = bc.is_chain_valid()
    print(f"Sigue invalida -> valida={valida} ({motivo})")
    assert not valida

    print("\nOK: is_chain_valid() detecta la manipulacion en ambos casos.")


if __name__ == "__main__":
    demo()
