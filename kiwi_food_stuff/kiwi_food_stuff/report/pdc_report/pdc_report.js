// Copyright (c) 2026, Emeron and contributors
// For license information, please see license.txt

frappe.query_reports["PDC Report"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_default("company")
        },
        {
            fieldname: "customer",
            label: __("Customer"),
            fieldtype: "Link",
            options: "Customer"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nPending\nCleared\nBounced",
            default: "Pending"
        }
    ],

    onload: function(report) {

        // Hide selection tooltip
        $('<style>.dt-toast { display: none !important; }</style>').appendTo('head');

        report.page.add_inner_button(__('Update Status'), function() {

            let selected_rows = report.datatable.rowmanager.getCheckedRows();

            if (!selected_rows.length) {
                frappe.msgprint(__('Please select at least one row'));
                return;
            }

            let dialog = new frappe.ui.Dialog({
                title: __('Update Cheque Status'),
                fields: [
                    {
                        fieldname: 'new_status',
                        label: __('New Status'),
                        fieldtype: 'Select',
                        options: ['Pending', 'Cleared', 'Bounced'],
                        reqd: 1
                    }
                ],
                primary_action_label: __('Update'),
                primary_action: function(values) {

                    let payment_entries = [];

                    selected_rows.forEach(row_index => {
                        let row = report.data[row_index];
                        payment_entries.push(row.name);
                    });

                    frappe.call({
                        method: "kiwi_food_stuff.kiwi_food_stuff.report.pdc_report.pdc_report.update_multiple_status",
                        args: {
                            payment_entries: payment_entries,
                            status: values.new_status
                        },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Status updated successfully'),
                                    indicator: 'green'
                                });
                                report.refresh();
                            } else {
                                frappe.msgprint({
                                    title: __('Permission Denied or Error'),
                                    message: r.message ? r.message.message : __('Failed to update status'),
                                    indicator: 'red'
                                });
                            }
                        }
                    });

                    dialog.hide();
                }
            });

            dialog.show();
        });
    },

    get_datatable_options(options) {
        return Object.assign(options, {
            checkboxColumn: true
        });
    }
};
