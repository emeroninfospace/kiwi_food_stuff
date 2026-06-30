# Copyright (c) 2026, Emeron and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}

    # Always force company if not set
    if not filters.get("company"):
        filters["company"] = frappe.db.get_value("Company", {}, "name")

    columns = get_columns()
    data = get_data(filters)
    return columns, data


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_common_parties(doctype, txt, searchfield, start, page_len, filters):
    txt_like = "%%%s%%" % (txt or "")

    common_parties = frappe.db.sql("""
        SELECT name, party_name FROM (
            SELECT
                pl.primary_party as name,
                CONCAT(pl.primary_party, ' (', pl.primary_role, ')') as party_name
            FROM `tabParty Link` pl
            WHERE (%(txt)s = '' OR pl.primary_party LIKE %(txt_like)s)

            UNION

            SELECT
                pl.secondary_party as name,
                CONCAT(pl.secondary_party, ' (', pl.secondary_role, ')') as party_name
            FROM `tabParty Link` pl
            WHERE (%(txt)s = '' OR pl.secondary_party LIKE %(txt_like)s)
        ) parties
        GROUP BY name
        ORDER BY name
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        "txt": txt or "",
        "txt_like": txt_like,
        "page_len": page_len,
        "start": start
    })

    return common_parties


def get_columns():
    return [
        {
            "label": "Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 130
        },
        {
            "label": "Particulars",
            "fieldname": "particulars",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Vch Type",
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Vch No.",
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 250
        },
        {
            "label": "Debit",
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Credit",
            "fieldname": "credit",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Balance",
            "fieldname": "balance_display",
            "fieldtype": "Data",
            "width": 160
        },
    ]


def get_data(filters):
    if not filters.get("party"):
        return []

    party = filters.get("party")

    # ---- 1. Opening balance: sum of all entries before from_date ----
    opening_filters = dict(filters)
    opening_filters.pop("from_date", None)
    opening_conditions = get_conditions(opening_filters)

    if filters.get("from_date"):
        opening_conditions += " AND gle.posting_date < %(from_date)s"

    opening_row = frappe.db.sql("""
        SELECT
            SUM(gle.debit) as total_debit,
            SUM(gle.credit) as total_credit
        FROM `tabGL Entry` gle
        WHERE
            gle.docstatus = 1
            AND gle.is_cancelled = 0
            AND gle.party IS NOT NULL
            AND gle.party != ''
            {conditions}
    """.format(conditions=opening_conditions), filters, as_dict=1)

    opening_balance = flt(opening_row[0].total_debit) - flt(opening_row[0].total_credit) if opening_row else 0.0

    # ---- 2. Period entries ----
    conditions = get_conditions(filters)

    entries = frappe.db.sql("""
        SELECT
            gle.posting_date,
            gle.voucher_type,
            gle.voucher_no,
            gle.account,
            gle.debit,
            gle.credit,
            gle.against,
            gle.party_type,
            gle.party
        FROM
            `tabGL Entry` gle
        WHERE
            gle.docstatus = 1
            AND gle.is_cancelled = 0
            AND gle.party IS NOT NULL
            AND gle.party != ''
            {conditions}
        ORDER BY
            gle.posting_date ASC, gle.voucher_no ASC
    """.format(conditions=conditions), filters, as_dict=1)

    # ---- 3. Build ledger rows with running balance ----
    data = []
    running_balance = opening_balance
    total_debit = 0.0
    total_credit = 0.0

    # Opening Balance row
    data.append({
        "posting_date": filters.get("from_date"),
        "particulars": "Opening Balance",
        "voucher_type": "",
        "voucher_no": "",
        "debit": None,
        "credit": None,
        "balance_display": format_balance(running_balance),
        "balance_raw": running_balance,
        "is_group_row": 1
    })

    for entry in entries:
        debit = flt(entry.debit)
        credit = flt(entry.credit)
        running_balance += debit - credit
        total_debit += debit
        total_credit += credit

        # "Particulars" = the other side of the entry (the contra account),
        # shown with Dr/Cr prefix like in a manual ledger
        if debit > 0:
            particulars = "Dr {0}".format(entry.account)
        else:
            particulars = "Cr {0}".format(entry.account)

        data.append({
            "posting_date": entry.posting_date,
            "particulars": particulars,
            "voucher_type": entry.voucher_type,
            "voucher_no": entry.voucher_no,
            "debit": debit or None,
            "credit": credit or None,
            "balance_display": format_balance(running_balance),
            "balance_raw": running_balance
        })

    # Totals row
    data.append({
        "posting_date": None,
        "particulars": "",
        "voucher_type": "",
        "voucher_no": "",
        "debit": total_debit,
        "credit": total_credit,
        "balance_display": "",
        "is_group_row": 1,
        "bold": 1
    })

    # Closing Balance row
    data.append({
        "posting_date": None,
        "particulars": "Closing Balance",
        "voucher_type": "",
        "voucher_no": "",
        "debit": None,
        "credit": None,
        "balance_display": format_balance(running_balance),
        "balance_raw": running_balance,
        "is_group_row": 1,
        "bold": 1
    })

    # Grand total row — matches the PDF's bottom double-total line
    # (period totals plus the opening/closing balance brought down)
    data.append({
        "posting_date": None,
        "particulars": "",
        "voucher_type": "",
        "voucher_no": "",
        "debit": total_debit + (opening_balance if opening_balance > 0 else 0),
        "credit": total_credit + (running_balance if running_balance > 0 else 0),
        "balance_display": "",
        "is_group_row": 1,
        "bold": 1
    })

    return data


def format_balance(balance):
    if balance is None:
        return ""
    if balance >= 0:
        return "{0} Dr".format(frappe.utils.fmt_money(abs(balance)))
    else:
        return "{0} Cr".format(frappe.utils.fmt_money(abs(balance)))


def get_conditions(filters):
    conditions = ""

    if filters.get("company"):
        conditions += " AND gle.company = %(company)s"

    if filters.get("from_date"):
        conditions += " AND gle.posting_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND gle.posting_date <= %(to_date)s"

    # Only show Sales/Purchase related vouchers, exclude Payment Entry & Journal Entry
    conditions += """ AND gle.voucher_type IN (
        'Sales Invoice', 'Sales', 'Purchase Invoice', 'Purchase', 'Debit Note', 'Credit Note'
    )"""

    if filters.get("party"):
        conditions += """ AND (
            gle.party = %(party)s
            OR EXISTS (
                SELECT 1 FROM `tabParty Link` pl
                WHERE pl.primary_party = %(party)s
                AND pl.secondary_party = gle.party
            )
            OR EXISTS (
                SELECT 1 FROM `tabParty Link` pl
                WHERE pl.secondary_party = %(party)s
                AND pl.primary_party = gle.party
            )
        )"""

    return conditions