frappe.listview_settings['Payment Entry'] = {
    add_fields: ['mode_of_payment'],
    formatters: {
        custom_pdc_status: function(value, df, doc) {
            if (doc.mode_of_payment === 'Cash') {
                return '';
            }
            return value;
        }
    }
};
