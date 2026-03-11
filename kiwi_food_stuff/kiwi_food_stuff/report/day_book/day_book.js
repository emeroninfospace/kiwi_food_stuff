frappe.query_reports["Day Book"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -30),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "voucher_type",
            "label": __("Voucher Type"),
            "fieldtype": "Select",
            "options": ["", "Sales Invoice", "Purchase Invoice", "Journal Entry", "Payment Entry"],
            "default": ""
        },
        {
            "fieldname": "voucher_no",
            "label": __("Voucher No"),
            "fieldtype": "Data"
        },
        {
            fieldname: "party_type",
            label: __("Party Type"),
            fieldtype: "Select",
            options: ["", "Customer", "Supplier"],
            default: "",
            on_change: function() {
                const party_type = this.get_value();  

                frappe.query_report.set_filter_value({
                    customer: "",
                    supplier: ""
                });
            }
        },

        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer",
            depends_on: "eval:doc.party_type == 'Customer'"
        },

        {
            fieldname: "supplier",
            label: __("Supplier"),
            fieldtype: "Link",
            options: "Supplier",
            depends_on: "eval:doc.party_type == 'Supplier'"
        },
        {
            "fieldname": "sales_person",
            "label": __("Sales Person"),
            "fieldtype": "Link",
            "options": "Sales Person"
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "debit_qty" && value && data.debit_qty > 0) {
            return `<span style="color: green; font-weight: bold;">${value}</span>`;
        }
        if (column.fieldname === "credit_qty" && value && data.credit_qty > 0) {
            return `<span style="color: #c0392b; font-weight: bold;">${value}</span>`;
        }

        return value;
    },

    "get_query": function(report) {
    }
};