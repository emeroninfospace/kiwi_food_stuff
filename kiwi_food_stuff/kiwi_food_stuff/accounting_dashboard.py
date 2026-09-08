import frappe
from frappe.utils import getdate, nowdate, add_days, add_months, flt


@frappe.whitelist()
def get_overview_dashboard_data(period="this_year", date_from=None, date_to=None, company=None):
	company = company or _default_company()
	date_range = _resolve_period(period, date_from, date_to)

	data = {
		"period_label": date_range["label"],
		"company": company,
		"total_customers": frappe.db.count("Customer"),
		"total_suppliers": frappe.db.count("Supplier"),
	}

	data.update(_get_sales_purchase(company, date_range))
	data.update(_get_received(company, date_range))
	data.update(_get_balances(company))
	data.update(_get_payable(company))
	data.update(_get_receivable(company))
	data.update(_get_bills_payable(company))
	data.update(_get_other_income_pending(company))
	data["sales_by_person"] = _get_sales_by_person(company, date_range)
	data["sales_by_territory"] = _get_sales_by_territory(company, date_range)
	data["recent_sales"] = _get_recent_sales(company)
	data["recent_purchases"] = _get_recent_purchases(company)
	data["overdue_receivables"] = _get_overdue("Sales Invoice", company)
	data["overdue_payables"] = _get_overdue("Purchase Invoice", company)
	data["monthly_sales_purchase"] = _get_monthly_sales_purchase(company)

	return data


def _default_company():
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	return company


def _resolve_period(period, date_from, date_to):
	today = getdate(nowdate())

	if period == "this_month":
		start, end, label = today.replace(day=1), today, "This Month"
	elif period == "last_month":
		first_this = today.replace(day=1)
		end = add_days(first_this, -1)
		start = end.replace(day=1)
		label = "Last Month"
	elif period == "last_year":
		start = today.replace(month=1, day=1, year=today.year - 1)
		end = today.replace(month=12, day=31, year=today.year - 1)
		label = "Last Year"
	elif period == "custom" and date_from and date_to:
		start, end = getdate(date_from), getdate(date_to)
		label = "{0} to {1}".format(start, end)
	else:
		start, end, label = today.replace(month=1, day=1), today, "This Year"

	return {"start": start, "end": end, "label": label}


def _get_sales_purchase(company, date_range):
	total_sales = frappe.db.sql(
		"""
		SELECT IFNULL(SUM(grand_total), 0) FROM `tabSales Invoice`
		WHERE company = %s AND docstatus = 1 AND posting_date BETWEEN %s AND %s
		""",
		(company, date_range["start"], date_range["end"]),
	)[0][0] or 0

	total_purchase = frappe.db.sql(
		"""
		SELECT IFNULL(SUM(grand_total), 0) FROM `tabPurchase Invoice`
		WHERE company = %s AND docstatus = 1 AND posting_date BETWEEN %s AND %s
		""",
		(company, date_range["start"], date_range["end"]),
	)[0][0] or 0

	return {"total_sales": total_sales, "total_purchase": total_purchase}


def _get_received(company, date_range):
	total_received = frappe.db.sql(
		"""
		SELECT IFNULL(SUM(base_paid_amount), 0) FROM `tabPayment Entry`
		WHERE company = %s AND docstatus = 1 AND payment_type = 'Receive'
			AND posting_date BETWEEN %s AND %s
		""",
		(company, date_range["start"], date_range["end"]),
	)[0][0] or 0
	return {"total_received": total_received}


