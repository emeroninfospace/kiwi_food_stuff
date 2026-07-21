(function () {
    'use strict';

    const getRow = (cdt, cdn) => locals?.[cdt]?.[cdn];

    const refreshLastRateField = (frm, cdn) => {
        const grid_row = frm.fields_dict.items?.grid?.grid_rows_by_docname?.[cdn];
        if (grid_row) {
            grid_row.refresh_field('custom_last_rate');
            return;
        }

        frm.fields_dict.items?.grid?.refresh();
    };

    const setCustomLastRate = (frm, cdt, cdn, value, was_dirty_before = frm.is_dirty()) => {
        const row = getRow(cdt, cdn);
        if (!row) return;

        const rate = flt(value);
        if (flt(row.custom_last_rate) === rate) return;

        row.custom_last_rate = rate;
        refreshLastRateField(frm, cdn);

        if (!was_dirty_before && frm.is_dirty()) {
            frm.doc.__unsaved = undefined;
            removeEventListener('beforeunload', frm.beforeUnloadListener, { capture: true });
            frm.toolbar?.set_indicator();
        }
    };

    const setLastRateForRow = (frm, cdt, cdn) => {
        const row = getRow(cdt, cdn);
        if (!row?.item_code || !frm.doc.supplier) {
            if (row) {
                setCustomLastRate(frm, cdt, cdn, 0);
            }
            return;
        }

        row._kiwi_last_rate_request = (row._kiwi_last_rate_request || 0) + 1;
        const requestId = row._kiwi_last_rate_request;
        const was_dirty_before = frm.is_dirty();

        frappe.call({
            method: 'kiwi_food_stuff.events.purchase_invoice.get_last_purchase_invoice_rate',
            args: {
                supplier: frm.doc.supplier,
                item_code: row.item_code,
                company: frm.doc.company || null,
                uom: row.uom || null,
                current_invoice: frm.doc.__islocal ? null : (frm.doc.name || null)
            },
            callback(r) {
                const current_row = getRow(cdt, cdn);
                if (!current_row || requestId !== current_row._kiwi_last_rate_request) return;

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

    frappe.ui.form.on('Purchase Invoice', {
        refresh(frm) {
            setupUpdateUomButton(frm);
            if (frm.doc.supplier && frm.doc.items?.length) {
                setLastRateForAllRows(frm);
            }
        },

        supplier(frm) {
            setLastRateForAllRows(frm);
        },

        company(frm) {
            setLastRateForAllRows(frm);
        }
    });

    frappe.ui.form.on('Purchase Invoice Item', {
        item_code(frm, cdt, cdn) {
            setTimeout(() => {
                setLastRateForRow(frm, cdt, cdn);
            }, 500);
        },

        uom(frm, cdt, cdn) {
            applyUomConversion(frm, cdt, cdn).then(() => {
                setLastRateForRow(frm, cdt, cdn);
            });
        }
    });
})();
