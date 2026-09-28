"""
tradezero_client.py
-------------------
Cliente oficial REST de TradeZero (ejecución / cuenta / posiciones).

IMPORTANTE:
  La Trading API de TradeZero NO entrega cotizaciones ni barras históricas.
  Market data sigue viniendo de Alpaca / Finviz / Yahoo / Twelve Data / FINRA.
  TradeZero se usa para:
    - listar cuentas y buying power
    - posiciones abiertas y P&L
    - enviar / cancelar órdenes (paper o live según tus keys)
    - short locates (si tu cuenta lo permite)

Documentación: https://developer.tradezero.com/
Base URL:     https://webapi.tradezero.com/v1/api
Auth headers: TZ-API-KEY-ID + TZ-API-SECRET-KEY

Uso rápido:
  from tradezero_client import TradeZeroClient
  tz = TradeZeroClient.from_env()
  print(tz.list_accounts())
  print(tz.get_positions())
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

import requests

logger = logging.getLogger("tradezero_client")

BASE_URL = "https://webapi.tradezero.com/v1/api"


class TradeZeroError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class TradeZeroClient:
    def __init__(
        self,
        api_key_id: str,
        api_secret: str,
        account_id: str = "",
        timeout: int = 30,
    ):
        if not api_key_id or not api_secret:
            raise TradeZeroError(
                "Faltan TZ_API_KEY_ID / TZ_API_SECRET_KEY. "
                "Genéralas en el portal TradeZero (paper primero)."
            )
        self.api_key_id = api_key_id.strip()
        self.api_secret = api_secret.strip()
        self.account_id = (account_id or "").strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "TZ-API-KEY-ID": self.api_key_id,
                "TZ-API-SECRET-KEY": self.api_secret,
            }
        )

    @classmethod
    def from_env(cls) -> "TradeZeroClient":
        """Lee credenciales desde variables de entorno / .env."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        return cls(
            api_key_id=os.getenv("TZ_API_KEY_ID", ""),
            api_secret=os.getenv("TZ_API_SECRET_KEY", "") or os.getenv("TZ_API_SECRET", ""),
            account_id=os.getenv("TZ_ACCOUNT_ID", ""),
        )

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = self._url(path)
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise TradeZeroError(f"Error de red TradeZero: {e}") from e

        if resp.status_code == 429:
            raise TradeZeroError("Rate limit 429 — espera ~2s y reintenta", 429)

        if resp.status_code >= 400:
            body: Any
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise TradeZeroError(
                f"TradeZero HTTP {resp.status_code}: {body}",
                status_code=resp.status_code,
                body=body,
            )

        if not resp.content:
            return None
        try:
            return resp.json()
        except Exception:
            return resp.text

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------
    def list_accounts(self) -> list:
        data = self._request("GET", "/accounts")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("accounts") or data.get("data") or [data]
        return []

    def ensure_account_id(self) -> str:
        if self.account_id:
            return self.account_id
        accounts = self.list_accounts()
        if not accounts:
            raise TradeZeroError("La API no devolvió ninguna cuenta para estas keys.")
        first = accounts[0]
        self.account_id = (
            first.get("account")
            or first.get("accountId")
            or first.get("id")
            or ""
        )
        if not self.account_id:
            raise TradeZeroError(f"No se pudo extraer accountId de: {first}")
        logger.info(f"TradeZero accountId detectado: {self.account_id}")
        return self.account_id

    def get_account(self, account_id: str = "") -> dict:
        aid = account_id or self.ensure_account_id()
        return self._request("GET", f"/account/{aid}") or {}

    def get_pnl(self, account_id: str = "") -> dict:
        aid = account_id or self.ensure_account_id()
        return self._request("GET", f"/accounts/{aid}/pnl") or {}

    def get_positions(self, account_id: str = "") -> list:
        aid = account_id or self.ensure_account_id()
        data = self._request("GET", f"/accounts/{aid}/positions")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("positions") or data.get("data") or []
        return []

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def list_orders_today(self, account_id: str = "") -> list:
        aid = account_id or self.ensure_account_id()
        data = self._request("GET", f"/accounts/{aid}/orders")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("orders") or data.get("data") or []
        return []

    def get_order(self, client_order_id: str, account_id: str = "") -> dict:
        aid = account_id or self.ensure_account_id()
        return self._request("GET", f"/accounts/{aid}/order/{client_order_id}") or {}

    def get_routes(self, account_id: str = "") -> list:
        aid = account_id or self.ensure_account_id()
        data = self._request("GET", f"/accounts/{aid}/routes")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("routes") or data.get("data") or []
        return []

    def place_equity_order(
        self,
        symbol: str,
        quantity: int,
        side: str = "Buy",
        open_close: str = "Open",
        order_type: str = "Limit",
        time_in_force: str = "Day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: str = "",
        route: str = "",
        account_id: str = "",
        dry_run: bool = False,
    ) -> dict:
        """
        Coloca una orden de acciones.

        side: "Buy" | "Sell"  (Short = Sell+Open, Cover = Buy+Close)
        order_type: "Market" | "Limit" | "Stop" | "StopLimit"
        time_in_force: "Day" | "GoodTillCancel" | "DayPlus" | ...
        """
        aid = account_id or self.ensure_account_id()
        symbol = symbol.strip().upper()
        qty = int(quantity)
        if qty < 1:
            raise TradeZeroError("orderQuantity debe ser >= 1 (sin fracciones).")

        body: dict[str, Any] = {
            "securityType": "Stock",
            "symbol": symbol,
            "side": side,
            "openClose": open_close,
            "orderType": order_type,
            "orderQuantity": qty,
            "timeInForce": time_in_force,
            "clientOrderId": client_order_id or f"tz-{uuid.uuid4().hex[:16]}",
        }
        if limit_price is not None:
            body["limitPrice"] = float(limit_price)
        if stop_price is not None:
            body["stopPrice"] = float(stop_price)
        if route:
            body["route"] = route

        if dry_run:
            logger.info(f"[DRY-RUN] Orden que se enviaría: {body}")
            return {"dry_run": True, "payload": body}

        return self._request("POST", f"/accounts/{aid}/order", json=body) or {}

    def buy_limit(
        self,
        symbol: str,
        quantity: int,
        limit_price: float,
        time_in_force: str = "Day",
        dry_run: bool = True,
        **kwargs,
    ) -> dict:
        """Compra long con límite. Por defecto dry_run=True (seguro)."""
        return self.place_equity_order(
            symbol=symbol,
            quantity=quantity,
            side="Buy",
            open_close="Open",
            order_type="Limit",
            limit_price=limit_price,
            time_in_force=time_in_force,
            dry_run=dry_run,
            **kwargs,
        )

    def sell_limit_close(
        self,
        symbol: str,
        quantity: int,
        limit_price: float,
        dry_run: bool = True,
        **kwargs,
    ) -> dict:
        """Cierra long con límite."""
        return self.place_equity_order(
            symbol=symbol,
            quantity=quantity,
            side="Sell",
            open_close="Close",
            order_type="Limit",
            limit_price=limit_price,
            dry_run=dry_run,
            **kwargs,
        )

    def cancel_order(self, client_order_id: str, account_id: str = "") -> Any:
        aid = account_id or self.ensure_account_id()
        return self._request("DELETE", f"/accounts/{aid}/orders/{client_order_id}")

    def is_easy_to_borrow(self, symbol: str, account_id: str = "") -> bool:
        aid = account_id or self.ensure_account_id()
        data = self._request(
            "GET", f"/accounts/{aid}/is-easy-to-borrow/symbol/{symbol.upper()}"
        )
        if isinstance(data, dict):
            return bool(data.get("isEasyToBorrow"))
        return False

    def test_connection(self) -> dict:
        """Prueba real: lista cuentas + opcionalmente posiciones."""
        accounts = self.list_accounts()
        aid = self.ensure_account_id()
        positions = []
        pnl = {}
        try:
            positions = self.get_positions(aid)
            pnl = self.get_pnl(aid)
        except TradeZeroError as e:
            logger.warning(f"Posiciones/PnL no disponibles aún: {e}")
        return {
            "ok": True,
            "account_id": aid,
            "accounts_count": len(accounts),
            "positions_count": len(positions),
            "pnl_summary": {
                k: pnl.get(k)
                for k in ("accountValue", "availableCash", "dayPnl", "exposure")
                if isinstance(pnl, dict) and k in pnl
            },
        }


def main():
    """CLI de diagnóstico: python tradezero_client.py"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("=== TradeZero connection test ===")
    print("Market data NO viene de TradeZero — solo ejecución/cuenta.")
    try:
        tz = TradeZeroClient.from_env()
        result = tz.test_connection()
        print("OK →", result)
        print("\nCuentas:")
        for a in tz.list_accounts():
            print(" ", a)
        print("\nPosiciones:")
        for p in tz.get_positions():
            print(" ", p)
    except TradeZeroError as e:
        print("ERROR:", e)
        print(
            "\nConfigura en .env:\n"
            "  TZ_API_KEY_ID=...\n"
            "  TZ_API_SECRET_KEY=...\n"
            "  TZ_ACCOUNT_ID=...   (opcional; se detecta solo)\n"
            "Usa keys PAPER primero."
        )


if __name__ == "__main__":
    main()