def _get_balances(company):
	def account_list(account_type):
		accounts = frappe.db.get_all(
			"Account",
			filters={"company": company, "account_type": account_type, "is_group": 0},
			fields=["name", "account_name"],
		)
		result = []
		total = 0
		for a in accounts:
			bal = frappe.db.sql(
				"SELECT IFNULL(SUM(debit - credit), 0) FROM `tabGL Entry` WHERE account = %s AND is_cancelled = 0",
				(a.name,),
			)[0][0] or 0
			a["balance"] = bal
			total += flt(bal)
			result.append(a)
		result.sort(key=lambda x: x["balance"], reverse=True)
		return result, total

	bank_accounts, bank_total = account_list("Bank")
	cash_accounts, cash_total = account_list("Cash")

	return {
		"bank_accounts": bank_accounts,
		"bank_total": bank_total,
		"cash_accounts": cash_accounts,
		"cash_total": cash_total,
	}


def _get_payable(company):
	rows = frappe.db.get_all(
		"Purchase Invoice",
		filters={"company": company, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "supplier_name", "due_date", "outstanding_amount"],
		order_by="due_date asc",
	)
	today = nowdate()
	overdue = len([r for r in rows if r.due_date and str(r.due_date) < today])
	total = sum(flt(r.outstanding_amount) for r in rows)

	paid_count = frappe.db.count(
		"Purchase Invoice",
		{"company": company, "docstatus": 1, "outstanding_amount": 0},
	)

	return {
		"accounts_payable": total,
		"accounts_payable_count": len(rows),
		"overdue_payable": overdue,
		"paid_payable": paid_count,
		"all_payable": rows,
	}


def _get_receivable(company):
	rows = frappe.db.get_all(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "customer_name", "due_date", "outstanding_amount"],
		order_by="due_date asc",
	)
	today = nowdate()
	overdue = len([r for r in rows if r.due_date and str(r.due_date) < today])
	total = sum(flt(r.outstanding_amount) for r in rows)

	paid_count = frappe.db.count(
		"Sales Invoice",
		{"company": company, "docstatus": 1, "outstanding_amount": 0},
	)

	return {
		"accounts_receivable": total,
		"accounts_receivable_count": len(rows),
		"overdue_receivable": overdue,
		"paid_receivable": paid_count,
		"all_receivable": rows,
	}


def _get_bills_payable(company):
	# Kiwi's own "Expense Entry" doctype — a bills/vouchers register that sits
	# alongside (not instead of) standard Purchase Invoice / Accounts Payable.
	# status is one of '', 'Unpaid', 'Paid'; Unpaid = money still owed out.
	if not frappe.db.table_exists("Expense Entry"):
		return {"bills_payable": 0, "bills_count": 0, "bills_records": []}

	rows = frappe.db.get_all(
		"Expense Entry",
		filters={"company": company, "docstatus": 1, "status": "Unpaid"},
		fields=["name", "posting_date", "grand_total"],
		order_by="posting_date asc",
	)
	total = sum(flt(r.grand_total) for r in rows)
	return {"bills_payable": total, "bills_count": len(rows), "bills_records": rows}


def _get_other_income_pending(company):
	if not frappe.db.table_exists("Other Income"):
		return {"other_income_pending": 0, "other_income_count": 0, "other_income_records": []}

	rows = frappe.db.get_all(
		"Other Income",
		filters={"company": company, "docstatus": 1, "status": "Unpaid"},
		fields=["name", "posting_date", "grand_total"],
		order_by="posting_date asc",
	)
	total = sum(flt(r.grand_total) for r in rows)
	return {"other_income_pending": total, "other_income_count": len(rows), "other_income_records": rows}


