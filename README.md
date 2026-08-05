# FBR Digital Invoicing
ERPNext / Frappe App

---

## Overview

FBR Digital Invoicing is a Frappe / ERPNext application that integrates Pakistan FBR Digital Invoicing API with Sales Invoices.
It automates invoice submission, scenario handling, QR code generation, and maintains complete API logs.

---

## Main Features

- Supports ERPNext v14 and above
- Secure integration with FBR Digital Invoicing API
- Automatic invoice submission on Sales Invoice submit
- Supports Sandbox and Production environments
- Automatic FBR Scenario determination
- Generates FBR Invoice Number
- Generates QR Code for invoice verification
- HS Code based UOM auto-fetch
- Supports Registered and Unregistered buyers
- Supports Fixed Notified Value / Retail Price
- Handles Further Tax, Zero Rated, Exempt, and Reduced Rate scenarios
- Supports multiple tax components
- User-friendly validation messages
- Full API request and response logging
- Error tracking via FDI Request Log
- Token-based authentication

---

## Supported Scenarios


- SN001 - Registered Buyer
- SN002 - Unregistered Buyer
- SN005 – Reduced Rate
- SN006 – Exempt
- SN007 – Zero Rated
- SN008 – Third Schedule
- SN017 – Processing
- SN024 – SRO Based
- SN026 – Retail Sale
- SN027 – SRO Item Based
- SN028 – Retail Reduced Rate

---

## Installation

### Frappe Cloud

One-click installation available from Frappe Cloud Marketplace.

---

### Self Hosting

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/UniVenture-Solutions/fbr_digital_invoicing.git --branch version-15
bench --site your.site.name install-app fbr_digital_invoicing
bench migrate
bench restart

Configuration:
Configure FBR Digital Invoicing Settings:

Environment (Sandbox / Production)

API Base URL

Authorization Token

Seller NTN / CNIC mapping

Usage:

Configure FBR Digital Invoicing Settings

Create or update a Sales Invoice

Select FBR Sale Type

Add HS Codes on items

Enable Post to FBR Digital Invoicing

Submit the invoice

Upon successful submission, the system generates:

FBR Invoice Number

QR Code

API Logs

Logging and Debugging:

All API requests, responses, and errors are stored in FDI Request Log

Validation errors are displayed during invoice submission

Dependencies:

Frappe Framework

ERPNext

Python

Requests

PyQRCode

Contributing:

Contribution guidelines follow ERPNext standards:

Issue Guidelines

Pull Request Requirements

License:

MIT License
