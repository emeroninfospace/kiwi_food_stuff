(function() {
    'use strict';
    
    const TIMEOUTS = {
        ITEM_CODE_UPDATE: 300,
        USER_EDIT_EXPIRY: 10000,
        QTY_SUPPRESS: 600,
        UOM_UPDATE: 200
    };
    
    // Helper functions
    const getRow = (cdt, cdn) => {
        return (typeof locals !== 'undefined' && locals[cdt] && locals[cdn]) ? locals[cdt][cdn] : null;
    };
    
    const isUserEditingField = (cdn, fieldname) => {
        const active = document?.activeElement;
        if (!active?.closest) return false;
        return active.closest(`[data-name="${cdn}"]`) && 
               active.closest(`[data-fieldname="${fieldname}"]`);
    };
    
    const calculateStockUomRate = (priceListRate, conversionFactor) => {
        return conversionFactor && conversionFactor !== 1 
            ? priceListRate / conversionFactor 
            : priceListRate;
    };
    
    const clearFlagAfterDelay = (row, flag, delay) => {
        setTimeout(() => {
            if (row && row[flag]) delete row[flag];
        }, delay);
    };
    
    // Override frappe.model.set_value
    if (typeof frappe !== 'undefined' && frappe.model?.set_value) {
        const _orig_set_value = frappe.model.set_value;
        frappe.model.set_value = function(cdt, cdn, field, value) {
            if (field === 'price_list_rate') {
                const row = getRow(cdt, cdn);
                if (row) {
                    if (row._suppress_price_update) return;
                    
                    if (row._user_edited_price) {
                        const timeSinceEdit = Date.now() - row._user_edited_price;
                        if (timeSinceEdit < TIMEOUTS.USER_EDIT_EXPIRY) return;
                        delete row._user_edited_price;
                    }
                }
            }
            return _orig_set_value.apply(this, arguments);
        };
    }
    
    // Form event handlers
    frappe.ui.form.on('Sales Invoice Item', {
        item_code: function(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            setTimeout(() => {
                if (!row._user_edited_stock_rate && row.price_list_rate) {
                    row.stock_uom_rate = row.price_list_rate;
                }
            }, TIMEOUTS.ITEM_CODE_UPDATE);
        },
        
        price_list_rate: function(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            
            // Mark as user-edited if currently focused on this field
            if (isUserEditingField(cdn, 'price_list_rate')) {
                row._user_edited_price = Date.now();
            }
            
            // Auto-update stock_uom_rate if not manually edited
            if (!row._user_edited_stock_rate) {
                row.stock_uom_rate = calculateStockUomRate(row.price_list_rate, row.conversion_factor);
            }
        },
        
        stock_uom_rate: function(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            row._user_edited_stock_rate = Date.now();
            clearFlagAfterDelay(row, '_user_edited_stock_rate', TIMEOUTS.USER_EDIT_EXPIRY);
        },
        
        qty: function(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            row._suppress_price_update = true;
            clearFlagAfterDelay(row, '_suppress_price_update', TIMEOUTS.QTY_SUPPRESS);
        },
        
        uom: function(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            
            frappe.call({
                method: "kiwi_food_stuff.events.sales_invoice.get_conversion_factor",
                args: {
                    item_code: row.item_code,
                    uom: row.uom
                },
                callback: function(r) {
                    if (!r.message) return;
                    
                    const newConversion = r.message;
                    frappe.model.set_value(cdt, cdn, 'conversion_factor', newConversion);
                    
                    if (row.stock_uom_rate) {
                        const newRate = row.stock_uom_rate * newConversion;
                        setTimeout(() => {
                            frappe.model.set_value(cdt, cdn, 'price_list_rate', newRate);
                        }, TIMEOUTS.UOM_UPDATE);
                    }
                }
            });
        }
    });
})();