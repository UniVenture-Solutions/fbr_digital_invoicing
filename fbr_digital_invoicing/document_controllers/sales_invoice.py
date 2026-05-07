import frappe
import json
import ast
import re
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice as SalesInvoiceController
from fbr_digital_invoicing.api import FBRDigitalInvoicingAPI  
from frappe.utils import cint
from frappe.utils import get_link_to_form
from frappe.exceptions import ValidationError
import pyqrcode


class SalesInvoice(SalesInvoiceController):
    def before_submit(self):
        if not self.custom_post_to_fdi:
            return
        if self.fbr_sale_type.furthertax:
            try:
                rate = self.taxes[1].rate
            except (IndexError, AttributeError):
                rate = None

            if not rate or rate <= 0:
                frappe.throw("Please select a valid Further Tax Rate")

        settings = frappe.get_doc("FBR Digital Invoicing Settings")
        
        try:
            endpoint = ""
            end_points = {
                "production": "di_data/v1/di/postinvoicedata",
                "sandbox": "di_data/v1/di/postinvoicedata_sb"
            }
            if settings.get("environment") == "production":
                endpoint = end_points.get("production")
            elif settings.get("environment") == "sandbox":
                endpoint = end_points.get("sandbox")
            else:
                frappe.throw("Please select a valid environment")
            

            api = FBRDigitalInvoicingAPI(self.company)
            response = api.make_request("POST", endpoint, self.get_mapped_data())
            response = self.normalize_fbr_response(response)

            if not isinstance(response, dict):
                frappe.log_error(
                    title="FBR Invoicing API Error",
                    message=frappe.as_json(response, indent=4)
                )
                frappe.throw("Invalid response from FBR Invoicing API. Please check FDI Request Log.")

            resdata = response.get("validationResponse")
            if not resdata and all(k in response for k in ("status", "statusCode")):
                resdata = response

            if isinstance(resdata, str):
                try:
                    resdata = frappe.parse_json(resdata)
                except Exception:
                    try:
                        resdata = json.loads(resdata)
                    except Exception:
                        resdata = None

            if not resdata or not isinstance(resdata, dict):
                frappe.log_error(
                    title="FBR Invoicing API Error",
                    message=frappe.as_json(response, indent=4)
                )
                frappe.throw("Invalid response from FBR Invoicing API. Please check FDI Request Log.")
            
            if resdata.get("status") == "Valid":
                self.custom_fbr_invoice_no = response.get("invoiceNumber")
                self.custom_qr_code = None
                frappe.msgprint("Invoice successfully validated by FBR.")
            else:
                frappe.log_error(
                    title="FBR Invoicing API Error",
                    message=frappe.as_json(response, indent=4)
                )

                error_message = resdata.get("error") or "FBR rejected the invoice."
                friendly_hint = self.get_fbr_validation_hint(resdata)
                frappe.throw(f"{error_message} {friendly_hint}".strip())
                  
                
        except Exception as e:
            if isinstance(e, ValidationError):
                raise

            frappe.log_error(
               title="FBR Invoicing API Error",
               message=frappe.get_traceback()
            )

            frappe.throw(f"Error while submitting invoice to FBR: {str(e)}")

    def on_submit(self):
        super().on_submit()
        if not self.custom_post_to_fdi:
            return
        if not self.custom_fbr_invoice_no:
            return

        url = pyqrcode.create(self.custom_fbr_invoice_no)
        url.svg(frappe.get_site_path() + '/public/files/' + self.name + '_online_qrcode.svg', scale=8)
        self.custom_qr_code = '/files/' + self.name + '_online_qrcode.svg'
        frappe.db.set_value("Sales Invoice", self.name, "custom_qr_code", self.custom_qr_code)
        frappe.msgprint("Invoice successfully submitted to FBR Invoice.")
        
    def get_mapped_data(self):

        
        data = {}
        data["invoiceType"] = "Sale Invoice"
        data["invoiceDate"] = self.posting_date
        
        data["sellerNTNCNIC"] = self.company_tax_id
        data["sellerBusinessName"] = self.company
        data["sellerProvince"] = frappe.db.get_value("Company", self.company, "custom_province")  # Default to Sindh if not set
        # Uncomment the next line if you have a seller address field
        # data["sellerAddress"] =self.company_address
        
        
        data["buyerNTNCNIC"] = self.tax_id if self.tax_id else ""
        data["buyerBusinessName"] = self.customer_name
        data["buyerProvince"] = self.territory
        data["buyerAddress"] = self.customer_address
        data["buyerRegistrationType"] = "Unregistered" if not self.tax_id else "Registered"
        data["scenarioId"] = self.fbr_sale_type.scenarioid
        
       
        data["items"] = self.get_items()
        return data
    
    def get_items(self):
        settings = frappe.get_doc("FBR Digital Invoicing Settings")
        items = []
        taxes = self.taxes or []
        sales_tax_rate = taxes[0].rate if len(taxes) > 0 else 0
        for item in self.items:
            further_tax = 0
            uom = self.get_and_set_uom(item.custom_hs_code)
            tax_amount = round(item.amount * (sales_tax_rate / 100), 2) if sales_tax_rate else 0
            try:
                tax_rate = taxes[1].rate
                if tax_rate and tax_rate > 0:
                    further_tax = round(item.amount * (tax_rate / 100), 2)
            except IndexError:
                further_tax = 0  

            item_data = {
                "hsCode": item.custom_hs_code,  # Default HS Code if not set
                "productDescription": f"{item.item_code}-{item.idx}" if settings.get("make_items_unique") == 1 else item.item_code,
                "rate":"Exempt" if self.fbr_sale_type.tax_exempted else f"{cint(sales_tax_rate)}%",
                "uoM": uom,
                "quantity": item.qty,
                "totalValues": round(item.amount + tax_amount, 2),  # Placeholder, adjust as needed
                "valueSalesExcludingST": round(item.amount, 2),
                "fixedNotifiedValueOrRetailPrice":round(item.rate,2) if self.fbr_sale_type.fixednotifiedvalueorretailprice else 0,  # Placeholder, adjust as needed
                "salesTaxApplicable": tax_amount if tax_amount > 0 else 0,  # Assuming first tax is sales tax
                "salesTaxWithheldAtSource": 0,  # Placeholder, adjust as needed
                "extraTax": "",  # Placeholder, adjust as needed
                "furtherTax": further_tax if self.fbr_sale_type.furthertax else 0,  # Assuming first tax is further tax
                "sroScheduleNo": self.fbr_sale_type.sroscheduleno or "",  # Placeholder, adjust as needed
                "fedPayable": 0,  # Placeholder, adjust as needed
                "discount": 0,
                "saleType": self.fbr_sale_type.saletype,  # Adjust based on your logic
                "sroItemSerialNo": self.fbr_sale_type.sroitemserialno or ""   
            }
            items.append(item_data)
        return items

    def get_and_set_uom(self, hs_code):
        hs_code_doc = frappe.new_doc("HS Code")
        if frappe.db.exists("HS Code", hs_code):
            hs_code_doc = frappe.get_doc("HS Code", hs_code)
        
        api = FBRDigitalInvoicingAPI(self.company) 
        response = api.make_request("GET", f"/pdi/v2/HS_UOM?hs_code={hs_code}&annexure_id=3")
        if not response:
            return None

        uom = None
        if isinstance(response, list) and response:
            uom = response[0].get("description")
        elif isinstance(response, dict):
            uom = response.get("description")
            if not uom and isinstance(response.get("data"), list) and response.get("data"):
                uom = response.get("data")[0].get("description")

        if uom:
            hs_code_doc.hs_code = hs_code
            hs_code_doc.uom = uom
            hs_code_doc.save()
            return uom
        return None

    def get_fbr_validation_hint(self, validation_response):
        error_code = (validation_response or {}).get("errorCode")
        error_text = (validation_response or {}).get("error", "")

        # Seller province missing/invalid -> Company.custom_province
        if error_code == "0073" or "seller province" in (error_text or "").lower():
            company_link = get_link_to_form("Company", self.company)
            return f"Please set Seller Province in Company {company_link}."

        return ""

    def normalize_fbr_response(self, response):
        if isinstance(response, dict):
            return response
        if isinstance(response, list) and response:
            if isinstance(response[0], dict):
                return response[0]
            return None
        if isinstance(response, (bytes, bytearray)):
            try:
                response = response.decode("utf-8", errors="ignore")
            except Exception:
                return None
        if isinstance(response, str):
            s = response.strip()
            try:
                return frappe.parse_json(s)
            except Exception:
                pass
            try:
                return json.loads(s)
            except Exception:
                pass
            if s.startswith("b'") or s.startswith('b"'):
                try:
                    literal = ast.literal_eval(s)
                    if isinstance(literal, (bytes, bytearray)):
                        s = literal.decode("utf-8", errors="ignore").strip()
                        try:
                            return json.loads(s)
                        except Exception:
                            pass
                except Exception:
                    pass
            try:
                literal = ast.literal_eval(s)
                if isinstance(literal, dict):
                    return literal
            except Exception:
                pass
            if "{" in s and "}" in s:
                snippet = s[s.find("{"): s.rfind("}") + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    try:
                        literal = ast.literal_eval(snippet)
                        if isinstance(literal, dict):
                            return literal
                    except Exception:
                        pass
                    match = re.search(r"\{.*\}", s, flags=re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group(0))
                        except Exception:
                            try:
                                literal = ast.literal_eval(match.group(0))
                                if isinstance(literal, dict):
                                    return literal
                            except Exception:
                                return None
        return None
    @property
    def fbr_sale_type(self):
        custom_fbr_sale_type = self.custom_fbr_sale_type
        if custom_fbr_sale_type:
            sale_type = frappe.get_doc("FBR Sale Type", custom_fbr_sale_type)
            return sale_type
        else:
            frappe.throw("Please select a valid Fbr Sale Type")
        
            
        
