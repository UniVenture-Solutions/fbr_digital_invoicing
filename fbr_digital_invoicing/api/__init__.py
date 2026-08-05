import frappe
import requests
from frappe.exceptions import ValidationError



class FBRDigitalInvoicingAPI:
    def __init__(self, company):
        self.company = company
        settings = frappe.get_doc("FBR Digital Invoicing Settings")
        self.base_url = settings.get("url")
        self.token = frappe.get_doc("Company", self.company).get_password("custom_fbr_digital_invoicing_token")
        

    def init_request(self):
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)


    def make_request(self, method, endpoint, data=None):
        self.init_request()
        api_log = frappe.new_doc("FDI Request Log")
        request_payload = {
            "method": method,
            "endpoint": endpoint,
            "data": data,
        }
        api_log.request_data = frappe.as_json(request_payload, indent=4)

        saved = False
        try:
            if not self.base_url:
                api_log.error = "Missing FBR Digital Invoicing Settings URL"
                api_log.save(ignore_permissions=True)
                frappe.db.commit()
                saved = True
                frappe.throw("FBR Digital Invoicing Settings URL is missing")

            if not self.token:
                api_log.error = "Missing FBR Digital Invoicing token on Company"
                api_log.save(ignore_permissions=True)
                frappe.db.commit()
                saved = True
                frappe.throw("FBR Digital Invoicing token is missing on Company")

            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            request = self.session.request(method, url, json=data, timeout=30)

            try:
                response_json = request.json()
            except Exception:
                response_json = None

            if response_json is None and request.text:
                try:
                    response_json = frappe.parse_json(request.text)
                except Exception:
                    response_json = None

            if response_json is not None:
                api_log.response_data = frappe.as_json(response_json, indent=4)
            else:
                api_log.response_data = request.text

            if request.status_code != 200:
                api_log.error = f"HTTP {request.status_code}"
                api_log.save(ignore_permissions=True)
                frappe.db.commit()
                saved = True

                frappe.log_error(
                    title="FBR Invoicing API Error",
                    message=f"Error in FBR API: {request.text}"
                )
                frappe.throw(f"Error in FBR API: {request.text}")

            api_log.save(ignore_permissions=True)
            frappe.db.commit()
            saved = True
            return response_json or request.text

        except Exception as e:
            if not api_log.error:
                api_log.error = frappe.get_traceback()

            if not saved:
                api_log.save(ignore_permissions=True)
                frappe.db.commit()

            if not isinstance(e, ValidationError):
                frappe.log_error(
                    title="FBR Invoicing API Error",
                    message=frappe.get_traceback()
                )

            if isinstance(e, ValidationError):
                raise
            frappe.throw(f"Error while making request to FBR API: {str(e)}")
        
    
