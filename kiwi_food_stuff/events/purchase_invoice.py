import frappe
from frappe.utils import cstr, flt


@frappe.whitelist()
def get_last_purchase_invoice_rate(
    supplier, item_code, current_invoice=None, company=None, uom=None
):
    """Return the last rate purchased from this supplier for the given item.
    Prefers the same UOM and falls back to any UOM."""
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

    if current_invoice and not cstr(current_invoice).startswith("new-"):
        conditions.append("pi.name != %(current_invoice)s")
        params["current_invoice"] = current_invoice

    result = None
    if uom:
        result = _get_last_purchase_row([*conditions, "pii.uom = %(uom)s"], {**params, "uom": uom})

    if not result:
        result = _get_last_purchase_row(conditions, params)

    if not result:
        return None

    row = result[0]
    return {
        "last_rate": flt(row.rate),
        "from_purchase_invoice": row.purchase_invoice,
        "posting_date": str(row.posting_date),
        "uom": row.uom,
    }


@frappe.whitelist()
def get_last_purchase_invoice_rates(supplier, items, current_invoice=None, company=None):
    """Batch version of get_last_purchase_invoice_rate for [{name, item_code, uom}] rows,
    so the form needs one request instead of one per row. Returns {row name: result}."""
    items = frappe.parse_json(items) or []

    return {
        d.get("name"): get_last_purchase_invoice_rate(
            supplier, d.get("item_code"), current_invoice, company, d.get("uom")
        )
        for d in items
        if d.get("name") and d.get("item_code")
    }


def _get_last_purchase_row(conditions, params):
    return frappe.db.sql(
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
            {" AND ".join(conditions)}
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
