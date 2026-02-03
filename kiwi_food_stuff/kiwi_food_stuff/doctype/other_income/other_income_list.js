// Copyright (c) 2026, Emeron and contributors
// For license information, please see license.txt

frappe.listview_settings["Other Income"] = {
    add_fields: ["status", "grand_total"],
    get_indicator(doc) {
        if (doc.status === "Paid") {
            return ["Paid", "green", "status,=,Paid"];
        }
        if (doc.status === "Unpaid") {
            return ["Unpaid", "orange", "status,=,Unpaid"];
        }
    }
};
