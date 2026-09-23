# Fase 1 - Arquitectura y modelo de datos

Este documento fija las decisiones de la Fase 1 del MVP de GastroFlow. No incluye migraciones, contenedores ni pantallas implementadas; eso queda para las fases siguientes.

## Objetivo de arquitectura

GastroFlow se construye como una aplicacion Reflex 100% Python, con reglas de negocio en servicios de backend invocados por `rx.State`. No se monta una API FastAPI independiente para el MVP. Reflex queda como capa de UI y sincronizacion reactiva; el dominio y las transacciones viven en modulos Python independientes y testeables.

## Capas

```text
gastroflow/
  app.py                    # Entrada Reflex y registro de paginas.
  domain/                   # Tipos de dominio puros: enums, reglas, errores.
  models/                   # SQLModel: Base/Table/Create/Read.
  data/                     # Sesiones, repositorios, secuencias y unidad de trabajo.
  services/                 # Casos de uso y reglas de negocio.
  states/                   # rx.State, aislados por flujo de UI.
  ui/                       # Paginas y componentes Reflex.
  config/                   # Settings leidos desde variables de entorno.
alembic/                    # Migraciones desde Fase 3.
scripts/                    # Comandos seguros de seed/admin desde Fase 4.
tests/                      # Tests de reglas criticas.
docs/                       # Decisiones de arquitectura y modelo.
```

## Responsabilidades por capa

`domain/`

- Define enums estables: roles, estados de pedido, forma de pago, unidad de venta, promociones y reglas de precio de combo.
- Define la maquina de estados de pedidos y errores de dominio.
- No conoce Reflex, SQLModel ni Postgres.

`models/`

- Contiene los modelos SQLModel con el patron `EntidadBase`, `Entidad(table=True)`, `EntidadCreate`, `EntidadRead`.
- Usa `Decimal` para dinero y cantidades monetarias.
- Separa claves tecnicas `id` de codigos de negocio `codigo`.
- No contiene reglas de negocio complejas.

`data/`

- Maneja `engine`, sesiones, repositorios y generacion atomica de codigos.
- Encapsula SQL puntual, incluyendo secuencias o locks de Postgres si hacen falta para `PED-0001` y `GAS-0001`.
- No decide estados ni calcula precios finales por su cuenta.

`services/`

- Punto obligatorio para toda regla de negocio.
- Valida permisos de rol.
- Ejecuta transacciones.
- Calcula snapshots de precios, promociones, reglas mayoristas, costos de envio, totales y estado inicial del pedido.
- Genera links `wa.me/` cuando corresponda.

`states/`

- Expone estado y acciones Reflex.
- Invoca servicios asincronicamente.
- Mantiene separado `PublicOrderState` de estados internos como `OperationsState`, `ExpenseState`, `CatalogAdminState` y `AuthState`.
- No filtra seguridad por si solo: la autorizacion se vuelve a validar en servicios.

`ui/`

- Paginas y componentes visuales Reflex.
- Mobile-first para pedido publico, cocina/despacho y gastos.
- Puede ocultar acciones por rol para mejorar UX, pero eso nunca reemplaza validaciones de servicio.

## Flujos principales

### Pedido publico

1. `PublicOrderState` captura datos del cliente y del pedido.
2. El estado envia un comando a `OrderService.create_public_order`.
3. El servicio normaliza telefono y hace upsert de cliente.
4. El servicio carga catalogo vigente, valida reglas, calcula snapshots, total y estado inicial.
5. El servicio persiste pedido e items en una transaccion.
6. El estado muestra resumen confirmado y, si aplica, link de WhatsApp.

### Panel operativo

1. `OperationsState` solicita pedidos filtrados a `OrderService`.
2. El servicio valida rol `dueno` o `admin`.
3. La UI muestra tarjetas agrupadas por estado.
4. Un cambio de estado invoca `OrderService.transition_order`.
5. La maquina de estados valida la transicion y persiste el cambio.

### Alta de gasto

1. `ExpenseState` envia datos a `ExpenseService.create_expense`.
2. El servicio valida rol `dueno` o `admin`.
3. El servicio crea motivo/marca on-the-fly si no existen.
4. Genera `GAS-0001` de forma atomica y persiste el gasto.

### Configuracion

1. `CatalogAdminState` invoca `CatalogService`.
2. El servicio valida rol `admin`.
3. Admin puede modificar categorias, productos, promociones, reglas mayoristas, reglas de combo y zonas de envio.
4. Motivos de gasto y marcas no tienen CRUD dedicado en el MVP.

## Seguridad de arquitectura

- Passwords hasheadas con bcrypt desde Fase 4.
- Credenciales, DB URL y API keys siempre por variables de entorno.
- El cliente sin login solo puede crear pedidos publicos; no recibe listados internos ni configuracion administrativa.
- El formulario publico tendra validaciones anti-abuso basicas en servicio: normalizacion de telefono, validaciones estrictas de payload y limite simple por telefono/IP cuando la infraestructura este lista.
- La autorizacion se valida en servicios para cada operacion interna.

## Decisiones pendientes para fases futuras

- Elegir bcrypt o argon2 en Fase 4. Ambos cumplen el requisito, pero se definira uno antes de implementar auth.
- La Fase 3 usa secuencias PostgreSQL dedicadas para `PED-*` y `GAS-*`.
