# Copyright (c) 2026, emeron and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class ExpenseEntry(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        self.total_amount = 0
        self.total_vat = 0

        for item in self.items:
            item.amount = flt(item.amount)

            if item.amount and item.vat_percentage:
                item.vat_amount = flt(item.amount * item.vat_percentage / 100)
            else:
                item.vat_amount = 0

            item.total_amount = flt(item.amount) + flt(item.vat_amount)

            self.total_amount += item.amount
            self.total_vat += item.vat_amount

        self.grand_total = self.total_amount + self.total_vat

    def on_submit(self):
        # Set status to Unpaid when document is submitted
        self.db_set("status", "Unpaid", update_modified=False)

    def on_cancel(self):
        if self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)
            if je.docstatus == 1:
                je.cancel()
        
        # Reset status to Draft when cancelled
        self.db_set("status", "", update_modified=False)

    @frappe.whitelist()
    def make_journal_entry(self):
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = self.company
        je.posting_date = self.posting_date
        je.remark = f"Journal Entry for Expense Entry {self.name}"

        for row in self.items:
            je.append("accounts", {
                "account": row.account,
                "debit_in_account_currency": row.amount,
                "party_type": row.party_type,
                "party": row.party,
                "user_remark": row.narration,
                "voucher_no": row.voucher_no,
                "trn": row.trn,
                "supplier_name": row.supplier_name
            })

            if row.vat_amount > 0:
                je.append("accounts", {
                    "account": row.tax_account,
                    "debit_in_account_currency": row.vat_amount
                })

            je.append("accounts", {
                "account": row.account_from,
                "credit_in_account_currency": row.total_amount
            })

        je.insert(ignore_permissions=True)
        je.db_set(
            "title",
            f"Expense Entry: {self.name}",
            update_modified=False
        )
        je.submit()
        
        # Update journal entry reference and change status to Paid
        self.db_set("journal_entry", je.name, update_modified=False)
        self.db_set("status", "Paid", update_modified=False)
        
        return je.name