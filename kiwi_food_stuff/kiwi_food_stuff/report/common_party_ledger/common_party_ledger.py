# Copyright (c) 2026, Emeron and contributors
# For license information, please see license.txt

import frappe

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
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "Voucher Type",
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "width": 130
        },
        {
            "label": "Voucher No",
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 180
        },
        {
            "label": "Account",
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 200
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
            "label": "Against",
            "fieldname": "against",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "Party Type",
            "fieldname": "party_type",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Party",
            "fieldname": "party",
            "fieldtype": "Data",
            "width": 160
        },
    ]


def get_data(filters):
    conditions = get_conditions(filters)

    data = frappe.db.sql("""
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
            AND gle.party IS NOT NULL
            AND gle.party != ''
            {conditions}
        ORDER BY
            gle.posting_date ASC, gle.voucher_no ASC
    """.format(conditions=conditions), filters, as_dict=1)

    return data


def get_conditions(filters):
    conditions = ""

    if filters.get("company"):
        conditions += " AND gle.company = %(company)s"

    if filters.get("from_date"):
        conditions += " AND gle.posting_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND gle.posting_date <= %(to_date)s"

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