# ⚡ Bitaxe Performance Dashboard

Dashboard avanzado para monitorizar mineros **Bitaxe / NerdAxe** en tiempo real, con análisis de shares, buckets, probabilidades y evolución temporal.

Diseñado para minería tipo *solo/lottery*, donde el valor está en entender la calidad de los hashes, no solo el hashrate.

---

## 🚀 Características

### 📡 Monitorización en tiempo real
- Hashrate, temperatura, best share
- Probabilidad estimada de bloque (%)
- Datos de red (dificultad, precio, valor del bloque)

---

## 📊 Visualización avanzada

### 🟡 Scatter (distribución de shares)
- Clasificación por buckets:
  - `100k+`
  - `1M+`
  - `10M+`
  - `100M+`
  - `1G+`
- Colores consistentes en todo el dashboard

### 🔵 Timeline (evolución temporal)
- Gráfica lineal: **tiempo vs dificultad**
- Permite detectar:
  - rachas buenas
  - periodos muertos
  - comportamiento del minero

### 🟢 Pie chart (distribución)
- Proporción de shares por bucket

### 📋 Tabla avanzada
- Ordenación por columnas
- Paginación
- Datos persistentes (SQLite)

Incluye:
- diff
- hashrate
- temperatura
- % probabilidad
- diff restante para bloque
- timestamp completo

---

## 🧠 Análisis inteligente

El sistema calcula automáticamente:

```text
percent = (1 - e^(-diff / network_diff)) * 100
remaining = network_diff - share_diff```


## 🪙 Soporte multi-coin

Seleccionable en tiempo real:

- BTC
- BSV
- FCH

Incluye:
- dificultad de red
- precio en USD
- valor del bloque

---

## 🗄️ Persistencia

Base de datos SQLite:

### shares
Histórico general (cada ~10s)

### big_shares
Shares relevantes (>100k diff):
- bucket
- hashrate
- temperatura
- probabilidad
- diff restante
- timestamp

---

## ⚙️ Arquitectura

### Backend
- Python (Flask + Socket.IO)
- WebSocket con mineros
- API REST
- SQLite

### Frontend
- HTML + JavaScript
- Chart.js
- Socket.IO client

---

## 🔌 Endpoints

| Endpoint | Descripción |
|----------|------------|
| `/` | Dashboard |
| `/big/<miner>` | Shares relevantes |
| `/history/<miner>` | Histórico |
| `/set_coin` | Cambiar moneda |
| `/buckets/<miner>` | Conteo buckets |
| `/big_count/<miner>` | Total registros |

---

## 📦 Instalación

```bash
git clone <repo>
cd bitaxe-performance-dashboard
pip install flask flask-socketio requests websocket-client


## ▶️ Ejecución

```bash
python app.py


## Abrir en navegador:

http://localhost:5000


##⚡ Configuración

Editar en app.py:

BITAXES = {
    "gamma": "192.168.1.208",
    "nerd": "192.168.1.212"
}

