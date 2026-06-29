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
            fieldname: "party",
            label: __("Common Party"),
            fieldtype: "Link",
            options: "Customer",
            reqd: 0,
            get_query: function() {
                return {
                    query: "kiwi_food_stuff.kiwi_food_stuff.report.common_party_ledger.common_party_ledger.get_common_parties"
                };
            },
            on_change: function() {
                frappe.query_report.refresh();
            }
        }
    ]
};