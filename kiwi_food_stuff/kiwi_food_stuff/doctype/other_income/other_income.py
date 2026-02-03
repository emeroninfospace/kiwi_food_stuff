# Copyright (c) 2026, Emeron and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class OtherIncome(Document):

    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        self.total_amount = 0
        self.total_vat = 0

        for d in self.items:
            amount = flt(d.amount)
            vat_percent = flt(d.vat_percentage)

            if vat_percent:
                d.vat_amount = flt(amount * vat_percent / 100)
            else:
                d.vat_amount = 0

            d.total_amount = amount + flt(d.vat_amount)

            self.total_amount += amount
            self.total_vat += flt(d.vat_amount)

        self.grand_total = self.total_amount + self.total_vat

    def on_submit(self):
        self.db_set("status", "Unpaid", update_modified=False)

    def on_cancel(self):
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()

        self.db_set("status", "", update_modified=False)

    @frappe.whitelist()
    def make_journal_entry(self):
        je = frappe.new_doc("Journal Entry")
        je.company = self.company
        je.posting_date = self.posting_date
        je.remark = f"Other Income: {self.name}"

        for row in self.items:
            amount = flt(row.amount)
            vat_amount = flt(row.vat_amount)

            je.append("accounts", {
                "account": row.received_to,
                "debit_in_account_currency": amount + vat_amount
            })

            je.append("accounts", {
                "account": row.income_account,
                "credit_in_account_currency": amount,
                "user_remark": row.narration
            })

            if vat_amount:
                je.append("accounts", {
                    "account": row.tax_account,
                    "credit_in_account_currency": vat_amount
                })

        je.insert(ignore_permissions=True)
        je.submit()

        self.db_set("journal_entry", je.name, update_modified=False)
        self.db_set("status", "Paid", update_modified=False)

        return je.name