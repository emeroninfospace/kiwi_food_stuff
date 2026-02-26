# Copyright (c) 2026, Emeron and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import Order


def execute(filters=None):
    filters = frappe._dict(filters or {})

    # 1️⃣ Date Validation Before Running Query
    if filters.get("from_date") and filters.get("to_date"):
        if filters.get("from_date") > filters.get("to_date"):
            frappe.throw(_("From Date must be before To Date"))

    columns = get_columns()
    data = get_data(filters)

    return columns, data, None


def get_data(filters):
    pe = frappe.qb.DocType("Payment Entry")

    query = (
        frappe.qb.from_(pe)
        .select(
            pe.name,
            pe.posting_date,
            pe.reference_no,
            pe.party_name,
            pe.bank_account,
            pe.paid_amount,
            pe.custom_pdc_status.as_("cheque_status"),
        )
        .where(pe.party_type == "Customer")
        .where(pe.docstatus < 2)
        .where(pe.mode_of_payment == "Cheque")
        .orderby(pe.creation, order=Order.desc)
    )

    # Filters
    if filters.get("from_date"):
        query = query.where(pe.posting_date >= filters.get("from_date"))

    if filters.get("to_date"):
        query = query.where(pe.posting_date <= filters.get("to_date"))

    if filters.get("company"):
        query = query.where(pe.company == filters.get("company"))

    if filters.get("customer"):
        query = query.where(pe.party == filters.get("customer"))

    # 3️⃣ Status Filter Applied Directly in Query
    if filters.get("status"):
        query = query.where(pe.custom_pdc_status == filters.get("status"))

    return query.run(as_dict=1)


def get_columns():
    return [
        {
            "label": _("Payment Entry ID"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Payment Entry",
            "width": "150px",
        },
        {
            "label": _("Party Name"),
            "fieldname": "party_name",
            "fieldtype": "Data",
            "width": "150px",
        },
        {
            "label": _("Posting/Cheque Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": "150px",
        },
        {
            "label": _("Cheque/DD No"),
            "fieldname": "reference_no",
            "fieldtype": "Data",
            "width": "150px",
        },
        {
            "label": _("Cheque Status"),
            "fieldname": "cheque_status",
            "fieldtype": "Data",
            "width": "150px",
        },
        {
            "label": _("Bank"),
            "fieldname": "bank_account",
            "fieldtype": "Data",
            "width": "150px",
        },
        {
            "label": _("Amount"),
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "width": "100px",
        },
    ]


@frappe.whitelist()
def update_multiple_status(payment_entries, status):
    """Update the cheque status for multiple Payment Entries"""

    # 4️⃣ Role-Based Security Validation
    allowed_roles = ["Accounts Manager", "Accounts User"]
    user_roles = frappe.get_roles(frappe.session.user)

    if not any(role in user_roles for role in allowed_roles):
        frappe.throw(
            _("You are not permitted to update cheque status."),
            frappe.PermissionError,
        )

    try:
        import json

        if isinstance(payment_entries, str):
            payment_entries = json.loads(payment_entries)

        if not payment_entries:
            frappe.throw(_("No Payment Entries provided."))

        for payment_entry in payment_entries:
            frappe.db.set_value(
                "Payment Entry",
                payment_entry,
                "custom_pdc_status",
                status,
                update_modified=True,
            )

        frappe.db.commit()

        return {"success": True, "message": _("Status updated successfully")}

    except Exception:
        frappe.log_error(frappe.get_traceback(), _("PDC Status Update Error"))
        return {"success": False, "message": _("Failed to update status")}
