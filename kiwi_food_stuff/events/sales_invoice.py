import frappe
from frappe import _


SETTINGS_DOCTYPE = "Kiwi Food Stuff Settings"
STANDARD_SELLING_PRICE_LIST = "Standard Selling"
PRICE_VALIDATION_BYPASS_ROLE = "Super Admin"


def to_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0

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
    if is_price_list_rate_validation_bypassed():
        return

    messages = []

    for item in doc.items:
        messages.extend(
            get_price_list_rate_validation_messages(
                item_code=item.item_code,
                price_list_rate=item.price_list_rate,
                warehouse=item.warehouse,
                row_idx=item.idx,
            )
        )

    if messages:
        frappe.throw("<br>".join(messages), title=_("Invalid Price List Rate"))


def get_price_list_rate_validation_messages(item_code=None, price_list_rate=None, warehouse=None, row_idx=None):
    if not item_code or price_list_rate in (None, ""):
        return []

    messages = []
    item_rate = to_float(price_list_rate)
    row_label = _("Row {0}: ").format(row_idx) if row_idx else ""

    standard_selling_rate = get_standard_selling_rate(item_code)
    if standard_selling_rate is not None and item_rate < to_float(standard_selling_rate):
        messages.append(
            _(
                "{0}Price List Rate {1} cannot be less than Standard Selling rate {2} for item {3}."
            ).format(row_label, item_rate, to_float(standard_selling_rate), frappe.bold(item_code))
        )

    valuation_rate = get_bin_valuation_rate(item_code, warehouse)
    if valuation_rate is not None and item_rate < to_float(valuation_rate):
        messages.append(
            _(
                "{0}Price List Rate {1} cannot be less than valuation rate {2} for item {3} in warehouse {4}."
            ).format(row_label, item_rate, to_float(valuation_rate), frappe.bold(item_code), frappe.bold(warehouse))
        )

    return messages


def get_standard_selling_rate(item_code):
    item_prices = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": STANDARD_SELLING_PRICE_LIST,
        },
        fields=["price_list_rate"],
        order_by="valid_from desc, modified desc",
        limit=1,
    )

    if not item_prices:
        return None

    return item_prices[0].price_list_rate


def get_bin_valuation_rate(item_code, warehouse):
    if not warehouse:
        return None

    return frappe.db.get_value(
        "Bin",
        {
            "item_code": item_code,
            "warehouse": warehouse,
        },
        "valuation_rate",
    )


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