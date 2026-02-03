// Copyright (c) 2026, Emeron and contributors
// For license information, please see license.txt

frappe.ui.form.on("Other Income", {
    refresh(frm) {
        frm.set_query("income_account", "items", () => ({
            filters: {
                is_group: 0,
                company: frm.doc.company,
                account_type: ["in", ["Direct Income", "Indirect Income"]]
            }
        }));

        frm.set_query("received_to", "items", () => ({
            filters: {
                is_group: 0,
                company: frm.doc.company
            }
        }));

        if (frm.doc.docstatus === 1 && !frm.doc.journal_entry) {
            frm.add_custom_button(__("Make Receipt"), function () {
                frappe.confirm(
                    __("Create and submit Journal Entry for this income?"),
                    function () {
                        frm.call("make_journal_entry").then(r => {
                            if (r.message) {
                                frappe.msgprint(__("Journal Entry {0} created", [r.message]));
                                frm.reload_doc();
                            }
                        });
                    }
                );
            });
        }
    }
});

frappe.ui.form.on("Other Income Item", {
    amount: calculate_row,
    vat_percentage: calculate_row,
    items_remove: calculate_totals
});

function calculate_row(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    row.vat_amount = flt(row.amount * row.vat_percentage / 100);
    row.total_amount = flt(row.amount) + flt(row.vat_amount);

    frm.refresh_field("items");
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total = 0, vat = 0;

    (frm.doc.items || []).forEach(d => {
        total += flt(d.amount);
        vat += flt(d.vat_amount);
    });

    frm.set_value("total_amount", total);
    frm.set_value("total_vat", vat);
    frm.set_value("grand_total", total + vat);
}
