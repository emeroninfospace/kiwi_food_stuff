// (function() {
//     'use strict';
    
//     const TIMEOUTS = {
//         ITEM_CODE_UPDATE: 300,
//         USER_EDIT_EXPIRY: 10000,
//         QTY_SUPPRESS: 600,
//         UOM_UPDATE: 200
//     };
    
//     // Helper functions
//     const getRow = (cdt, cdn) => {
//         return (typeof locals !== 'undefined' && locals[cdt] && locals[cdn]) ? locals[cdt][cdn] : null;
//     };
    
//     const isUserEditingField = (cdn, fieldname) => {
//         const active = document?.activeElement;
//         if (!active?.closest) return false;
//         return active.closest(`[data-name="${cdn}"]`) && 
//                active.closest(`[data-fieldname="${fieldname}"]`);
//     };
    
//     const calculateStockUomRate = (priceListRate, conversionFactor) => {
//         return conversionFactor && conversionFactor !== 1 
//             ? priceListRate / conversionFactor 
//             : priceListRate;
//     };
    
//     const clearFlagAfterDelay = (row, flag, delay) => {
//         setTimeout(() => {
//             if (row && row[flag]) delete row[flag];
//         }, delay);
//     };
    
//     // Override frappe.model.set_value
//     if (typeof frappe !== 'undefined' && frappe.model?.set_value) {
//         const _orig_set_value = frappe.model.set_value;
//         frappe.model.set_value = function(cdt, cdn, field, value) {
//             if (field === 'price_list_rate') {
//                 const row = getRow(cdt, cdn);
//                 if (row) {
//                     if (row._suppress_price_update) return;
                    
//                     if (row._user_edited_price) {
//                         const timeSinceEdit = Date.now() - row._user_edited_price;
//                         if (timeSinceEdit < TIMEOUTS.USER_EDIT_EXPIRY) return;
//                         delete row._user_edited_price;
//                     }
//                 }
//             }
//             return _orig_set_value.apply(this, arguments);
//         };
//     }
    
//     // Form event handlers
//     frappe.ui.form.on('Sales Invoice Item', {
//         item_code: function(frm, cdt, cdn) {
//             const row = locals[cdt][cdn];
//             setTimeout(() => {
//                 if (!row._user_edited_stock_rate && row.price_list_rate) {
//                     row.stock_uom_rate = row.price_list_rate;
//                 }
//             }, TIMEOUTS.ITEM_CODE_UPDATE);
//         },
        
//         price_list_rate: function(frm, cdt, cdn) {
//             const row = locals[cdt][cdn];
            
//             // Mark as user-edited if currently focused on this field
//             if (isUserEditingField(cdn, 'price_list_rate')) {
//                 row._user_edited_price = Date.now();
//             }
            
//             // Auto-update stock_uom_rate if not manually edited
//             if (!row._user_edited_stock_rate) {
//                 row.stock_uom_rate = calculateStockUomRate(row.price_list_rate, row.conversion_factor);
//             }
//         },
        
//         stock_uom_rate: function(frm, cdt, cdn) {
//             const row = locals[cdt][cdn];
//             row._user_edited_stock_rate = Date.now();
//             clearFlagAfterDelay(row, '_user_edited_stock_rate', TIMEOUTS.USER_EDIT_EXPIRY);
//         },
        
//         qty: function(frm, cdt, cdn) {
//             const row = locals[cdt][cdn];
//             row._suppress_price_update = true;
//             clearFlagAfterDelay(row, '_suppress_price_update', TIMEOUTS.QTY_SUPPRESS);
//         },
        
//         uom: function(frm, cdt, cdn) {
//             const row = locals[cdt][cdn];
            
//             frappe.call({
//                 method: "kiwi_food_stuff.events.sales_invoice.get_conversion_factor",
//                 args: {
//                     item_code: row.item_code,
//                     uom: row.uom
//                 },
//                 callback: function(r) {
//                     if (!r.message) return;
                    
