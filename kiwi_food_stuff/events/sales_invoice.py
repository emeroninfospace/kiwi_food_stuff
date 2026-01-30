import frappe

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