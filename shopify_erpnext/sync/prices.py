"""
prices.py
---------
Sync item prices from ERPNext (Standard Selling) to Shopify product variants.
Only active Shopify products are updated.
"""

import frappe
from shopify_erpnext.sync import shopify_client


def sync_prices():
    """Main entry point called by the Frappe scheduler."""
    settings = frappe.get_single("Shopify Settings")
    if not settings.enable_price_sync:
        return

    frappe.logger().info("ERPNext -> Shopify Price Sync Started")
    updated = skipped = failed = 0

    # Fetch prices directly from ERPNext database
    prices = frappe.get_all(
        "Item Price",
        filters={"price_list": "Standard Selling", "selling": 1},
        fields=["item_code", "price_list_rate"],
    )
    frappe.logger().info(f"Fetched {len(prices)} item prices from ERPNext (Standard Selling).")
    price_map = {p["item_code"]: p["price_list_rate"] for p in prices}

    try:
        variants = shopify_client.get_all_variants()
    except Exception as e:
        frappe.log_error(title="Shopify Price Sync Error", message=f"Failed to fetch variants: {e}")
        return

    for variant in variants:
        sku = variant.get("sku")
        if not sku or sku not in price_map:
            skipped += 1
            continue

        new_price = price_map[sku]
        try:
            shopify_client.update_variant_price(variant["id"], new_price)
            updated += 1
        except Exception as e:
            frappe.log_error(title="Shopify Price Sync Error", message=f"Failed to update SKU {sku}: {e}")
            failed += 1

    frappe.log_error(title="Shopify Price Sync Complete", message=f"Updated: {updated}, Skipped: {skipped}, Failed: {failed}")
