# UMBCoin (UMBC) — Semanas 2 y 3

Moneda funcional: wallets secp256k1, transacciones firmadas, mempool, Proof of Work,
recompensa de minería, balances, API REST y red de nodos con consenso de cadena más larga.

| Archivo | Qué es |
|---|---|
| `core.py` | Bloques, wallets, firmas, PoW, validación y balances |
| `node.py` | Nodo: API REST (Flask) + red de nodos |
| `cli.py` | Cliente: crear wallet, enviar, consultar saldo, minar |
| `test_seguridad.py` | Pruebas de seguridad (pytest) |

## Instalar

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/pytest -q
```

## Unirse a la red pública y minar

```bash
export UMBC_NODO=https://umbc.5maple.com
python cli.py crear                 # wallet.json: ¡es tu llave privada, no la compartas!
python cli.py minar                 # minas con tu CPU; cada bloque = 50 UMBC
python cli.py saldo
python cli.py enviar <direccion> 10
```

La llave privada nunca sale de tu PC: la transacción se firma en local y al nodo
solo le llega firmada.

## Red local de varios nodos

```bash
python node.py --puerto 5000 &
python node.py --puerto 5001 &
curl -X POST localhost:5000/nodos/registrar -H 'Content-Type: application/json' -d '{"nodos":["http://127.0.0.1:5001"]}'
curl -X POST localhost:5001/nodos/registrar -H 'Content-Type: application/json' -d '{"nodos":["http://127.0.0.1:5000"]}'
curl localhost:5001/nodos/resolver
```

Cada nodo guarda su cadena en `cadena_<puerto>.json`. Todos los nodos tienen que usar
la misma `UMBC_DIFICULTAD` (por defecto 4).

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/transacciones/nueva` | Agrega una tx firmada al mempool (400 si la firma es inválida o no hay saldo) |
| GET | `/cadena` | Cadena completa + dificultad |
| GET | `/mempool` | Transacciones pendientes |
| GET | `/minar?direccion=<dir>` | Mina en el nodo; la recompensa va a `<dir>` |
| POST | `/bloques/nuevo` | Recibe un bloque minado afuera (lo usan `cli.py minar` y los nodos vecinos) |
| GET | `/balance/<dir>` | Saldo, calculado recorriendo la cadena |
| POST | `/nodos/registrar` | `{"nodos": ["http://host:puerto"]}` |
| GET | `/nodos/resolver` | Adopta la cadena válida más larga de los vecinos |

En el nodo público, `/minar` y `/nodos/registrar` están bloqueados: hay que minar con tu propia
CPU usando `cli.py minar`, y el servidor no hace peticiones a URLs que le mande cualquiera.
