# Copyright (c) 2026, Emeron and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class KiwiFoodStuffSettings(Document):
	def validate(self):
		if self.delete_permission and not self.role:
			frappe.throw(_("Role is required when Delete Permission is enabled."))

		if self.credit_note_submit_permission and not self.credit_note_role:
			frappe.throw(_("Credit Note Role is required when Credit Note Submit Permission is enabled."))

	def on_update(self):
		frappe.clear_cache(doctype=self.doctype)
		frappe.cache.delete_key("bootinfo")
