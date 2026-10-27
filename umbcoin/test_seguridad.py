"""Pruebas de seguridad (actividad 3.3).  Ejecutar:  pytest -q"""

import os

os.environ["UMBC_DIFICULTAD"] = "2"  # rapido para pruebas; el PoW se valida igual

import copy

import pytest

import core
import node
from core import Blockchain, create_wallet, sign_transaction


@pytest.fixture
def red():
    """Cadena donde 'ana' ya tiene 50 UMBC minados."""
    bc = Blockchain()
    ana, _ = create_wallet()
    luis, _ = create_wallet()
    dir_ = lambda sk: core.address_of(sk.get_verifying_key().to_string().hex())
    bc.mine_block(dir_(ana))
    return bc, ana, dir_(ana), luis, dir_(luis)


def test_flujo_completo(red):
    bc, ana, a, luis, l = red
    assert bc.add_transaction(sign_transaction(ana, l, 20)) is None
    bc.mine_block(l)
    assert bc.get_balance(a) == 30
    assert bc.get_balance(l) == 20 + core.RECOMPENSA
    assert bc.mempool == []


def test_firma_falsificada_rechazada(red):
    bc, ana, a, luis, l = red
    tx = sign_transaction(ana, l, 10)
    tx["monto"] = 50  # alterar una tx ya firmada
    assert bc.add_transaction(tx) == "firma invalida"
    robo = sign_transaction(luis, l, 10)
    robo["de"] = a  # luis firma "en nombre" de ana
    assert bc.add_transaction(robo) == "firma invalida"
    sin_firma = dict(sign_transaction(ana, l, 10), firma="00" * 64)
    assert bc.add_transaction(sin_firma) == "firma invalida"
    assert bc.mempool == []


def test_doble_gasto_y_replay(red):
    bc, ana, a, luis, l = red
    assert "saldo insuficiente" in bc.add_transaction(sign_transaction(ana, l, 51))
    assert bc.add_transaction(sign_transaction(ana, l, 30)) is None
    assert "saldo insuficiente" in bc.add_transaction(sign_transaction(ana, l, 30))  # pendiente cuenta
    tx = bc.mempool[0]
    bc.mine_block(l)
    assert "replay" in bc.add_transaction(tx)  # reenviar una tx ya confirmada
    for monto in (0, -5, 1.5, True):
        assert bc.add_transaction(sign_transaction(ana, l, monto)) is not None


def test_cadena_manipulada_no_se_acepta(red):
    bc, ana, a, luis, l = red
    bc.add_transaction(sign_transaction(ana, l, 20))
    bc.mine_block(a)
    falsa = copy.deepcopy(bc.chain)
    falsa[2].transactions[1]["monto"] = 1  # el atacante cambia el monto...
    for b, prev in zip(falsa[2:], falsa[1:]):  # ...y re-mina todo hacia adelante
        b.previous_hash = prev.hash
        b.nonce = 0
        b.hash = b.calculate_hash()
        b.mine()
    falsa.append(Blockchain(falsa).build_block(l))
    falsa[-1].mine()
    valida, motivo = bc.is_chain_valid(falsa)
    assert not valida and "firma invalida" in motivo  # la firma delata el cambio aunque el PoW este bien
    assert not bc.replace_chain(falsa)


def test_bloque_sin_pow_o_recompensa_inflada(red):
    bc, ana, a, luis, l = red
    b = bc.build_block(l)
    while b.hash.startswith("00"):  # garantizar un hash que NO cumple la dificultad
        b.nonce += 1
        b.hash = b.calculate_hash()
    assert "Proof of Work" in bc.add_block(b)
    b = bc.build_block(l)
    b.transactions[0]["monto"] = 1_000_000
    b.mine()
    assert "recompensa" in bc.add_block(b)


def test_api():
    node.bc = Blockchain()
    c = node.app.test_client()
    ana, _ = create_wallet()
    a = core.address_of(ana.get_verifying_key().to_string().hex())
    assert c.get(f"/minar?direccion={a}").status_code == 200
    assert c.get(f"/balance/{a}").json["balance"] == 50
    tx = sign_transaction(ana, "ab" * 32, 5)
    assert c.post("/transacciones/nueva", json=tx).status_code == 201
    tx["monto"] = 49
    assert c.post("/transacciones/nueva", json=tx).status_code == 400
    assert c.post("/bloques/nuevo", json={"basura": 1}).status_code == 400
    assert c.get("/cadena").json["longitud"] == 2
