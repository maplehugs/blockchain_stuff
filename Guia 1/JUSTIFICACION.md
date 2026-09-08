# UMBCoin (UMBC) — Semana 1: justificación conceptual

## ¿Por qué el efecto avalancha es indispensable para detectar manipulación?

Un bloque guarda su propio hash, calculado sobre todos sus campos (index, timestamp,
transactions, previous_hash, nonce). El efecto avalancha significa que cambiar **un solo bit**
de la entrada produce una salida completamente distinta e impredecible. Se ve en la demo:

```
SHA-256("UMB")  = 898546e878a639f0efbeb76d921c3a4d5156218ca69fa5d06a4237e117c94d31
SHA-256("UMB.") = 7b9c935501c203572f3033ddd945df71bfa31125f43e79f539597250ac2d6557
```

Un punto de diferencia, y los 64 caracteres cambian: no hay parecido parcial del que un
atacante pueda aprovecharse.

Eso da dos garantías que sostienen la cadena:

1. **Detección local.** Si alguien altera el monto de una transacción, el hash recalculado ya
   no coincide con el almacenado. `is_chain_valid()` lo detecta en un solo cálculo.
2. **Detección en cascada.** Si el atacante recalcula el hash del bloque alterado para
   disimular, ese hash nuevo ya no coincide con el `previous_hash` del bloque siguiente. Para
   que la cadena vuelva a cuadrar tendría que rehacer *todos* los bloques posteriores — que es
   exactamente el trabajo que el Proof of Work (Semana 2) vuelve económicamente inviable.

La evidencia de ambos casos está en `evidencia.txt`.

## ¿Qué pasaría con una función hash sin esa propiedad?

Sin efecto avalancha, entradas parecidas producirían hashes parecidos, y el sistema se rompe
por varios lados:

- **Manipulación invisible en la práctica.** Cambiar `monto: 50` por `monto: 51` daría un hash
  casi idéntico; cualquier validación tolerante, un log truncado o una revisión humana que
  compare "los primeros caracteres" dejaría pasar el fraude.
- **Falsificación dirigida.** Si el hash es predecible ante cambios pequeños, el atacante puede
  ajustar campos por tanteo hasta reconstruir el hash original en vez de buscar a ciegas:
  ya no necesita fuerza bruta, tiene un atajo. Eso equivale a perder también la resistencia a
  preimagen y a colisiones.
- **Proof of Work sin valor.** El PoW se apoya en que la única forma de encontrar un nonce
  válido es probar por fuerza bruta. Si el hash fuera predecible, el nonce se calcularía en
  lugar de buscarse, la minería dejaría de costar y el ataque del 51 % dejaría de requerir el
  51 % de nada.

En resumen: la inmutabilidad de una blockchain no viene de que los datos "no se puedan tocar"
—cualquiera puede editar su copia local—, sino de que **tocarlos siempre se nota**. El efecto
avalancha es lo que hace que se note.

## Nota de diseño

El `previous_hash` del génesis es una constante de 64 ceros, y `is_chain_valid()` la verifica
explícitamente: si no, un atacante podría reemplazar el bloque 0 completo por uno propio y la
cadena seguiría siendo "coherente" consigo misma.
