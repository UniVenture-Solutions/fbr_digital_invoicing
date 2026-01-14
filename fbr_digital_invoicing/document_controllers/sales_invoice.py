import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice as SalesInvoiceController
from fbr_digital_invoicing.api import FBRDigitalInvoicingAPI  
from frappe.utils import cint
import pyqrcode


class SalesInvoice(SalesInvoiceController):
    def on_submit(self):
        super().on_submit()
        if not self.custom_post_to_fdi:
            return
        if self.fbr_sale_type.furthertax:
            try:
                rate = self.taxes[1].rate
            except (IndexError, AttributeError):
                rate = None

            if not rate or rate <= 0:
                frappe.throw("Please select a valid Further Tax Rate")

        data = self.get_mapped_data()
        api_log = frappe.new_doc("FDI Request Log")
        api_log.request_data = frappe.as_json(data, indent=4)
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
            

            api = FBRDigitalInvoicingAPI()
            response = api.make_request("POST", endpoint, self.get_mapped_data())
            resdata = response.get("validationResponse")
            
            if resdata.get("status") == "Valid":
                self.custom_fbr_invoice_no = response.get("invoiceNumber")
                frappe.db.set_value("Sales Invoice", self.name, "custom_fbr_invoice_no", self.custom_fbr_invoice_no)
                url = pyqrcode.create(self.custom_fbr_invoice_no)
                url.svg(frappe.get_site_path()+'/public/files/'+self.name+'_online_qrcode.svg', scale=8)
                self.custom_qr_code = '/files/'+self.name+'_online_qrcode.svg'
                frappe.db.set_value("Sales Invoice", self.name, "custom_qr_code", self.custom_qr_code)
                api_log.response_data = frappe.as_json(response, indent=4)
                api_log.save()
                frappe.msgprint("Invoice successfully submitted to FBR Invoice.")
            else:
                api_log.response_data = frappe.as_json(response, indent=4)
                api_log.save()
                frappe.log_error(
                    title="FBR Invoicing API Error",
                    message=frappe.as_json(response, indent=4)
                )
                frappe.throw(
                    "Error in FBR Invoicing" 
                )
                  
                
        except Exception as e:
            api_log.error = frappe.as_json(e, indent=4)
            api_log.save()
                
            frappe.log_error(
               title="FBR Invoicing API Error",
               message=frappe.as_json(response, indent=4)
            )
            
            frappe.throw(f"Error while submitting invoice to FBR: {str(e)}")

        # api_log.save()
        
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
        frappe.log_error(frappe.as_json(data,indent=4),"test")
        return data
    
    def get_items(self):
        settings = frappe.get_doc("FBR Digital Invoicing Settings")
        items = []
        for item in self.items:
            further_tax = 0
            uom = self.get_and_set_uom(item.custom_hs_code)
            tax_amount = round(item.amount * (self.taxes[0].rate /100), 2)
            try:
                tax_rate = self.taxes[1].rate
                if tax_rate and tax_rate > 0:
                    further_tax = round(item.amount * (tax_rate / 100), 2)
            except IndexError:
                further_tax = 0  

            item_data = {
                "hsCode": item.custom_hs_code,  # Default HS Code if not set
                "productDescription": f"{item.item_code}-{item.idx}" if settings.get("make_items_unique") == 1 else item.item_code,
                "rate":"Exempt" if self.fbr_sale_type.tax_exempted else f"{cint(self.taxes[0].rate)}%",
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
        
        api = FBRDigitalInvoicingAPI() 
        response = api.make_request("GET", f"/pdi/v2/HS_UOM?hs_code={hs_code}&annexure_id=3")
        if response:
            #res = response.json()
            uom = response[0].get("description")
            hs_code_doc.hs_code = hs_code
            hs_code_doc.uom = uom
            hs_code_doc.save()
            return uom
    @property
    def fbr_sale_type(self):
        custom_fbr_sale_type = self.custom_fbr_sale_type
        if custom_fbr_sale_type:
            sale_type = frappe.get_doc("FBR Sale Type", custom_fbr_sale_type)
            return sale_type
        else:
            frappe.throw("Please select a valid Fbr Sale Type")
        
            
        