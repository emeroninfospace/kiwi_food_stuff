frappe.ui.form.on('Payment Entry', {
    onload: function (frm) {
        frm.set_query("reference_name", "references", function (doc, cdt, cdn) {
                    const child = locals[cdt][cdn];
                    const filters = { docstatus: 1, company: doc.company,status: ["!=", "Paid"]};
                    const party_type_doctypes = [
                        "Sales Invoice",
                        "Sales Order",
                        "Purchase Invoice",
                        "Purchase Order",
                        "Dunning",
                    ];

                    if (in_list(party_type_doctypes, child.reference_doctype)) {
                        filters[doc.party_type.toLowerCase()] = doc.party;
                    }

                    return {
                        filters: filters,
                    };
                });
    }
    });