def _get_sales_by_person(company, date_range, limit=8):
	rows = frappe.db.sql(
		"""
		SELECT
			IFNULL(si.sales_person, '') AS person,
			IFNULL(sp.sales_person_name, 'Unassigned') AS person_name,
			SUM(si.grand_total) AS total,
			COUNT(*) AS count
		FROM `tabSales Invoice` si
		LEFT JOIN `tabSales Person` sp ON sp.name = si.sales_person
		WHERE si.company = %(company)s AND si.docstatus = 1
			AND si.posting_date BETWEEN %(start)s AND %(end)s
		GROUP BY si.sales_person
		ORDER BY total DESC
		LIMIT %(limit)s
		""",
		{"company": company, "start": date_range["start"], "end": date_range["end"], "limit": limit},
		as_dict=True,
	)

	for r in rows:
		r["invoices"] = frappe.db.get_all(
			"Sales Invoice",
			filters={
				"company": company,
				"docstatus": 1,
				"sales_person": r.person or "",
				"posting_date": ["between", [date_range["start"], date_range["end"]]],
			},
			fields=["name", "customer_name", "posting_date", "grand_total"],
			order_by="posting_date desc",
			limit_page_length=50,
		)
	return rows


def _get_sales_by_territory(company, date_range, limit=8):
	rows = frappe.db.sql(
		"""
		SELECT
			IFNULL(territory, 'Unassigned') AS territory,
			SUM(grand_total) AS total,
			COUNT(*) AS count
		FROM `tabSales Invoice`
		WHERE company = %(company)s AND docstatus = 1
			AND posting_date BETWEEN %(start)s AND %(end)s
		GROUP BY territory
		ORDER BY total DESC
		LIMIT %(limit)s
		""",
		{"company": company, "start": date_range["start"], "end": date_range["end"], "limit": limit},
		as_dict=True,
	)

	for r in rows:
		r["invoices"] = frappe.db.get_all(
			"Sales Invoice",
			filters={
				"company": company,
				"docstatus": 1,
				"territory": r.territory if r.territory != "Unassigned" else ["in", ["", None]],
				"posting_date": ["between", [date_range["start"], date_range["end"]]],
			},
			fields=["name", "customer_name", "posting_date", "grand_total"],
			order_by="posting_date desc",
			limit_page_length=50,
		)
	return rows


def _get_recent_sales(company, limit=20):
	return frappe.db.get_all(
		"Sales Invoice",
		filters={"company": company, "docstatus": 1},
		fields=["name", "customer_name", "posting_date", "grand_total", "sales_person", "territory"],
		order_by="posting_date desc, creation desc",
		limit_page_length=limit,
	)


def _get_recent_purchases(company, limit=20):
	return frappe.db.get_all(
		"Purchase Invoice",
		filters={"company": company, "docstatus": 1},
		fields=["name", "supplier_name", "posting_date", "grand_total", "status"],
		order_by="posting_date desc, creation desc",
		limit_page_length=limit,
	)


def _get_overdue(doctype, company, limit=100):
	party_field = "customer_name" if doctype == "Sales Invoice" else "supplier_name"
	rows = frappe.db.get_all(
		doctype,
		filters={
			"company": company,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
			"due_date": ["<", nowdate()],
		},
		fields=["name", party_field, "due_date", "outstanding_amount"],
		order_by="due_date asc",
		limit_page_length=limit,
	)
	return rows


def _get_monthly_sales_purchase(company, months=12):
	today = getdate(nowdate())
	result = []
	for i in range(months - 1, -1, -1):
		month_date = add_months(today.replace(day=1), -i)
		start = month_date.replace(day=1)
		next_month = add_months(start, 1)
		end = add_days(next_month, -1)

		sales = frappe.db.sql(
			"""
			SELECT IFNULL(SUM(grand_total), 0) FROM `tabSales Invoice`
			WHERE company = %s AND docstatus = 1 AND posting_date BETWEEN %s AND %s
			""",
			(company, start, end),
		)[0][0] or 0

		purchase = frappe.db.sql(
			"""
			SELECT IFNULL(SUM(grand_total), 0) FROM `tabPurchase Invoice`
			WHERE company = %s AND docstatus = 1 AND posting_date BETWEEN %s AND %s
			""",
			(company, start, end),
		)[0][0] or 0

		result.append(
			{
				"month_key": start.strftime("%Y-%m"),
				"month": start.strftime("%b %y"),
				"sales": sales,
				"purchase": purchase,
			}
		)
	return result