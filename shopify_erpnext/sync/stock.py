"""
stock.py
--------
Sync projected stock levels from ERPNext to Shopify.
Only unit items are synced (bundles show 0 in ERPNext Bin and are skipped).
Only active Shopify products with inventory tracking enabled are updated.
"""

import frappe
from shopify_erpnext.sync import shopify_client


def sync_stock():
    """Main entry point called by the Frappe scheduler."""
    settings = frappe.get_single("Shopify Settings")
    if not settings.enable_stock_sync:
        return

    frappe.logger().info("ERPNext -> Shopify Stock Sync Started")
    updated = skipped = failed = 0

    # Fetch projected stock directly from ERPNext database
    bins = frappe.get_all(
        "Bin",
        filters={"warehouse": settings.warehouse},
        fields=["item_code", "projected_qty"],
        limit_page_length=2000,
    )

    # Cap projected_qty at 0 — never send negative stock to Shopify
    stock_map = {
        b["item_code"]: max(0, float(b.get("projected_qty") or 0))
        for b in bins
    }
    frappe.logger().info(f"Fetched stock levels for {len(stock_map)} items from ERPNext ({settings.warehouse}).")

    try:
        inventory_map = shopify_client.get_inventory_map()
        location_id = shopify_client.get_location_id()
    except Exception as e:
        frappe.log_error(title="Shopify Stock Sync Error", message=f"Failed to fetch Shopify inventory data: {e}")
        return

    for sku, inventory_item_id in inventory_map.items():
        if sku not in stock_map:
            skipped += 1
            continue

        qty = stock_map[sku]
        try:
            shopify_client.set_inventory_level(location_id, inventory_item_id, qty)
            updated += 1
        except Exception as e:
            frappe.log_error(title="Shopify Stock Sync Error", message=f"Failed to set inventory for SKU {sku}: {e}")
            failed += 1

    frappe.log_error(title="Shopify Stock Sync Complete", message=f"Updated: {updated}, Skipped: {skipped}, Failed: {failed}")
