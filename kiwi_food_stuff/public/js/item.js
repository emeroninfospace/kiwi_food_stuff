frappe.ui.form.on("UOM Conversion Detail", {
    custom_qty: function(frm, cdt, cdn) {
        calculate_conversion_factor(frm, cdt, cdn);
    },
    custom_unit_qty: function(frm, cdt, cdn) {
        calculate_conversion_factor(frm, cdt, cdn);
    },
    uom: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if ( frm.doc.stock_uom) {
            frappe.model.set_value(cdt, cdn, 'custom_unit', frm.doc.stock_uom);
        } 
    }
});
function calculate_conversion_factor(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let conversion_factor = 0;
    if (row.custom_unit_qty && row.custom_qty) {
        conversion_factor = row.custom_unit_qty / row.custom_qty;
    }
    
    frappe.model.set_value(cdt, cdn, 'conversion_factor', conversion_factor);
}

