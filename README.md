# 🍕 Gastro-Flow (MVP) — Sistema de Pedidos y Gastos

Sistema centralizado de gestión operativa y control de gastos diseñado específicamente para locales gastronómicos pequeños y medianos (parametrizado inicialmente para pizzerías y rotiserías). 

Reemplaza los flujos manuales propensos a pérdidas de información (como planillas de Google Sheets compartidas) mediante una interfaz web ágil y mobile-first, conectada a una base de datos relacional robusta lista para consumo directo desde **Power BI**.

---

## 🚀 Stack Tecnológico

El proyecto está desarrollado **100% en Python**, priorizando una arquitectura desacoplada por capas:

* **Frontend & Backend App:** [Reflex](https://reflex.dev/) (Full-stack Python reactivo sobre Starlette/FastAPI y WebSockets).
* **ORM & Validación:** [SQLModel](https://sqlmodel.tiangolo.com/) (integración de SQLAlchemy 2.0 y Pydantic v2).
* **Base de Datos:** PostgreSQL 16.
* **Control de Esquema y Migraciones:** Alembic.
* **Entorno & Contenedores:** Docker & Docker Compose.
* **Autenticación:** Hashing criptográfico (bcrypt/argon2) y autorización RBAC a nivel de capa de servicios.

---

## 🏛️ Arquitectura y Principios de Diseño

1. **Lógica de Negocio en Servicios (`services/`):** La UI nunca valida reglas de negocio ni ejecuta transacciones complejas directamente. Todo se resuelve mediante casos de uso (`OrderService`, `ExpenseService`, etc.).
2. **Modelo "BI-Friendly":** 
   * Manejo estricto de dinero mediante tipos `Decimal` / `NUMERIC` en PostgreSQL (sin imprecisiones de `float`).
   * **Snapshot de precios históricos:** `pedido_item.precio_unitario` y `pedido.costo_envio` guardan el valor vigente en el momento de compra para no alterar balances pasados ante futuras actualizaciones de catálogo.
   * Cantidades y unidades tipadas (separando magnitudes numéricas de strings de medida).
3. **Claves Primarias Técnicas vs. Códigos de Negocio:** Uso de IDs enteros autoincrementales en la base de datos y secuencias atómicas para códigos correlativos legibles (`PED-0001`, `GAS-0001`).
4. **UI Mobile-First para Despacho:** Interfaz táctil pensada para celulares y tablets en entornos de cocina, con tarjetas grandes de cambio de estado en tiempo real.

---

## 📋 Módulos del Sistema

* **Formulario Público de Pedidos (Sin Login):**
  * Catálogo dinámico (categorías, pizzas simples o combinadas de 2 sabores).
  * Regla mayorista (validación de mínimo de unidades).
  * Cálculo de costos por zona de entrega o retiro en el local.
  * Selector de ubicación con Google Maps (con degradación controlada a texto libre en caso de no disponer de API Key).
  * Enlace preformateado a WhatsApp (`wa.me`) para pedidos que requieran confirmación manual según `combo_regla`.
* **Panel Operativo (Dueño y Admin):**
  * Vista de pedidos agrupada por estados (`PEDIDO`, `PENDIENTE_CONFIRMACION`, `EN_PROCESO`, `ENTREGADO`, `CANCELADO`).
  * Botones de un solo toque para transición de estados sin recargar pantalla.
  * Formulario de gastos con autocompletado y creación en caliente (*on-the-fly*) de motivos y marcas.
* **Panel de Configuración (Solo Admin):**
  * CRUD de categorías, productos, reglas de combinación (`combo_regla`) y zonas de envío.

---

## 📁 Estructura del Repositorio

```text
.
├── alembic/                  # Entorno y scripts de migración de BD
│   └── versions/
├── backend/
│   ├── database/             # Conexión engine, sesiones y secuencias
│   ├── models/               # Modelos SQLModel (Base/Table/Create/Read)
│   ├── repositories/         # Capa de acceso a datos pura
│   └── services/             # Lógica de dominio y transacciones
├── frontend/
│   ├── components/           # Componentes UI reutilizables (Reflex)
│   ├── pages/                # Vistas (Público, Cocina, Gastos, Admin)
│   └── state/                # Clases rx.State (aisladas por módulo)
├── tests/                    # Tests unitarios y de integración (pytest)
├── docker-compose.yml        # Orquestación de Postgres y aplicación
├── Dockerfile
├── alembic.ini
├── rxconfig.py               # Configuración de Reflex
└── requirements.txt
