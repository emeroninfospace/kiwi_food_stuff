// Helpers shared by the Sales Invoice and Purchase Invoice form scripts.
// Loaded before them through doctype_js in hooks.py.
frappe.provide('kiwi_food_stuff.invoice');

(function (invoice) {
    'use strict';

    const getRow = (cdt, cdn) => locals?.[cdt]?.[cdn];

    // Set the informational custom_last_rate without marking a saved form as dirty
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

    // Replace a method of ERPNext's form controller (frm.cscript) once per form.
    // `wrapper` receives the original method and returns the replacement.
    const wrapControllerMethod = (frm, method, wrapper) => {
        const original = frm.cscript?.[method];
        if (typeof original !== 'function' || original._kiwi_wrapped) return;

        const wrapped = wrapper(original);
        wrapped._kiwi_wrapped = true;
        frm.cscript[method] = wrapped;
    };

    // Re-read conversion factors of all rows in one request and save
    const updateAllUomConversions = async (frm) => {
        const rows = (frm.doc.items || []).filter((row) => row.item_code && row.uom);
        if (!rows.length) {
            frappe.show_alert({ message: __('No items to update'), indicator: 'orange' });
            return;
        }

        frm.dashboard.set_headline_alert(__('Updating UOM conversions...'));

        try {
            const factors = await frappe.xcall('kiwi_food_stuff.events.sales_invoice.get_conversion_factors', {
                items: rows.map((row) => ({ name: row.name, item_code: row.item_code, uom: row.uom }))
            });

            // Only update conversion_factor + stock_qty — keep rate / price_list_rate as-is
            rows.forEach((row) => {
                const conv = flt(factors?.[row.name] || 1);
                row.conversion_factor = conv;
                row.stock_qty = flt(row.qty * conv, precision('stock_qty', row));
            });

            frm.refresh_field('items');
            frm.dirty();
        } finally {
            frm.dashboard.clear_headline();
        }

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

    Object.assign(invoice, {
        getRow,
        setCustomLastRate,
        wrapControllerMethod,
        setupUpdateUomButton
    });
})(kiwi_food_stuff.invoice);
