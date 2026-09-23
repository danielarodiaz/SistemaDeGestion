# Datos requeridos para seed inicial de catalogo

La Fase 2 pide un seed inicial con datos conocidos del negocio. Los datos confirmados se guardan en `gastroflow/seed/catalog_seed.json` como seed declarativo para que Fase 3 lo convierta en inserts reales una vez existan modelos y migraciones.

## Datos minimos a confirmar

### Categorias

Formato requerido:

| codigo | nombre |
| --- | --- |
| `LISTA_HORNO` | Lista para hornear |

Categorias confirmadas:

| codigo | nombre |
| --- | --- |
| `LISTA_HORNO` | Lista para hornear |
| `LISTA_COMER` | Lista para comer |
| `PRE_PIZZAS` | Pre pizzas |
| `MAYORISTA` | Mayorista |
| `PAN_ARABE` | Pan árabe |
| `PIZZETAS` | Pizzetas |

### Productos

Formato requerido actualizado:

| categoria | codigo | nombre | descripcion | fotos | precio | unidad_venta |
| --- | --- | --- | --- | --- | --- | --- |
| `LISTA_HORNO` | `MUZZA_HORNO` | Muzzarella | null | null | `5500.00` | `PIEZA` |
| `LISTA_HORNO` | `ESPECIAL_HORNO` | Especial | null | null | `7000.00` | `PIEZA` |
| `LISTA_HORNO` | `CALABRESA_HORNO` | Calabresa | null | null | `7000.00` | `PIEZA` |

Los precios promocionales y mayoristas no viven en `producto`.

### Promociones

Formato requerido:

| codigo | productos elegibles | tipo | cantidad_minima | precio_unitario_promocional | activa |
| --- | --- | --- | --- | --- | --- |
| `PROMO_MUZZA_HORNO_2` | `MUZZA_HORNO` | `PRECIO_UNITARIO_POR_CANTIDAD` | 2 | `5000.00` | true |
| `PROMO_ESPECIAL_CALABRESA_HORNO_2` | `ESPECIAL_HORNO`, `CALABRESA_HORNO` | `PRECIO_UNITARIO_POR_CANTIDAD` | 2 | `6500.00` | true |

### Mayorista

Formato requerido:

| codigo | categoria | cantidad_minima_total | producto | precio_unitario_mayorista |
| --- | --- | --- | --- | --- |
| `MAYORISTA_LISTA_HORNO_10` | `LISTA_HORNO` | 10 | `MUZZA_HORNO` | `4500.00` |
| `MAYORISTA_LISTA_HORNO_10` | `LISTA_HORNO` | 10 | `ESPECIAL_HORNO` | `6000.00` |
| `MAYORISTA_LISTA_HORNO_10` | `LISTA_HORNO` | 10 | `CALABRESA_HORNO` | `6000.00` |

### Zonas de envio

Formato requerido:

| nombre | costo |
| --- | --- |
| San Miguel de Tucuman | `1500.00` |
| Alderetes | `500.00` |
| Yerba Buena | `2000.00` |

### Combos

Formato requerido:

| producto_a | producto_b | requiere_confirmacion | regla_precio | precio_fijo_combo |
| --- | --- | --- | --- | --- |
| `MUZZA_HORNO` | `ESPECIAL_HORNO` | false | `PROMEDIO` |  |

Reglas permitidas:

- `MAYOR_VALOR`
- `PROMEDIO`
- `PRECIO_FIJO`

Si `regla_precio` es `PRECIO_FIJO`, `precio_fijo_combo` es obligatorio.
