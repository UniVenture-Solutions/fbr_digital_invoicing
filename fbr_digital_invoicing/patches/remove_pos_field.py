import frappe

def execute():
    docs = frappe.get_all("Custom Field", filters={"dt": "Sales Invoice Item", "fieldname": "pos_invoice"})

    if len(docs) > 0:
        for doc in docs:
            frappe.delete_doc("Custom Field", doc.name)
            frappe.db.commit()


