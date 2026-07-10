import frappe
from frappe import _
from frappe.utils import flt, getdate


SETTINGS_DOCTYPE = "Kiwi Food Stuff Settings"
STANDARD_SELLING_PRICE_LIST = "Standard Selling"
PRICE_VALIDATION_BYPASS_ROLE = "Super Admin"


def to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0

@frappe.whitelist()
def get_last_sales_invoice_rate(customer, item_code, current_invoice=None):
    """Return the last price_list_rate sold to this customer for the given item."""
    if not customer or not item_code:
        return None

    exclude_condition = ""
    params = {
        "customer": customer,
        "item_code": item_code,
    }

    if current_invoice:
        exclude_condition = "AND si.name != %(current_invoice)s"
        params["current_invoice"] = current_invoice

    result = frappe.db.sql(
        """
        SELECT
            sii.price_list_rate,
            si.name AS sales_invoice,
            si.posting_date
        FROM
            `tabSales Invoice Item` sii
        INNER JOIN
            `tabSales Invoice` si ON si.name = sii.parent
        WHERE
            si.customer = %(customer)s
            AND si.docstatus = 1
            AND IFNULL(si.is_return, 0) = 0
            AND sii.item_code = %(item_code)s
            {exclude}
        ORDER BY
            si.posting_date DESC,
            si.creation DESC
        LIMIT 1
        """.format(exclude=exclude_condition),
        params,
        as_dict=True,
    )

    if not result:
        return None

    row = result[0]
    return {
        "last_rate": row.price_list_rate,
        "from_sales_invoice": row.sales_invoice,
        "posting_date": str(row.posting_date),
    }


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_uoms(doctype, txt, searchfield, start, page_len, filters):
    item_code = filters.get('item_code') if isinstance(filters, dict) else frappe.parse_json(filters).get('item_code')
    if not item_code:
        return []

    return frappe.db.sql("""
        SELECT uom
        FROM `tabUOM Conversion Detail`
        WHERE parent = %(item_code)s
          AND parenttype = 'Item'
          AND uom LIKE %(txt)s
        ORDER BY uom
        LIMIT %(page_len)s OFFSET %(start)s
    """, {
        'item_code': item_code,
        'txt': f'%{txt}%',
        'page_len': page_len,
        'start': start
    })


@frappe.whitelist()
def get_conversion_factor(item_code, uom):
    conversion_factor = frappe.db.get_value(
        "UOM Conversion Detail",
        {"parent": item_code, "uom": uom},
        "conversion_factor"
    )
    
    if conversion_factor:
        return conversion_factor
    else:
        return 1

# for triggering price list rate
def validate_sales_invoice(doc, method):
    for item in doc.items:
        if item.price_list_rate and item.conversion_factor:
            stock_rate = item.price_list_rate / item.conversion_factor

            # Recalculate correctly
            final_rate = stock_rate * item.conversion_factor

            # FORCE correct value
            item.price_list_rate = final_rate
            item.rate = final_rate


def validate_sales_invoice_price_list_rates(doc, method=None):
    """Runs on Sales Invoice and POS Invoice before_submit."""
    if is_price_list_rate_validation_bypassed():
        return

    messages = collect_sales_invoice_price_list_rate_messages(doc)

    if messages:
        frappe.throw("<br>".join(messages), title=_("Invalid Price List Rate"))


def collect_sales_invoice_price_list_rate_messages(doc):
    transaction_date = doc.get("posting_date") or doc.get("transaction_date")
    messages = []

    for item in doc.items:
        messages.extend(
            get_price_list_rate_validation_messages(
                item_code=item.item_code,
                uom=item.uom,
                price_list_rate=item.price_list_rate,
                warehouse=item.warehouse,
                conversion_factor=item.conversion_factor,
                transaction_date=transaction_date,
                row_idx=item.idx,
            )
        )

    return messages


