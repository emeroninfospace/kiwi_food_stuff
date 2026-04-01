frappe.ui.form.on('Payment Entry', {
    onload: function (frm) {
        frm.set_query("reference_name", "references", function (doc, cdt, cdn) {
                    const child = locals[cdt][cdn];
                    const party_type_doctypes = [
                        "Sales Invoice",
                        "Sales Order",
                        "Purchase Invoice",
                        "Purchase Order",
                        "Dunning",
                    ];
                    
                    // Doctypes that have a 'status' field
                    const doctypes_with_status = [
                        "Sales Invoice",
                        "Sales Order",
                        "Purchase Invoice",
                        "Purchase Order",
                    ];
                    
                    const filters = { docstatus: 1, company: doc.company };
                    
                    // Only add status filter for doctypes that have it
                    if (in_list(doctypes_with_status, child.reference_doctype)) {
                        filters.status = ["!=", "Paid"];
                    }

                    if (in_list(party_type_doctypes, child.reference_doctype)) {
                        filters[doc.party_type.toLowerCase()] = doc.party;
                    }

                    return {
                        filters: filters,
                    };
                });
    }
});