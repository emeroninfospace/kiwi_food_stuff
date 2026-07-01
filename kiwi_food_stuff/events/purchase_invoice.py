import frappe
from frappe.utils import cstr, flt


@frappe.whitelist()
def get_last_purchase_invoice_rate(
    supplier, item_code, current_invoice=None, company=None, uom=None
):
    """Return the last rate purchased from this supplier for the given item."""
    if not supplier or not item_code:
        return None

    params = {
        "supplier": supplier,
        "item_code": item_code,
    }

    conditions = [
        "pi.supplier = %(supplier)s",
        "pi.docstatus = 1",
        "IFNULL(pi.is_return, 0) = 0",
        "pii.parenttype = 'Purchase Invoice'",
        "pii.item_code = %(item_code)s",
    ]

    if company:
        conditions.append("pi.company = %(company)s")
        params["company"] = company

    if uom:
        conditions.append("pii.uom = %(uom)s")
        params["uom"] = uom

    if current_invoice and not cstr(current_invoice).startswith("new-"):
        conditions.append("pi.name != %(current_invoice)s")
        params["current_invoice"] = current_invoice

    where_clause = " AND ".join(conditions)

    result = frappe.db.sql(
        f"""
        SELECT
            pii.rate,
            pi.name AS purchase_invoice,
            pi.posting_date,
            pii.uom
        FROM
            `tabPurchase Invoice Item` pii
        INNER JOIN
            `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE
            {where_clause}
        ORDER BY
            pi.posting_date DESC,
            pi.posting_time DESC,
            pi.creation DESC,
            pii.idx DESC
        LIMIT 1
        """,
        params,
        as_dict=True,
    )

    if not result and uom:
        params_without_uom = {k: v for k, v in params.items() if k != "uom"}
        conditions_without_uom = [c for c in conditions if "pii.uom" not in c]
        where_clause = " AND ".join(conditions_without_uom)

        result = frappe.db.sql(
            f"""
            SELECT
                pii.rate,
                pi.name AS purchase_invoice,
                pi.posting_date,
                pii.uom
            FROM
                `tabPurchase Invoice Item` pii
            INNER JOIN
                `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE
                {where_clause}
            ORDER BY
                pi.posting_date DESC,
                pi.posting_time DESC,
                pi.creation DESC,
                pii.idx DESC
            LIMIT 1
            """,
            params_without_uom,
            as_dict=True,
        )

    if not result:
        return None

    row = result[0]
    return {
        "last_rate": flt(row.rate),
        "from_purchase_invoice": row.purchase_invoice,
        "posting_date": str(row.posting_date),
        "uom": row.uom,
    }
