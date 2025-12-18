frappe.ui.form.on('Sales Invoice Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        row.base_price_list_rate = row.price_list_rate;
    },

    price_list_rate: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row._rate_set_by_uom) {
            row.base_price_list_rate = row.price_list_rate;
        }

        row._rate_set_by_uom = false;
    },

    uom: function(frm, cdt, cdn) {
        update_uom(frm, cdt, cdn);
    }
});

function update_uom(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (!row.item_code || !row.uom) return;

    frappe.call({
        method: "kiwi_food_stuff.events.sales_invoice.get_conversion_factor",
        args: {
            item_code: row.item_code,
            uom: row.uom
        },
        callback: function(r) {
            if (r.message) {
                row.conversion_factor = r.message;

                if (row.base_price_list_rate) {
                    row._rate_set_by_uom = true;

                    row.price_list_rate =
                        row.base_price_list_rate * row.conversion_factor;

                    frm.refresh_field("items");
                }
            }
        }
    });
}
