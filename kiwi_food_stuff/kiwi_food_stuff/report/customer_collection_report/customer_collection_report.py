# Copyright (c) 2026, Emeron and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Sales Invoice",
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 160
        },
        {
            "label": "Payment Entry",
            "fieldname": "payment_entry",
            "fieldtype": "Link",
            "options": "Payment Entry",
            "width": 160
        },
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 300
        },
        {
            "label": "Sales Person",
            "fieldname": "sales_person",
            "fieldtype": "Link",
            "options": "Sales Person",
            "width": 160
        },
        {
            "label": "Net Total",
            "fieldname": "net_total",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Grand Total",
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Paid Amount",
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Balance Amount",
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "label": "Mode of Payment",
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "width": 140
        }
    ]



def get_data(filters):
    conditions = ""
    values = filters.copy()

    if filters.get("from_date"):
        conditions += " AND si.posting_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND si.posting_date <= %(to_date)s"
    if filters.get("customer"):
        conditions += " AND si.customer = %(customer)s"
    if filters.get("company"):
        conditions += " AND si.company = %(company)s"
    if filters.get("sales_invoice"):
        conditions += " AND si.name = %(sales_invoice)s"
    if filters.get("sales_person"):
        conditions += """
            AND EXISTS (
                SELECT 1 FROM `tabSales Team` st
                WHERE st.parent = si.name
                AND st.parenttype = 'Sales Invoice'
                AND st.sales_person = %(sales_person)s
            )
        """


    invoices = frappe.db.sql(
        f"""
        SELECT
			si.name,
			si.posting_date,
			si.customer,
			si.net_total,
			si.grand_total,
			si.paid_amount,
			si.outstanding_amount,
            (
            SELECT st.sales_person
            FROM `tabSales Team` st
            WHERE st.parent = si.name
              AND st.parenttype = 'Sales Invoice'
            ORDER BY st.idx
            LIMIT 1
        ) AS sales_person
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1 {conditions}
        ORDER BY si.posting_date DESC
        """,
        values,
        as_dict=True
    )

    data = []

    for si in invoices:
        data.append({
			"sales_invoice": si.name,
			"posting_date": si.posting_date,
			"customer": si.customer,
            "sales_person": si.sales_person,
			"net_total": si.net_total,
			"grand_total": si.grand_total,
			"paid_amount": si.paid_amount,
			"outstanding_amount": si.outstanding_amount,
			"indent": 0
		})


        payments = frappe.db.sql(
            """
            SELECT
                pe.name,
                pe.posting_date,
                pe.mode_of_payment,
                per.allocated_amount
            FROM `tabPayment Entry Reference` per
            INNER JOIN `tabPayment Entry` pe
                ON pe.name = per.parent
                AND pe.docstatus = 1
            WHERE
                per.reference_doctype = 'Sales Invoice'
                AND per.reference_name = %s
            ORDER BY pe.posting_date
            """,
            si.name,
            as_dict=True
        )

        for pe in payments:
            data.append({
                "sales_invoice": "",  
                "payment_entry": pe.name,
                "posting_date": pe.posting_date,
                "paid_amount": pe.allocated_amount,
                "mode_of_payment": pe.mode_of_payment,
                "indent": 1
            })

    return data



