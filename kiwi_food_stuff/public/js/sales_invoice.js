
(function() {
    if (typeof frappe !== 'undefined' && frappe.model && frappe.model.set_value) {
        const _orig_set_value = frappe.model.set_value;
        frappe.model.set_value = function(cdt, cdn, field, value) {
            try {
                const row = (typeof locals !== 'undefined' && locals[cdt] && locals[cdn]) ? locals[cdt][cdn] : (locals[cdt] ? locals[cdt][cdn] : null);
                if (field === 'price_list_rate') {
   
                    if (row && row._suppress_price_update) {
                        return; 
                    }
                }
            } catch (e) {}
            return _orig_set_value.apply(this, arguments);
        };
    }
})();

frappe.ui.form.on('Sales Invoice Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        setTimeout(() => {
            row.stock_uom_rate = row.price_list_rate;
        }, 300);
    },
    
    price_list_rate: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.conversion_factor && row.conversion_factor != 1) {
            row.stock_uom_rate = row.price_list_rate / row.conversion_factor;
        } else {
            row.stock_uom_rate = row.price_list_rate;
        }
    },

    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        row._suppress_price_update = true;
        setTimeout(() => {
            try {
                delete row._suppress_price_update;
            } catch (e) {}
        }, 600);
    },

    uom: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        frappe.call({
            method: "kiwi_food_stuff.events.sales_invoice.get_conversion_factor",
            args: {
                item_code: row.item_code,
                uom: row.uom
            },
            callback: function(r) {
                if (r.message) {
                    let new_conversion = r.message;
                    
                    frappe.model.set_value(cdt, cdn, 'conversion_factor', new_conversion);
                    
                    if (row.stock_uom_rate) {
                        let new_rate = row.stock_uom_rate * new_conversion;
                        
                        setTimeout(() => {
                            frappe.model.set_value(cdt, cdn, 'price_list_rate', new_rate);
                        }, 200);
                    }
                }
            }
        });
    }
});
