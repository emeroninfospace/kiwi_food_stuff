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
        const item_code = row.item_code;

        frappe.call({
            method: 'kiwi_food_stuff.events.sales_invoice.get_last_sales_invoice_rate',
            args: {
                customer: frm.doc.customer,
                item_code: item_code,
                current_invoice: frm.doc.name || null
            },
            callback(r) {
                // Ignore a late response if the row's item was changed meanwhile
                if (getRow(cdt, cdn)?.item_code !== item_code) return;

                const rate = r.message ? r.message.last_rate : 0;
                setCustomLastRate(frm, cdt, cdn, rate, was_dirty_before);
            }
        });
    };

    // One request for all rows instead of one per row
    const setLastRateForAllRows = (frm) => {
        const rows = (frm.doc.items || []).filter((row) => row.item_code);
        if (!rows.length) return;

        if (!frm.doc.customer) {
            rows.forEach((row) => setCustomLastRate(frm, row.doctype, row.name, 0));
            return;
        }

        const was_dirty_before = frm.is_dirty();

        frappe.call({
            method: 'kiwi_food_stuff.events.sales_invoice.get_last_sales_invoice_rates',
            args: {
                customer: frm.doc.customer,
                item_codes: rows.map((row) => row.item_code),
                current_invoice: frm.doc.name || null
            },
            callback(r) {
                const rates = r.message || {};
                rows.forEach((row) => {
                    const current = getRow(row.doctype, row.name);
                    if (!current?.item_code) return;

                    const last = rates[current.item_code];
                    setCustomLastRate(frm, row.doctype, row.name, last ? last.last_rate : 0, was_dirty_before);
                });
            }
        });
    };

    // Per-form cache of each item's UOM conversion factors and price list rates, so a UOM
    // change is resolved locally instead of through several dependent server calls
    const PRICE_CACHE_TTL = 10 * 60 * 1000;

    const priceKey = (frm, item_code) =>
        [item_code, frm.doc.selling_price_list, frm.doc.customer, frm.doc.posting_date].join('|');

    const prefetchUomPrices = (frm, item_code) => {
        if (!item_code || !frm.doc.selling_price_list) return;

        frm._kiwi_uom_prices = frm._kiwi_uom_prices || {};
        const key = priceKey(frm, item_code);
        const cached = frm._kiwi_uom_prices[key];
        if (cached && Date.now() - cached.at < PRICE_CACHE_TTL) return;

        frm._kiwi_uom_prices[key] = { at: Date.now(), data: null };

        frappe.xcall('kiwi_food_stuff.events.sales_invoice.get_item_uom_prices', {
            item_code: item_code,
            price_list: frm.doc.selling_price_list,
            customer: frm.doc.customer || null,
            transaction_date: frm.doc.posting_date || null
        }).then((data) => {
            if (frm._kiwi_uom_prices[key]) frm._kiwi_uom_prices[key].data = data;
        }).catch(() => {
            delete frm._kiwi_uom_prices[key];
        });
    };

    const getCachedUomPrice = (frm, row) => {
        const cached = frm._kiwi_uom_prices?.[priceKey(frm, row.item_code)];
        if (!cached?.data || Date.now() - cached.at >= PRICE_CACHE_TTL) return null;
        return cached.data[row.uom] || null;
    };

    // Patch ERPNext's Sales Invoice controller so price changes don't depend on network timing
    const patchController = (frm) => {
        const ctrl = frm.cscript;
        if (!ctrl || ctrl._kiwi_patched) return;
        ctrl._kiwi_patched = true;

        // UOM change: use the cached conversion factor and price, no server call.
        // Falls back to ERPNext's flow when the item's prices aren't cached yet.
        const erpnextUom = ctrl.uom;
        ctrl.uom = function (doc, cdt, cdn) {
            const row = getRow(cdt, cdn);
            const price = row?.item_code && row.uom ? getCachedUomPrice(frm, row) : null;
            if (!price || price.price_list_rate === null || price.price_list_rate === undefined) {
                if (row?.item_code) prefetchUomPrices(frm, row.item_code);
                return erpnextUom.call(this, doc, cdt, cdn);
            }

            row.pricing_rules = '';
            row.conversion_factor = flt(price.conversion_factor) || 1;
            refresh_field('conversion_factor', cdn, 'items');
            this.conversion_factor(doc, cdt, cdn, true);

            const rate = flt(price.price_list_rate) * flt(doc.plc_conversion_rate || 1) / flt(doc.conversion_rate || 1);
            return frappe.model.set_value(cdt, cdn, 'price_list_rate', rate);
        };

        // Qty change: keep the row's rate and only recompute stock qty and totals.
        // ERPNext would re-fetch the price list rate here and overwrite the rate.
        const erpnextQty = ctrl.qty;
        ctrl.qty = function (doc, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row?.price_list_rate) {
                return erpnextQty.call(this, doc, cdt, cdn);
            }

            this.conversion_factor(doc, cdt, cdn, true);
            this.calculate_taxes_and_totals();
        };

        // ERPNext drops apply_price_list while another call is in flight, which loses the
        // price update on a slow network. Replay the dropped call once the current one finishes.
        const erpnextApplyPriceList = ctrl.apply_price_list;
        const pendingPriceList = new Map();
        ctrl.apply_price_list = function (item, reset_plc_conversion) {
            if (this.in_apply_price_list) {
                pendingPriceList.set(item ? item.name : '__all__', [item, reset_plc_conversion]);
                return;
            }

            const req = erpnextApplyPriceList.call(this, item, reset_plc_conversion);
            req?.always?.(() => {
                const next = pendingPriceList.entries().next().value;
                if (!next) return;

                pendingPriceList.delete(next[0]);
                const [row, reset] = next[1];
                if (!row || getRow(row.doctype, row.name)) {
                    this.apply_price_list(row, reset);
                }
            });
            return req;
        };
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
        onload(frm) {
            patchController(frm);
        },

        refresh(frm) {
            patchController(frm);
            applyCreditNoteSubmitPermission(frm);
            setupUpdateUomButton(frm);
            if (frm.doc.customer && frm.doc.items?.length) {
                setLastRateForAllRows(frm);
            }

            frm.set_query('uom', 'items', function(doc, cdt, cdn) {
                const row = locals[cdt][cdn];
                if (!row || !row.item_code) return {};
                return {
                    query: 'kiwi_food_stuff.events.sales_invoice.get_item_uoms',
                    filters: { item_code: row.item_code }
                };
            });
        },

        is_return(frm) {
            applyCreditNoteSubmitPermission(frm);
        },

        customer(frm) {
            setLastRateForAllRows(frm);
        }
    });

    frappe.ui.form.on('Sales Invoice Item', {
        // These handlers return a resolved promise: returning nothing makes Frappe wait for
        // every pending request before running ERPNext's handler for the same field.
        item_code(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (row?.item_code) {
                prefetchUomPrices(frm, row.item_code);
            }

            setLastRateForRow(frm, cdt, cdn);
            return Promise.resolve();
        },

        price_list_rate(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row) return Promise.resolve();

            row.ignore_pricing_rule = 1;

            if (row.conversion_factor) {
                row.stock_uom_rate = toStockRate(row.price_list_rate, row.conversion_factor);
            }
            return Promise.resolve();
        },

        stock_uom_rate(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row || !row.conversion_factor) return;

            row.ignore_pricing_rule = 1;

            const newRate = toSellingRate(row.stock_uom_rate, row.conversion_factor);
            frappe.model.set_value(cdt, cdn, 'price_list_rate', newRate);
        }

        // uom and qty are handled by the patched controller methods in patchController
    });

})();