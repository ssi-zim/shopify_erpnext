# Shopify ERPNext Integration

A Frappe app that syncs Shopify orders, customers, prices, and stock with ERPNext.

## What it does

- Pulls new Shopify orders and creates Sales Orders in ERPNext (every 15 minutes)
- Syncs customers from Shopify to ERPNext using phone number as the unique identifier
- Syncs prices from ERPNext (Standard Selling) to Shopify (every hour)
- Syncs projected stock from ERPNext to Shopify (every hour)

## Installation on Frappe Cloud

1. Push this repo to GitHub (must be public)
2. Log in to [frappecloud.com](https://frappecloud.com)
3. Go to your site -> **Apps** -> **Install App**
4. Enter your GitHub repo URL
5. Install the app on your site

## Setup after installation

1. In ERPNext, go to **Shopify Settings** (search in the top bar)
2. Fill in your Shopify credentials (Shop Name, Client ID, Client Secret)
3. Set your Company and Warehouse
4. Enable the sync options you want
5. Save

The scheduler will start running automatically.

## Sync Schedule

| Sync        | Frequency    |
|-------------|-------------|
| Orders      | Every 15 min |
| Prices      | Every hour   |
| Stock       | Every hour   |
