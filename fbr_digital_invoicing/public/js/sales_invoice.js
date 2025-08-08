frappe.ui.form.on('Sales Invoice', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 1 && !frm.doc.custom_fbr_invoice_no) {
            frm.add_custom_button(__('Sync to FDI'), function () {
                frappe.call({
                    method: 'fbr_digital_invoicing.document_controllers.sales_invoice.sync_to_fdi',
                    args: {
                        docname: frm.doc.name
                    },
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint(__('Synced successfully with FDI.'));
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});