//                     const newConversion = r.message;
//                     frappe.model.set_value(cdt, cdn, 'conversion_factor', newConversion);
                    
//                     if (row.stock_uom_rate) {
//                         const newRate = row.stock_uom_rate * newConversion;
//                         setTimeout(() => {
//                             frappe.model.set_value(cdt, cdn, 'price_list_rate', newRate);
//                         }, TIMEOUTS.UOM_UPDATE);
//                     }
//                 }
//             });
//         }
//     });
// })();




(function () {
    'use strict';

    const getRow = (cdt, cdn) => locals?.[cdt]?.[cdn];
    const toStockRate = (price, conv) => {
        if (!price || !conv) return 0;
        return price / conv;
    };

    const toSellingRate = (stockRate, conv) => {
        if (!stockRate || !conv) return 0;
        return stockRate * conv;
    };

    const setCustomLastRate = (frm, cdt, cdn, value, was_dirty_before = frm.is_dirty()) => {
        const row = getRow(cdt, cdn);
        if (!row) return;

        const rate = flt(value);
        if (flt(row.custom_last_rate) === rate) return;

        row.custom_last_rate = rate;

        const grid_row = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
        if (grid_row) {
            grid_row.refresh_field('custom_last_rate');
        }

        if (!was_dirty_before && frm.is_dirty()) {
            frm.doc.__unsaved = undefined;
            removeEventListener('beforeunload', frm.beforeUnloadListener, { capture: true });
            frm.toolbar?.set_indicator();
        }
    };

    const setLastRateForRow = (frm, cdt, cdn) => {
        const row = getRow(cdt, cdn);
        if (!row?.item_code || !frm.doc.customer) {
            if (row) {
                setCustomLastRate(frm, cdt, cdn, 0);
            }
            return;
        }

        const was_dirty_before = frm.is_dirty();

        frappe.call({
            method: 'kiwi_food_stuff.events.sales_invoice.get_last_sales_invoice_rate',
            args: {
                customer: frm.doc.customer,
                item_code: row.item_code,
                current_invoice: frm.doc.name || null
            },
            callback(r) {
                const rate = r.message ? r.message.last_rate : 0;
                setCustomLastRate(frm, cdt, cdn, rate, was_dirty_before);
            }
        });
    };

    const setLastRateForAllRows = (frm) => {
        (frm.doc.items || []).forEach((row) => {
            if (row.item_code) {
                setLastRateForRow(frm, row.doctype, row.name);
            }
        });
    };

    const rememberNormalSubmitPermission = (frm) => {
        if (!frm.perm?.[0]) return;

        if (frm._kiwi_normal_submit_permission === undefined) {
            frm._kiwi_normal_submit_permission = frm.perm[0].submit;
        }
    };

    const refreshToolbar = (frm) => {
        if (frm.toolbar) {
            frm.toolbar.refresh();
        }
    };

    const restoreNormalSubmitPermission = (frm) => {
        if (!frm.perm?.[0] || frm._kiwi_normal_submit_permission === undefined) return;

        frm.perm[0].submit = frm._kiwi_normal_submit_permission;
        refreshToolbar(frm);
    };

    const applyCreditNoteSubmitPermission = (frm) => {
        if (!frm.perm?.[0]) return;

        rememberNormalSubmitPermission(frm);

        if (!cint(frm.doc.is_return) || cint(frm.doc.docstatus) !== 0) {
            restoreNormalSubmitPermission(frm);
            return;
        }

        frm.perm[0].submit = 0;
        refreshToolbar(frm);

        frm._kiwi_credit_note_submit_request = (frm._kiwi_credit_note_submit_request || 0) + 1;
        const requestId = frm._kiwi_credit_note_submit_request;

        frappe.call({
            method: 'kiwi_food_stuff.permissions.can_submit_credit_note',
            args: {
                docname: frm.doc.name
            },
            callback(r) {
                if (requestId !== frm._kiwi_credit_note_submit_request) return;

                if (!cint(frm.doc.is_return) || cint(frm.doc.docstatus) !== 0) {
                    restoreNormalSubmitPermission(frm);
                    return;
                }

                if (r.message === null || r.message === undefined) {
                    restoreNormalSubmitPermission(frm);
                    return;
                }

                frm.perm[0].submit = r.message ? 1 : 0;
                refreshToolbar(frm);
            }
        });
    };

    const applyUomConversion = (frm, cdt, cdn) => {
        return new Promise((resolve) => {
            const row = getRow(cdt, cdn);
            if (!row?.item_code || !row.uom) {
                resolve();
                return;
            }

            frappe.call({
                method: 'kiwi_food_stuff.events.sales_invoice.get_conversion_factor',
                args: {
                    item_code: row.item_code,
                    uom: row.uom
                },
                callback(r) {
                    const conv = flt(r.message || 1);

                    // Only update conversion_factor + stock_qty — keep rate / price_list_rate as-is
                    row.conversion_factor = conv;
                    row.stock_qty = flt(row.qty * conv, precision('stock_qty', row));

                    refresh_field('conversion_factor', cdn, 'items');
                    refresh_field('stock_qty', cdn, 'items');

                    frm.dirty();
                    resolve();
                }
            });
        });
    };

    const updateAllUomConversions = async (frm) => {
        const rows = (frm.doc.items || []).filter((row) => row.item_code && row.uom);
        if (!rows.length) {
            frappe.show_alert({ message: __('No items to update'), indicator: 'orange' });
            return;
        }

        frm.dashboard.set_headline_alert(__('Updating UOM conversions...'));

        for (const row of rows) {
            await applyUomConversion(frm, row.doctype, row.name);
        }

        frm.dashboard.clear_headline();

        await frm.save();
        frappe.show_alert({
            message: __('Conversion Factor and Stock Qty updated for {0} item(s)', [rows.length]),
            indicator: 'green'
        });
    };

    const setupUpdateUomButton = (frm) => {
        frm.remove_custom_button(__('Update UOM Conversion'));

        // Only after save, on draft invoices with items
        if (frm.is_new() || cint(frm.doc.docstatus) !== 0 || !frm.doc.items?.length) {
            return;
        }

        frm.add_custom_button(__('Update UOM Conversion'), () => {
            updateAllUomConversions(frm);
        });
    };

    frappe.ui.form.on('Sales Invoice', {
        refresh(frm) {
            applyCreditNoteSubmitPermission(frm);
            setupUpdateUomButton(frm);
            if (frm.doc.customer && frm.doc.items?.length) {
                setLastRateForAllRows(frm);
            }
        },

        is_return(frm) {
            applyCreditNoteSubmitPermission(frm);
        },

        customer(frm) {
            setLastRateForAllRows(frm);
        }
    });

    frappe.ui.form.on('Sales Invoice Item', {
        item_code(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row) return;

            row.ignore_pricing_rule = 1;

            if (row.price_list_rate && row.conversion_factor) {
                row.stock_uom_rate = toStockRate(row.price_list_rate, row.conversion_factor);
            }

            setLastRateForRow(frm, cdt, cdn);
        },

        price_list_rate(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row) return;

            row.ignore_pricing_rule = 1;

            if (row.conversion_factor) {
                row.stock_uom_rate = toStockRate(row.price_list_rate, row.conversion_factor);
            }
        },

        stock_uom_rate(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row || !row.conversion_factor) return;

            row.ignore_pricing_rule = 1;

            const newRate = toSellingRate(row.stock_uom_rate, row.conversion_factor);
            frappe.model.set_value(cdt, cdn, 'price_list_rate', newRate);
        },

        uom(frm, cdt, cdn) {
            applyUomConversion(frm, cdt, cdn);
        },

        qty(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row) return;

            row.ignore_pricing_rule = 1;

            const currentRate = row.price_list_rate;

            setTimeout(() => {
                frappe.model.set_value(cdt, cdn, 'price_list_rate', currentRate);
            }, 50);
        }
    });

})();