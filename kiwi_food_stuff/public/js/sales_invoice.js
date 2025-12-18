frappe.ui.form.on('Sales Invoice Item', {
    price_list_rate: function(frm, cdt, cdn) {
        update_uom(frm, cdt, cdn);
    },

    uom: function(frm, cdt, cdn) {
        update_uom(frm, cdt, cdn);
        
    }
});
function update_uom(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.call({
            method: "kiwi_food_stuff.events.sales_invoice.get_conversion_factor",
            args: {
                item_code: row.item_code,
                uom: row.uom
            },
            callback: function(r) {
                if (r.message) {
                    row.conversion_factor = r.message;
                    if (row.uom && row.conversion_factor && row.price_list_rate) {
                        row.price_list_rate = row.price_list_rate * row.conversion_factor;
                        frm.refresh_field('items');
                    }
                }
            }
        });
    }

    