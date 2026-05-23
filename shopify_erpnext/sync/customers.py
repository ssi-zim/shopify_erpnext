"""
customers.py
------------
Find or create an ERPNext Customer from a Shopify order.
Uses phone number as the unique identifier.
"""

import frappe


def _extract_phone(order: dict) -> str:
    customer = order.get("customer") or {}
    phone = (
        customer.get("phone") or
        (order.get("billing_address") or {}).get("phone") or
        (order.get("shipping_address") or {}).get("phone") or ""
    )
    phone = str(phone).strip().replace(" ", "").replace("-", "")
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    return phone


def get_or_create_customer(order: dict) -> str | None:
    """
    Find an existing customer by phone, or create a new one.
    Returns the ERPNext customer name, or None if it could not be resolved.
    """
    customer_data = order.get("customer") or {}
    phone = _extract_phone(order)

    if not phone:
        frappe.logger().warning(
            f"Shopify order {order.get('name')} has no phone number — skipping customer sync."
        )
        return None

    # Check if customer already exists
    existing = frappe.db.get_value("Customer", {"mobile_no": phone}, "name")
    if existing:
        return existing

    # Build customer name
    first = (customer_data.get("first_name") or "").strip()
    last = (customer_data.get("last_name") or "").strip()
    name = f"{first} {last}".strip() or phone

    settings = frappe.get_single("Shopify Settings")

    try:
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Individual",
            "customer_group": "Individual",
            "territory": "Zimbabwe",
            "mobile_no": phone,
            "email_id": (customer_data.get("email") or "").strip(),
            "company": settings.company,
        })
        customer.insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info(f"Created customer: {name} ({phone})")

        # Create linked address if available
        _create_address(customer.name, name, order, phone)

        return customer.name

    except Exception as e:
        frappe.logger().error(f"Failed to create customer {name}: {e}")
        return None


def _create_address(customer_name: str, display_name: str, order: dict, phone: str) -> None:
    addr = order.get("shipping_address") or order.get("billing_address") or {}
    if not addr.get("address1"):
        return

    try:
        address = frappe.get_doc({
            "doctype": "Address",
            "address_title": display_name,
            "address_type": "Billing",
            "address_line1": addr.get("address1", ""),
            "city": addr.get("city") or "Harare",
            "country": addr.get("country") or "Zimbabwe",
            "phone": phone,
            "is_primary_address": 1,
            "links": [{
                "link_doctype": "Customer",
                "link_name": customer_name,
            }],
        })
        address.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.logger().warning(f"Could not create address for {display_name}: {e}")
