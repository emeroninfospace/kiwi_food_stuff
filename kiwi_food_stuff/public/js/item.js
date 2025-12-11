frappe.ui.form.on("UOM Conversion Detail", {
    custom_qty: function(frm, cdt, cdn) {
        calculate_conversion_factor(frm, cdt, cdn);
    },
    custom_unit_qty: function(frm, cdt, cdn) {
        calculate_conversion_factor(frm, cdt, cdn);
    }
});

// Function to calculate conversion_factor from custom_qty and custom_unit_qty
function calculate_conversion_factor(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    if (!row) return;
    
    // Get values from the row
    let custom_qty = flt(row.custom_qty) || 0;
    let custom_unit_qty = flt(row.custom_unit_qty) || 0;
    
    // Calculate conversion_factor = custom_unit_qty / custom_qty
    let conversion_factor = 0;
    if (custom_qty && custom_qty !== 0) {
        conversion_factor = custom_unit_qty / custom_qty;
    }
    
    // Set the conversion_factor in the same row
    frappe.model.set_value(cdt, cdn, 'conversion_factor', conversion_factor);
}