def get_price_list_rate_validation_messages(
    item_code=None,
    price_list_rate=None,
    uom=None,
    warehouse=None,
    conversion_factor=1,
    transaction_date=None,
    row_idx=None,
):
    if not item_code or price_list_rate in (None, ""):
        return []

    if not uom:
        return []

    messages = []
    item_rate = flt(price_list_rate)
    row_label = _("Row {0}: ").format(row_idx) if row_idx else ""

    standard_selling_rate = get_standard_selling_rate(item_code, uom, transaction_date)
    if standard_selling_rate is not None and item_rate < flt(standard_selling_rate):
        messages.append(
            _(
                "{0}Price List Rate {1} cannot be less than Standard Selling rate {2} "
                "for item {3} (Price List: {4}, UOM: {5})."
            ).format(
                row_label,
                item_rate,
                flt(standard_selling_rate),
                frappe.bold(item_code),
                frappe.bold(STANDARD_SELLING_PRICE_LIST),
                frappe.bold(uom),
            )
        )

    # bin_valuation = get_bin_valuation_rate_in_uom(
    #     item_code, warehouse, uom, conversion_factor
    # )
    # if bin_valuation and item_rate < flt(bin_valuation["rate"]):
    #     messages.append(
    #         _(
    #             "{0}Price List Rate {1} cannot be less than Bin valuation rate {2} "
    #             "({3} per {4}) for item {5} in warehouse {6}."
    #         ).format(
    #             row_label,
    #             item_rate,
    #             flt(bin_valuation["rate"]),
    #             flt(bin_valuation["stock_valuation_rate"]),
    #             frappe.bold(bin_valuation["stock_uom"]),
    #             frappe.bold(item_code),
    #             frappe.bold(warehouse),
    #         )
    #     )

    return messages


def get_standard_selling_rate(item_code, uom, transaction_date=None):
    if not item_code or not uom:
        return None

    transaction_date = getdate(transaction_date or frappe.utils.today())

    item_prices = frappe.db.sql(
        """
        SELECT price_list_rate
        FROM `tabItem Price`
        WHERE item_code = %(item_code)s
          AND price_list = %(price_list)s
          AND uom = %(uom)s
          AND IFNULL(valid_from, '2000-01-01') <= %(transaction_date)s
          AND IFNULL(valid_upto, '2500-12-31') >= %(transaction_date)s
        ORDER BY valid_from DESC, modified DESC
        LIMIT 1
        """,
        {
            "item_code": item_code,
            "price_list": STANDARD_SELLING_PRICE_LIST,
            "uom": uom,
            "transaction_date": transaction_date,
        },
        as_dict=True,
    )

    if not item_prices:
        return None

    return item_prices[0].price_list_rate


def get_bin_valuation_rate_in_uom(item_code, warehouse, uom, conversion_factor=None):
    if not warehouse or not item_code or not uom:
        return None

    bin_details = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["valuation_rate", "stock_uom"],
        as_dict=True,
    )

    if not bin_details:
        return None

    stock_valuation_rate = flt(bin_details.valuation_rate)
    if not stock_valuation_rate:
        return None

    stock_uom = bin_details.stock_uom or frappe.get_cached_value("Item", item_code, "stock_uom")

    if uom == stock_uom:
        return {
            "rate": stock_valuation_rate,
            "stock_valuation_rate": stock_valuation_rate,
            "stock_uom": stock_uom,
        }

    line_conversion_factor = flt(conversion_factor) if conversion_factor else None
    if not line_conversion_factor:
        line_conversion_factor = flt(get_conversion_factor(item_code, uom))

    return {
        "rate": stock_valuation_rate * line_conversion_factor,
        "stock_valuation_rate": stock_valuation_rate,
        "stock_uom": stock_uom,
    }


def is_price_list_rate_validation_bypassed(user=None):
    user = user or frappe.session.user

    if not user or user == "Guest":
        return False

    settings = get_settings()
    if not settings or not to_float(settings.sales_invoice_price_list_permission):
        return False

    return PRICE_VALIDATION_BYPASS_ROLE in frappe.get_roles(user)


def get_settings():
    try:
        return frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except frappe.DoesNotExistError:
        return None


# ADD sales person to sales invoice from POS profile
def add_pos_sales_person(doc, method=None):
    if not doc.is_pos or not doc.pos_profile:
        return

    current_user = frappe.session.user
    if not current_user or current_user == "Administrator":
        return

    try:
        pos_profile = frappe.get_doc("POS Profile", doc.pos_profile)
    except frappe.DoesNotExistError:
        return

    allowed_users = [
        row.user for row in (pos_profile.applicable_for_users or [])
        if row.user
    ]

    if current_user not in allowed_users:
        return

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": current_user},
        "name",
    )

    if not employee:
        return

    sales_person = frappe.db.get_value(
        "Sales Person",
        {"employee": employee},
        "name",
    )

    if not sales_person:
        return

    for row in doc.sales_team or []:
        if row.sales_person == sales_person:
            return

    doc.append("sales_team", {
        "sales_person": sales_person,
        "allocated_percentage": 100,
    })
    doc.db_update()


# Add sales person to the standalone invoice
def set_sales_person(doc, method=None):
    if doc.is_pos:
        return

    if doc.sales_team:
        return

    user = frappe.session.user

    if user in ("Guest", "Administrator"):
        return

    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return

    sales_person = frappe.db.get_value("Sales Person", {"employee": employee}, "name")
    if not sales_person:
        return

    doc.append("sales_team", {
        "sales_person": sales_person,
        "allocated_percentage": 100
    })