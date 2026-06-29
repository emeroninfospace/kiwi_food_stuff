// Copyright (c) 2026, Emeron and contributors
// For license information, please see license.txt

frappe.query_reports["Common Party Ledger"] = {
    onload: function(report) {
        // Force set company on load
        frappe.db.get_value("Company", {}, "name", function(r) {
            if (r && r.name) {
                frappe.query_report.set_filter_value("company", r.name);
                frappe.query_report.refresh();
            }
        });
    },

    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "party_type",
            label: __("Party Type"),
            fieldtype: "Select",
            options: "\nCustomer\nSupplier",
            reqd: 0,
            on_change: function() {
                frappe.query_report.set_filter_value("party", "");
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "party",
            label: __("Party"),
            fieldtype: "Link",
            options: "Customer",
            reqd: 0,
            get_query: function() {
                var party_type = frappe.query_report.get_filter_value("party_type");
                if (!party_type) {
                    frappe.msgprint(__("Please select Party Type first"));
                    return;
                }
                return {
                    doctype: party_type,
                    query: "kiwi_food_stuff.kiwi_food_stuff.report.common_party_ledger.common_party_ledger.get_common_parties",
                    filters: {
                        party_type: party_type
                    }
                };
            },
            on_change: function() {
                frappe.query_report.refresh();
            }
        }
    ]
};