(function () {
    'use strict';

    const { getRow, setCustomLastRate, wrapControllerMethod, setupUpdateUomButton } = kiwi_food_stuff.invoice;

    // Form handlers return this instead of nothing: returning nothing makes Frappe wait for
    // every pending request before running ERPNext's handler for the same event.
    const NOT_BLOCKING = () => Promise.resolve();

    const toStockRate = (price, conv) => {
        if (!price || !conv) return 0;
        return price / conv;
    };

    const toSellingRate = (stockRate, conv) => {
        if (!stockRate || !conv) return 0;
        return stockRate * conv;
    };

    // ---------------------------------------------------------------------------------
    // Last rate sold to the customer (custom_last_rate)
    // ---------------------------------------------------------------------------------

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

    // ---------------------------------------------------------------------------------
    // Per-form cache of each item's UOM conversion factors and price list rates, so a UOM
    // change is resolved locally instead of through several dependent server calls
    // ---------------------------------------------------------------------------------

    const PRICE_CACHE_TTL = 10 * 60 * 1000;

    const priceKey = (frm, item_code) =>
        [item_code, frm.doc.selling_price_list, frm.doc.customer, frm.doc.posting_date].join('|');

    const isFresh = (entry) => entry && Date.now() - entry.at < PRICE_CACHE_TTL;

    // Fetch prices for the items not cached yet, in one request
    const prefetchUomPrices = (frm, item_codes) => {
        if (!frm.doc.selling_price_list) return;

        const cache = (frm._kiwi_uom_prices = frm._kiwi_uom_prices || {});
        const missing = [...new Set(item_codes)].filter(
            (item_code) => item_code && !isFresh(cache[priceKey(frm, item_code)])
        );
        if (!missing.length) return;

        const keys = missing.map((item_code) => priceKey(frm, item_code));
        keys.forEach((key) => {
            cache[key] = { at: Date.now(), data: null };
        });

        frappe.xcall('kiwi_food_stuff.events.sales_invoice.get_item_uom_prices', {
            item_codes: missing,
            price_list: frm.doc.selling_price_list,
            customer: frm.doc.customer || null,
            transaction_date: frm.doc.posting_date || null
        }).then((data) => {
            missing.forEach((item_code, i) => {
                if (cache[keys[i]]) cache[keys[i]].data = data?.[item_code] || {};
            });
        }).catch(() => {
            keys.forEach((key) => delete cache[key]);
        });
    };

    const prefetchUomPricesForAllRows = (frm) => {
        if (cint(frm.doc.docstatus) !== 0) return;
        prefetchUomPrices(frm, (frm.doc.items || []).map((row) => row.item_code));
    };

    const getCachedUomPrice = (frm, row) => {
        const entry = frm._kiwi_uom_prices?.[priceKey(frm, row.item_code)];
        if (!isFresh(entry) || !entry.data) return null;

        const price = entry.data[row.uom];
        return price && price.price_list_rate !== null && price.price_list_rate !== undefined ? price : null;
    };

    // ---------------------------------------------------------------------------------
    // Patches to ERPNext's Sales Invoice controller, so prices don't depend on network timing
    // ---------------------------------------------------------------------------------

    const patchController = (frm) => {
        // UOM change: use the cached conversion factor and price, no server call.
        // Falls back to ERPNext's flow when the item's prices aren't cached yet.
        wrapControllerMethod(frm, 'uom', (erpnextUom) => function (doc, cdt, cdn) {
            const row = getRow(cdt, cdn);
            const price = row?.item_code && row.uom ? getCachedUomPrice(frm, row) : null;
            if (!price) {
                if (row?.item_code) prefetchUomPrices(frm, [row.item_code]);
                return erpnextUom.call(this, doc, cdt, cdn);
            }

            row.pricing_rules = '';
            row.conversion_factor = flt(price.conversion_factor) || 1;
            refresh_field('conversion_factor', cdn, 'items');
            this.conversion_factor(doc, cdt, cdn, true);

            const rate = flt(price.price_list_rate) * flt(doc.plc_conversion_rate || 1) / flt(doc.conversion_rate || 1);
            return frappe.model.set_value(cdt, cdn, 'price_list_rate', rate);
        });

        // Qty change: keep the row's rate and only recompute stock qty and totals.
        // ERPNext would re-fetch the price list rate here and overwrite the rate.
        wrapControllerMethod(frm, 'qty', (erpnextQty) => function (doc, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row?.price_list_rate) {
                return erpnextQty.call(this, doc, cdt, cdn);
            }

            this.conversion_factor(doc, cdt, cdn, true);
            this.calculate_taxes_and_totals();
        });

        // ERPNext drops apply_price_list while another call is in flight, which loses the
        // price update on a slow network. Replay the dropped call once the current one finishes.
        const pendingPriceList = new Map();
        wrapControllerMethod(frm, 'apply_price_list', (erpnextApplyPriceList) => function (item, reset_plc_conversion) {
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
        });
    };

    // ---------------------------------------------------------------------------------
    // Credit note submit permission
    // ---------------------------------------------------------------------------------

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

    // ---------------------------------------------------------------------------------
    // Form events
    // ---------------------------------------------------------------------------------

    frappe.ui.form.on('Sales Invoice', {
        onload(frm) {
            patchController(frm);
            return NOT_BLOCKING();
        },

        refresh(frm) {
            patchController(frm);
            applyCreditNoteSubmitPermission(frm);
            setupUpdateUomButton(frm);
            if (frm.doc.customer && frm.doc.items?.length) {
                setLastRateForAllRows(frm);
                prefetchUomPricesForAllRows(frm);
            }

            frm.set_query('uom', 'items', function(doc, cdt, cdn) {
                const row = locals[cdt][cdn];
                if (!row || !row.item_code) return {};
                return {
                    query: 'kiwi_food_stuff.events.sales_invoice.get_item_uoms',
                    filters: { item_code: row.item_code }
                };
            });
            return NOT_BLOCKING();
        },

        is_return(frm) {
            applyCreditNoteSubmitPermission(frm);
            return NOT_BLOCKING();
        },

        customer(frm) {
            setLastRateForAllRows(frm);
            prefetchUomPricesForAllRows(frm);
            return NOT_BLOCKING();
        }
    });

    frappe.ui.form.on('Sales Invoice Item', {
        item_code(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (row?.item_code) {
                prefetchUomPrices(frm, [row.item_code]);
            }

            setLastRateForRow(frm, cdt, cdn);
            return NOT_BLOCKING();
        },

        price_list_rate(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (row?.conversion_factor) {
                row.stock_uom_rate = toStockRate(row.price_list_rate, row.conversion_factor);
            }
            return NOT_BLOCKING();
        },

        stock_uom_rate(frm, cdt, cdn) {
            const row = getRow(cdt, cdn);
            if (!row || !row.conversion_factor) return NOT_BLOCKING();

            const newRate = toSellingRate(row.stock_uom_rate, row.conversion_factor);
            return frappe.model.set_value(cdt, cdn, 'price_list_rate', newRate);
        }

        // uom and qty are handled by the patched controller methods in patchController
    });
})();
