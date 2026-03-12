# Copyright (c) 2026, Emeron and contributors
# License: see license.txt

import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_data(filters):
    company = filters.get("company")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    party_type = filters.get("party_type")
    customer = filters.get("customer")
    supplier = filters.get("supplier")
    
    company_accounts = frappe.get_cached_value(
        "Company",
        company,
        ["default_receivable_account", "default_payable_account"],
        as_dict=True
    )

    receivable_account = company_accounts.default_receivable_account
    payable_account = company_accounts.default_payable_account

    if not receivable_account or not payable_account:
        frappe.throw("Default Receivable / Payable Account not set in Company")

    data = []
    
    if not all([company, from_date, to_date]):
        frappe.throw("Company, From Date and To Date are mandatory")

    voucher_no_filter = f"%{filters.get('voucher_no')}%" if filters.get("voucher_no") else None
    selected_voucher_type = filters.get("voucher_type")

    processed_vouchers = set()


    if selected_voucher_type in (None, "", "Sales Invoice"):
        if party_type != "Supplier":
            conditions = [
                "si.posting_date BETWEEN %(from_date)s AND %(to_date)s",
                "si.company = %(company)s",
                "si.docstatus = 1",
            ]

            params = {
                "from_date": from_date,
                "to_date": to_date,
                "company": company,
                "receivable_account": receivable_account
            }

            if voucher_no_filter:
                conditions.append("si.name LIKE %(voucher_no)s")
                params["voucher_no"] = voucher_no_filter

            if customer:
                conditions.append("si.customer = %(customer)s")
                params["customer"] = customer

            if filters.get("sales_person"):
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM `tabSales Team` st
                        WHERE st.parent = si.name
                        AND st.sales_person = %(sales_person)s
                    )
                """)
                params["sales_person"] = filters["sales_person"]

            sql_cond = " AND ".join(conditions)

            sales_raw = frappe.db.sql(f"""
                SELECT 
                    si.posting_date,
                    si.name AS voucher_no,
                    si.customer,
                    sii.item_name,
                    si.grand_total AS amount,
                    st.sales_person
                FROM `tabSales Invoice` si
                LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
                LEFT JOIN `tabSales Team` st ON st.parent = si.name
                WHERE {sql_cond}
                ORDER BY si.posting_date,    si.name, sii.idx
            """, params, as_dict=True)

            grouped = {}
            for row in sales_raw:
                key = row.voucher_no
                if key not in grouped:
                    grouped[key] = {
                        "posting_date": row.posting_date,
                        "voucher_no": row.voucher_no,
                        "voucher_type": "Sales Invoice",
                        "customer": row.customer,
                        "sales_person": row.sales_person or "",
                        "amount": row.amount or 0,
                        "items": []
                    }
                if row.item_name:
                    grouped[key]["items"].append(row.item_name)

            for key, g in grouped.items():
                if len(g["items"]) == 0:
                    particulars = "Sales Invoice"
                elif len(g["items"]) == 1:
                    particulars = g["items"][0]
                else:
                    particulars = f"{g['items'][0]} + more"

                data.append({
                    "posting_date": g["posting_date"],
                    "particulars": particulars,
                    "voucher_type": g["voucher_type"],
                    "voucher_no": g["voucher_no"],
                    "debit_qty": g["amount"],
                    "credit_qty": 0,
                    "sales_person": g["sales_person"],
                    "party": g["customer"]
                })
                processed_vouchers.add(key)

    if selected_voucher_type in (None, "", "Purchase Invoice"):
        if party_type != "Customer":
            conditions = [
                "pi.posting_date BETWEEN %(from_date)s AND %(to_date)s",
                "pi.company = %(company)s",
                "pi.docstatus = 1",
                "gle.is_cancelled = 0"
            ]

            params = {
                "from_date": from_date,
                "to_date": to_date,
                "company": company,
                "payable_account": payable_account
            }

            if voucher_no_filter:
                conditions.append("pi.name LIKE %(voucher_no)s")
                params["voucher_no"] = voucher_no_filter

            if supplier:
                conditions.append("pi.supplier = %(supplier)s")
                params["supplier"] = supplier

            sql_cond = " AND ".join(conditions)

            purchase_raw = frappe.db.sql(f"""
                SELECT 
                    pi.posting_date,
                    pi.name AS voucher_no,
                    pi.supplier,
                    pii.item_name,
                    gle.credit AS amount
                FROM `tabPurchase Invoice` pi
                INNER JOIN `tabGL Entry` gle 
                    ON gle.voucher_type = 'Purchase Invoice'
                    AND gle.voucher_no = pi.name
                    AND gle.account = %(payable_account)s
                    AND gle.is_cancelled = 0
                LEFT JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
                WHERE {sql_cond}
                ORDER BY pi.posting_date, pi.name, pii.idx
            """, params, as_dict=True)

            grouped = {}
            for row in purchase_raw:
                key = row.voucher_no
                if key not in grouped:
                    grouped[key] = {
                        "posting_date": row.posting_date,
                        "voucher_no": row.voucher_no,
                        "voucher_type": "Purchase Invoice",
                        "supplier": row.supplier,
                        "amount": row.amount or 0,
                        "items": []
                    }
                if row.item_name:
                    grouped[key]["items"].append(row.item_name)

            for key, g in grouped.items():
                if len(g["items"]) == 0:
                    particulars = "Purchase Invoice"
                elif len(g["items"]) == 1:
                    particulars = g["items"][0]
                else:
                    particulars = f"{g['items'][0]} + more"

                data.append({
                    "posting_date": g["posting_date"],
                    "particulars": particulars,
                    "voucher_type": g["voucher_type"],
                    "voucher_no": g["voucher_no"],
                    "debit_qty": 0,
                    "credit_qty": g["amount"],
                    "sales_person": "",
                    "party": g["supplier"]
                })
                processed_vouchers.add(key)


    if selected_voucher_type in (None, "", "Payment Entry"):
        conditions = [
            "pe.posting_date BETWEEN %(from_date)s AND %(to_date)s",
            "pe.company = %(company)s",
            "pe.docstatus = 1",
        ]

        params = {
            "from_date": from_date,
            "to_date": to_date,
            "company": company
        }

        if voucher_no_filter:
            conditions.append("pe.name LIKE %(voucher_no)s")
            params["voucher_no"] = voucher_no_filter

        if party_type == "Customer" and customer:
            conditions.append("pe.party = %(party)s AND pe.party_type = 'Customer'")
            params["party"] = customer
        elif party_type == "Supplier" and supplier:
            conditions.append("pe.party = %(party)s AND pe.party_type = 'Supplier'")
            params["party"] = supplier

        sql_cond = " AND ".join(conditions)

        payments = frappe.db.sql(f"""
            SELECT 
                pe.posting_date,
                pe.name AS voucher_no,
                pe.party,
                pe.party_type,
                pe.paid_amount,
                pe.received_amount
            FROM `tabPayment Entry` pe
            WHERE {sql_cond}
            ORDER BY pe.posting_date, pe.name
        """, params, as_dict=True)

        for row in payments:
            if row.party_type == "Customer":
                particulars = f"Payment received from {row.party}"
                debit_qty = row.received_amount or 0
                credit_qty = 0
            else:
                particulars = f"Payment made to {row.party}"
                debit_qty = 0
                credit_qty = row.paid_amount or 0

            data.append({
                "posting_date": row.posting_date,
                "particulars": particulars,
                "voucher_type": "Payment Entry",
                "voucher_no": row.voucher_no,
                "debit_qty": debit_qty,
                "credit_qty": credit_qty,
                "sales_person": "",
                "party": row.party or ""
            })


    if selected_voucher_type in (None, "", "Journal Entry"):
        conditions = [
            "je.posting_date BETWEEN %(from_date)s AND %(to_date)s",
            "je.company = %(company)s",
            "je.docstatus = 1",
            "gle.is_cancelled = 0"
        ]

        params = {
            "from_date": from_date,
            "to_date": to_date,
            "company": company
        }

        if voucher_no_filter:
            conditions.append("je.name LIKE %(voucher_no)s")
            params["voucher_no"] = voucher_no_filter

        if party_type == "Customer" and customer:
            conditions.append("gle.party = %(party)s AND gle.party_type = 'Customer'")
            params["party"] = customer
        elif party_type == "Supplier" and supplier:
            conditions.append("gle.party = %(party)s AND gle.party_type = 'Supplier'")
            params["party"] = supplier

        sql_cond = " AND ".join(conditions)

        journals_raw = frappe.db.sql(f"""
            SELECT 
                je.posting_date,
                je.name AS voucher_no,
                gle.party,
                gle.party_type,
                gle.debit,
                gle.credit,
                gle.account
            FROM `tabJournal Entry` je
            INNER JOIN `tabGL Entry` gle 
                ON gle.voucher_type = 'Journal Entry'
                AND gle.voucher_no = je.name
                AND gle.is_cancelled = 0
            WHERE {sql_cond}
            ORDER BY je.posting_date, je.name, gle.idx
        """, params, as_dict=True)

        grouped = {}
        for row in journals_raw:
            key = row.voucher_no
            if key not in grouped:
                grouped[key] = {
                    "posting_date": row.posting_date,
                    "voucher_no": row.voucher_no,
                    "voucher_type": "Journal Entry",
                    "party": row.party or "",
                    "party_type": row.party_type,
                    "entries": []
                }
            account_str = row.account
            if row.party:
                account_str += f" ({row.party})"
            grouped[key]["entries"].append(account_str)

        for key, g in grouped.items():
            if len(g["entries"]) == 0:
                particulars = "Journal Entry"
            elif len(g["entries"]) == 1:
                particulars = g["entries"][0]
            else:
                particulars = f"{g['entries'][0]} + more"

            debit_total = sum(r.debit for r in journals_raw if r.voucher_no == key)
            credit_total = sum(r.credit for r in journals_raw if r.voucher_no == key)

            data.append({
                "posting_date": g["posting_date"],
                "particulars": particulars,
                "voucher_type": g["voucher_type"],
                "voucher_no": g["voucher_no"],
                "debit_qty": debit_total,
                "credit_qty": credit_total,
                "sales_person": "",
                "party": g["party"]
            })

    return sorted(data, key=lambda x: (x["posting_date"], x["voucher_no"]))

def get_columns():
    return [
        {
            "label": "Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110
        },
        {
            "label": "Particulars",
            "fieldname": "particulars",
            "fieldtype": "Data",
            "width": 340
        },
        {
            "label": "Party",
            "fieldname": "party",
            "fieldtype": "Data",
            "width": 300
        },
        {
            "label": "Vch Type",
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "width": 130
        },
        {
            "label": "Vch No",
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 170
        },
        {
            "label": "Sales Person",
            "fieldname": "sales_person",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Debit Amount (Inwards)",
            "fieldname": "debit_qty",
            "fieldtype": "Currency",
            "options": "currency:company",
            "width": 160
        },
        {
            "label": "Credit Amount (Outwards)",
            "fieldname": "credit_qty",
            "fieldtype": "Currency",
            "options": "currency:company",
            "width": 160
        },
    ]