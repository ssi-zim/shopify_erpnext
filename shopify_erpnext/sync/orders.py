"""
orders.py
---------
Pull open orders from Shopify and create Sales Orders in ERPNext.
Duplicate detection uses frappe.db directly — no local JSON file needed.
"""

import frappe
from shopify_erpnext.sync import shopify_client
from shopify_erpnext.sync.customers import get_or_create_customer


def _is_synced(shopify_order_id: str) -> bool:
    return frappe.db.exists("Sales Order", {"custom_shopify_id": shopify_order_id}) is not None


def _map_order(shopify_order: dict, customer_name: str) -> dict:
    settings = frappe.get_single("Shopify Settings")

    items = []
    for line in shopify_order.get("line_items", []):
        sku = line.get("sku") or str(line.get("variant_id", ""))
        items.append({
            "item_code": sku,
            "qty": float(line.get("quantity", 1)),
            "rate": float(line.get("price", 0)),
            "warehouse": settings.warehouse,
            "description": line.get("name", ""),
        })

    # Always add delivery charge
    items.append({
        "item_code": "DEL1",
        "qty": 1,
        "warehouse": settings.warehouse,
    })

    order_date = shopify_order.get("created_at", "")[:10]

    addr = shopify_order.get("shipping_address") or shopify_order.get("billing_address") or {}
    parts = [addr.get(k) or "" for k in ["name", "address1", "address2", "city", "province", "zip", "country", "phone"]]
    shipping_address = ", ".join(p for p in parts if p)

    return {
        "doctype": "Sales Order",
        "naming_series": "SAL-ORD-.YYYY.-",
        "customer": customer_name,
        "company": settings.company,
        "transaction_date": order_date,
        "delivery_date": order_date,
        "order_type": "Sales",
        "currency": shopify_order.get("currency", "USD"),
        "items": items,
        "shipping_address": shipping_address,
        "custom_shopify_id": str(shopify_order.get("id", "")),
        "custom_shopify_order_number": shopify_order.get("name", ""),
        "custom_notes": shopify_order.get("note") or "",
    }


def sync_orders():
    """Main entry point called by the Frappe scheduler."""
    settings = frappe.get_single("Shopify Settings")
    if not settings.enable_order_sync:
        return

    frappe.logger().info("=" * 50)
    frappe.logger().info("Shopify -> ERPNext Order Sync Started")
    frappe.logger().info("=" * 50)

    created = skipped = failed = 0

    try:
        orders = shopify_client.get_orders(
            limit=settings.sync_order_limit or 50,
            status=settings.order_status or "open",
        )
    except Exception as e:
        frappe.logger().error(f"Failed to fetch orders from Shopify: {e}")
        return

    frappe.logger().info(f"Starting sync for {len(orders)} orders...")

    for order in orders:
        shopify_order_id = str(order.get("id", ""))
        order_number = order.get("name", shopify_order_id)

        if _is_synced(shopify_order_id):
            frappe.logger().info(f"Order {order_number} already synced — skipping.")
            skipped += 1
            continue

        customer_name = get_or_create_customer(order)
        if not customer_name:
            frappe.logger().error(f"Order {order_number} skipped — could not resolve customer.")
            failed += 1
            continue

        try:
            order_data = _map_order(order, customer_name)
            doc = frappe.get_doc(order_data)
            doc.insert(ignore_permissions=True)

            try:
                doc.submit()
                frappe.logger().info(f"Order {order_number} -> {doc.name} [Submitted]")
            except Exception as submit_err:
                frappe.logger().warning(
                    f"Order {order_number} -> {doc.name} [Draft - needs review]: {submit_err}"
                )

            frappe.db.commit()
            created += 1

        except Exception as e:
            frappe.logger().error(f"Order {order_number} failed to create: {e}")
            frappe.db.rollback()
            failed += 1

    frappe.logger().info("-" * 50)
    frappe.logger().info(f"Order Sync complete. Created: {created}, Skipped: {skipped}, Failed: {failed}")
