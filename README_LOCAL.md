# Small Cap Bot — Instalación LOCAL (VS Code + Python 3.12)

Misma potencia que Streamlit Cloud (screening, dual motor, Halt, Short FINRA,
Confianza, perfiles Premarket/Regular/After-Hours, Scalp LISTO), más:

- Corre en tu laptop (más rápido, sin sleep de la nube)
- Cliente **TradeZero** para cuenta / posiciones / órdenes (paper o live)
- **Market data sigue siendo multi-fuente** (Alpaca, Finviz, Yahoo, Twelve Data, FINRA, Nasdaq RSS)

## Importante sobre TradeZero

La API oficial de TradeZero es de **ejecución**, no de cotizaciones:

| Qué sí | Qué no |
|--------|--------|
| Cuentas, buying power, P&L | Quotes / Level 2 |
| Posiciones y órdenes | Barras históricas / charts |
| Enviar/cancelar órdenes | Scanner de gaps |
| Short locates | RVOL / float |

Por eso el bot **mantiene** Alpaca + Finviz + etc. para datos, y TradeZero
como **broker opcional** para ejecutar cuando tú lo decidas.

## Requisitos

- Python **3.12.x** (tienes 3.12.3 — perfecto)
- VS Code
- Keys Alpaca (paper) y, si quieres, keys TradeZero **paper** primero

## Instalación (Windows)

1. Copia esta carpeta donde quieras, ej. `C:\bots\smallcaps_bot`
2. Copia `.env.example` → `.env` y rellena keys
3. En VS Code abre la carpeta
4. Terminal:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

O doble clic en `scripts\run_local.bat`

## Probar TradeZero (sin enviar órdenes reales)

```bat
.venv\Scripts\activate
python tradezero_client.py
```

Debe listar tus cuentas paper. Si falla, revisa `TZ_API_KEY_ID` y `TZ_API_SECRET_KEY`.

## Enviar una orden paper (manual, con dry_run)

```python
from tradezero_client import TradeZeroClient

tz = TradeZeroClient.from_env()
# Solo simula el payload (no envía):
print(tz.buy_limit("AAPL", quantity=1, limit_price=1.00, dry_run=True))

# Para enviar de verdad en PAPER (¡solo con keys paper!):
# print(tz.buy_limit("AAPL", quantity=1, limit_price=1.00, dry_run=False))
```

## Nube + local

- **Local**: desarrollas y operas más rápido
- **GitHub → Streamlit Cloud**: mismo código para mirar el panel fuera de casa
- No subas el archivo `.env` a GitHub (ya está en `.gitignore`)

## Arquitectura de datos (no cambia)

```
Scanner (TradingView/Finviz)
    → DataFetcher (Alpaca IEX, Finviz float, Yahoo, Twelve Data, Tiingo…)
    → Screener (Clásico / Smart + Halt + Short + Confianza + Sesión)
    → UI Streamlit
    → Ejecución: Alpaca paper  y/o  TradeZero (cuando actives el puente)
```

## Seguridad

1. Empieza siempre con keys **paper** de TradeZero y Alpaca.
2. `buy_limit(..., dry_run=True)` por defecto.
3. No automatices órdenes live hasta validar paper varios días.
