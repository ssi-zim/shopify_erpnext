app_name = "shopify_erpnext"
app_title = "Shopify ERPNext"
app_publisher = "Silver Stream Distribution"
app_description = "Shopify to ERPNext Integration"
app_version = "1.0.0"
app_email = ""
app_license = "MIT"

# Scheduled tasks
# Orders sync every 15 minutes
# Prices and stock sync every hour
scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "shopify_erpnext.sync.orders.sync_orders",
        ],
        "0 * * * *": [
            "shopify_erpnext.sync.prices.sync_prices",
            "shopify_erpnext.sync.stock.sync_stock",
        ],
    }
}
