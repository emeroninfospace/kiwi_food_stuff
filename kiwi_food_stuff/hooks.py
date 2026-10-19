app_name = "kiwi_food_stuff"
app_title = "Kiwi Food Stuff"
app_publisher = "Emeron"
app_description = "Kiwi Food Stuff"
app_email = "muhammed786ashkar@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "kiwi_food_stuff",
# 		"logo": "/assets/kiwi_food_stuff/logo.png",
# 		"title": "Kiwi Food Stuff",
# 		"route": "/kiwi_food_stuff",
# 		"has_permission": "kiwi_food_stuff.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/kiwi_food_stuff/css/kiwi_food_stuff.css"
# app_include_js = "/assets/kiwi_food_stuff/js/kiwi_food_stuff.js"

# include js, css files in header of web template
# web_include_css = "/assets/kiwi_food_stuff/css/kiwi_food_stuff.css"
# web_include_js = "/assets/kiwi_food_stuff/js/kiwi_food_stuff.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "kiwi_food_stuff/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
               "Sales Invoice" : ["public/js/invoice_common.js", "public/js/sales_invoice.js"],
               "Purchase Invoice" : ["public/js/invoice_common.js", "public/js/purchase_invoice.js"],
               "Payment Entry" : "public/js/payment_entry.js"}
doctype_list_js = {"Payment Entry" : "public/js/payment_entry_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "kiwi_food_stuff/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "kiwi_food_stuff.utils.jinja_methods",
# 	"filters": "kiwi_food_stuff.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "kiwi_food_stuff.install.before_install"
# after_install = "kiwi_food_stuff.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "kiwi_food_stuff.uninstall.before_uninstall"
# after_uninstall = "kiwi_food_stuff.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "kiwi_food_stuff.utils.before_app_install"
# after_app_install = "kiwi_food_stuff.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "kiwi_food_stuff.utils.before_app_uninstall"
# after_app_uninstall = "kiwi_food_stuff.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "kiwi_food_stuff.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
has_permission = {
	"*": "kiwi_food_stuff.permissions.has_permission",
}

extend_bootinfo = [
	"kiwi_food_stuff.permissions.extend_bootinfo",
]

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Invoice": {
        "after_insert": "kiwi_food_stuff.events.sales_invoice.add_pos_sales_person",
        "before_insert": "kiwi_food_stuff.events.sales_invoice.set_sales_person",
        # "validate": "kiwi_food_stuff.events.sales_invoice.validate_sales_invoice",
        # "before_submit": "kiwi_food_stuff.events.sales_invoice.validate_sales_invoice_price_list_rates"
    }
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"kiwi_food_stuff.tasks.all"
# 	],
# 	"daily": [
# 		"kiwi_food_stuff.tasks.daily"
# 	],
# 	"hourly": [
# 		"kiwi_food_stuff.tasks.hourly"
# 	],
# 	"weekly": [
# 		"kiwi_food_stuff.tasks.weekly"
# 	],
# 	"monthly": [
# 		"kiwi_food_stuff.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "kiwi_food_stuff.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.client.delete": "kiwi_food_stuff.permissions.delete_doc",
	"frappe.desk.reportview.delete_items": "kiwi_food_stuff.permissions.delete_items",
	"frappe.desk.form.save.savedocs": "kiwi_food_stuff.permissions.savedocs",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "kiwi_food_stuff.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["kiwi_food_stuff.utils.before_request"]
# after_request = ["kiwi_food_stuff.utils.after_request"]

# Job Events
# ----------
# before_job = ["kiwi_food_stuff.utils.before_job"]
# after_job = ["kiwi_food_stuff.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", ["Sales Invoice-custom_sales_person",
                            "UOM Conversion Detail-custom_unit_qty",
                            "UOM Conversion Detail-custom_unit",
                            "UOM Conversion Detail-custom_qty",
                            "Payment Entry-custom_note",
                            "POS Invoice-custom_type",
                            "Payment Entry-custom_pdc_status",
                            "Sales Invoice Item-custom_last_rate",
                            "Purchase Invoice Item-custom_last_price",
                            ]]
        ]
    },
    {
    "dt": "Property Setter",
    "filters": [
        [
            "name",
            "in",
            [
                "Sales Invoice-main-field_order",
            ]
        ]
    ]
    },
    {
        "dt": "Custom HTML Block",
        "filters": [
            ["name", "in", ["Accouting Dashboard"]]
        ]
    }

]


# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"kiwi_food_stuff.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

