(function () {
    'use strict';

    const { getRow, setCustomLastRate, wrapControllerMethod, setupUpdateUomButton } = kiwi_food_stuff.invoice;

    // Form handlers return this instead of nothing: returning nothing makes Frappe wait for
    // every pending request before running ERPNext's handler for the same event.
    const NOT_BLOCKING = () => Promise.resolve();

    const currentInvoice = (frm) => (frm.doc.__islocal ? null : (frm.doc.name || null));

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
                current_invoice: currentInvoice(frm)
            },
            callback(r) {
                const current_row = getRow(cdt, cdn);
                if (!current_row || requestId !== current_row._kiwi_last_rate_request) return;

                const rate = r.message ? r.message.last_rate : 0;
                setCustomLastRate(frm, cdt, cdn, rate, was_dirty_before);
            }
        });
    };

    // One request for all rows instead of one per row
    const setLastRateForAllRows = (frm) => {
        const rows = (frm.doc.items || []).filter((row) => row.item_code);
        if (!rows.length) return;

        if (!frm.doc.supplier) {
            rows.forEach((row) => setCustomLastRate(frm, row.doctype, row.name, 0));
            return;
        }

        const was_dirty_before = frm.is_dirty();
        const requestIds = {};
        rows.forEach((row) => {
            row._kiwi_last_rate_request = (row._kiwi_last_rate_request || 0) + 1;
            requestIds[row.name] = row._kiwi_last_rate_request;
        });

        frappe.call({
            method: 'kiwi_food_stuff.events.purchase_invoice.get_last_purchase_invoice_rates',
            args: {
                supplier: frm.doc.supplier,
                items: rows.map((row) => ({ name: row.name, item_code: row.item_code, uom: row.uom || null })),
                company: frm.doc.company || null,
                current_invoice: currentInvoice(frm)
            },
            callback(r) {
                const rates = r.message || {};
                rows.forEach((row) => {
                    const current_row = getRow(row.doctype, row.name);
                    if (!current_row || requestIds[row.name] !== current_row._kiwi_last_rate_request) return;

                    const last = rates[row.name];
                    setCustomLastRate(frm, row.doctype, row.name, last ? last.last_rate : 0, was_dirty_before);
                });
            }
        });
    };

    // Refresh the last rate once ERPNext has finished updating the row, instead of
    // guessing with a timer. The last rate depends on the row's UOM, which ERPNext
    // sets in the item_code and uom responses.
    const patchController = (frm) => {
        ['item_code', 'uom'].forEach((method) => {
            wrapControllerMethod(frm, method, (erpnextMethod) => function (doc, cdt, cdn) {
                const req = erpnextMethod.call(this, doc, cdt, cdn);
                Promise.resolve(req).then(
                    () => setLastRateForRow(frm, cdt, cdn),
                    () => {}
                );
                return req;
            });
        });
    };

    frappe.ui.form.on('Purchase Invoice', {
        onload(frm) {
            patchController(frm);
            return NOT_BLOCKING();
        },

        refresh(frm) {
            patchController(frm);
            setupUpdateUomButton(frm);
            if (frm.doc.supplier && frm.doc.items?.length) {
                setLastRateForAllRows(frm);
            }
            return NOT_BLOCKING();
        },

        supplier(frm) {
            setLastRateForAllRows(frm);
            return NOT_BLOCKING();
        },

        company(frm) {
            setLastRateForAllRows(frm);
            return NOT_BLOCKING();
        }
    });
})();
