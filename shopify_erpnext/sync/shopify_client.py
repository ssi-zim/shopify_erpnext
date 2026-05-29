"""
shopify_client.py
-----------------
All Shopify API calls. Credentials come from the Shopify Settings DocType.
Access token is cached in Redis for 23 hours (Shopify tokens last 24 hours).
"""

import re
import requests
import frappe

SHOPIFY_API_VERSION = "2025-01"
TOKEN_CACHE_KEY = "shopify_erpnext_access_token"


def _settings():
    return frappe.get_single("Shopify Settings")


def _base_url():
    return f"https://{_settings().shop_name}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}"


def _get_access_token() -> str:
    """Fetch a Shopify access token using OAuth client credentials. Cached for 23 hours."""
    token = frappe.cache().get_value(TOKEN_CACHE_KEY)
    if token:
        return token

    s = _settings()
    url = f"https://{s.shop_name}.myshopify.com/admin/oauth/access_token"
    try:
        response = requests.post(url, json={
            "client_id": s.client_id,
            "client_secret": s.get_password("client_secret"),
            "grant_type": "client_credentials",
        }, timeout=30)
        response.raise_for_status()
    except Exception as e:
        frappe.log_error(title="Shopify Auth Error", message=str(e))
        raise

    token = response.json().get("access_token")
    frappe.cache().set_value(TOKEN_CACHE_KEY, token, expires_in_sec=82800)  # 23 hours
    return token


def _headers() -> dict:
    return {
        "X-Shopify-Access-Token": _get_access_token(),
        "Content-Type": "application/json",
    }


# ── Orders ────────────────────────────────────────────────────────────────────

def get_orders(limit: int = 50, status: str = "open") -> list:
    url = f"{_base_url()}/orders.json"
    response = requests.get(url, headers=_headers(), params={"status": status, "limit": limit}, timeout=30)
    response.raise_for_status()
    orders = response.json().get("orders", [])
    frappe.logger().info(f"Fetched {len(orders)} orders from Shopify.")
    return orders


# ── Variants / Prices ─────────────────────────────────────────────────────────

def get_all_variants() -> list:
    """Return all variants (with SKUs) from active Shopify products, handling pagination."""
    variants = []
    page_info = None

    while True:
        params = {"limit": 250, "status": "active", "fields": "id,variants"} if not page_info else \
                 {"limit": 250, "page_info": page_info}

        response = requests.get(f"{_base_url()}/products.json", headers=_headers(), params=params, timeout=30)
        response.raise_for_status()

        for product in response.json().get("products", []):
            for variant in product.get("variants", []):
                if variant.get("sku"):
                    variants.append(variant)

        link = response.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        match = re.search(r'<[^>]*page_info=([^&>]+)[^>]*>;\s*rel="next"', link)
        page_info = match.group(1) if match else None
        if not page_info:
            break

    frappe.logger().info(f"Found {len(variants)} Shopify variants with SKUs.")
    return variants


def update_variant_price(variant_id: int, price: float) -> None:
    url = f"{_base_url()}/variants/{variant_id}.json"
    response = requests.put(url, headers=_headers(),
                            json={"variant": {"id": variant_id, "price": str(price)}}, timeout=30)
    response.raise_for_status()


# ── Inventory / Stock ─────────────────────────────────────────────────────────

def get_location_id() -> int:
    """Return the first active Shopify location ID."""
    response = requests.get(f"{_base_url()}/locations.json", headers=_headers(), timeout=30)
    response.raise_for_status()
    locations = response.json().get("locations", [])
    active = [loc for loc in locations if loc.get("active")]
    if not active:
        raise Exception("No active locations found in Shopify.")
    location = active[0]
    frappe.logger().info(f"Using Shopify location: {location['name']} (ID: {location['id']})")
    return location["id"]


def get_inventory_map() -> dict:
    """Return {sku: inventory_item_id} for all active products with inventory tracking enabled."""
    inventory_map = {}
    page_info = None

    while True:
        params = {"limit": 250, "status": "active", "fields": "id,variants"} if not page_info else \
                 {"limit": 250, "page_info": page_info}

        response = requests.get(f"{_base_url()}/products.json", headers=_headers(), params=params, timeout=30)
        response.raise_for_status()

        for product in response.json().get("products", []):
            for variant in product.get("variants", []):
                sku = variant.get("sku")
                if sku and variant.get("inventory_management") == "shopify":
                    inventory_map[sku] = variant["inventory_item_id"]

        link = response.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        match = re.search(r'<[^>]*page_info=([^&>]+)[^>]*>;\s*rel="next"', link)
        page_info = match.group(1) if match else None
        if not page_info:
            break

    frappe.logger().info(f"Found {len(inventory_map)} Shopify inventory items with SKUs.")
    return inventory_map


def set_inventory_level(location_id: int, inventory_item_id: int, quantity: int) -> None:
    url = f"{_base_url()}/inventory_levels/set.json"
    response = requests.post(url, headers=_headers(), json={
        "location_id": location_id,
        "inventory_item_id": inventory_item_id,
        "available": int(quantity),
    }, timeout=30)
    if not response.ok:
        raise Exception(f"{response.status_code} - {response.text[:300]}")
