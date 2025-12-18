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