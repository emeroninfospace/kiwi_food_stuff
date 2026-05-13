import json

import frappe
from frappe import _
from frappe.desk.form.load import run_onload
from frappe.utils import cint


SETTINGS_DOCTYPE = "Kiwi Food Stuff Settings"
SALES_INVOICE_DOCTYPE = "Sales Invoice"
UNRESTRICTED_USERS = {"Administrator"}
UNRESTRICTED_ROLES = {"Administrator", "Super Admin"}


def extend_bootinfo(bootinfo):
	"""Control the Delete button shown in Desk from Kiwi Food Stuff Settings."""
	user = frappe.session.user

	if is_unrestricted_user(user):
		return

	if has_settings_delete_access(user):
		bootinfo.user["can_delete"] = get_all_deletable_doctypes()
	else:
		bootinfo.user["can_delete"] = []


def has_permission(doc, ptype, user=None, **kwargs):
	user = user or frappe.session.user

	if ptype == "delete":
		return has_delete_permission(user)

	if is_credit_note_submit_check(doc, ptype):
		return has_credit_note_submit_permission(user)

	return None


def has_delete_permission(user):
	"""Deny normal delete permission unless the settings role allows it."""
	if is_unrestricted_user(user):
		return None

	if has_settings_delete_access(user):
		return None

	return False


def has_credit_note_submit_permission(user):
	"""Deny return invoice submit unless the settings role allows it."""
	if is_unrestricted_user(user):
		return None

	if has_settings_credit_note_submit_access(user):
		return None

	return False


@frappe.whitelist(methods=["DELETE", "POST"])
def delete_doc(doctype, name):
	"""Delete from Desk only when Kiwi delete settings allow the current user."""
	if is_unrestricted_user():
		from frappe.client import delete_doc as default_delete_doc

		return default_delete_doc(doctype, name)

	_validate_settings_delete_access()
	delete_doc_ignoring_role_permissions(doctype, name)


@frappe.whitelist(methods=["POST", "DELETE"])
def delete_items():
	"""Bulk delete from list view using the Kiwi delete settings."""
	if is_unrestricted_user():
		from frappe.desk.reportview import delete_items as default_delete_items

		return default_delete_items()

	_validate_settings_delete_access()

	items = sorted(json.loads(frappe.form_dict.get("items") or "[]"), reverse=True)
	doctype = frappe.form_dict.get("doctype")
	delete_bulk(doctype, items)


@frappe.whitelist(methods=["POST", "PUT"])
def savedocs(doc, action):
	"""Submit credit notes using Kiwi settings; use Frappe's default path otherwise."""
	doc_data = parse_doc(doc)

	if not is_credit_note_submit_action(doc_data, action):
		from frappe.desk.form.save import savedocs as default_savedocs

		return default_savedocs(doc, action)

	if is_unrestricted_user():
		from frappe.desk.form.save import savedocs as default_savedocs

		return default_savedocs(doc, action)

	_validate_settings_credit_note_submit_access()

	server_doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, doc_data.get("name"))
	if not cint(server_doc.is_return):
		from frappe.desk.form.save import savedocs as default_savedocs

		return default_savedocs(doc, action)

	server_doc.flags.ignore_permissions = True
	server_doc.submit()

	run_onload(server_doc)
	send_updated_docs(server_doc)
	frappe.msgprint(_("Submitted"), indicator="green", alert=True)


@frappe.whitelist()
def can_submit_credit_note(docname=None):
	"""Return custom submit access for return Sales Invoices.

	None means the user should keep Frappe's normal submit permission.
	"""
	if is_unrestricted_user():
		return None

	if not docname or str(docname).startswith("new-"):
		return has_settings_credit_note_submit_access()

	doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, docname)
	if not cint(doc.is_return):
		return None

	return has_settings_credit_note_submit_access()


def delete_bulk(doctype, items):
	undeleted_items = []

	for index, name in enumerate(items):
		try:
			delete_doc_ignoring_role_permissions(doctype, name)

			if len(items) >= 5:
				frappe.publish_realtime(
					"progress",
					{
						"progress": [index + 1, len(items)],
						"title": _("Deleting {0}").format(doctype),
						"description": name,
					},
					user=frappe.session.user,
				)

			frappe.db.commit()
		except Exception:
			undeleted_items.append(name)
			frappe.db.rollback()

	if undeleted_items and len(items) != len(undeleted_items):
		frappe.clear_messages()
		delete_bulk(doctype, undeleted_items)
	elif undeleted_items:
		frappe.msgprint(
			_("Failed to delete {0} documents: {1}").format(
				len(undeleted_items), ", ".join(undeleted_items)
			),
			realtime=True,
			title=_("Bulk Operation Failed"),
		)
	else:
		frappe.msgprint(
			_("Deleted all documents successfully"),
			realtime=True,
			title=_("Bulk Operation Successful"),
		)


def delete_doc_ignoring_role_permissions(doctype, name):
	if frappe.is_table(doctype):
		from frappe.client import delete_doc as default_delete_doc

		return default_delete_doc(doctype, name)

	frappe.delete_doc(doctype, name, ignore_missing=False, ignore_permissions=True)


def has_settings_delete_access(user=None):
	user = user or frappe.session.user

	if user in ("Guest", None):
		return False

	settings = get_settings()
	delete_role = settings.role if settings and cint(settings.delete_permission) else None

	if not delete_role:
		return False

	return delete_role in frappe.get_roles(user)


def has_settings_credit_note_submit_access(user=None):
	user = user or frappe.session.user

	if user in ("Guest", None):
		return False

	settings = get_settings()
	submit_role = (
		settings.credit_note_role if settings and cint(settings.credit_note_submit_permission) else None
	)

	if not submit_role:
		return False

	return submit_role in frappe.get_roles(user)


def is_unrestricted_user(user=None):
	user = user or frappe.session.user

	if user in UNRESTRICTED_USERS:
		return True

	if not user or user == "Guest":
		return False

	return bool(set(frappe.get_roles(user)) & UNRESTRICTED_ROLES)


def get_settings():
	try:
		return frappe.get_cached_doc(SETTINGS_DOCTYPE)
	except frappe.DoesNotExistError:
		return None


def get_all_deletable_doctypes():
	return frappe.get_all(
		"DocType",
		filters={"istable": 0, "issingle": 0},
		pluck="name",
	)


def _validate_settings_delete_access():
	if not has_settings_delete_access():
		frappe.throw(_("You are not permitted to delete documents."), frappe.PermissionError)


def _validate_settings_credit_note_submit_access():
	if not has_settings_credit_note_submit_access():
		frappe.throw(_("You are not permitted to submit credit notes."), frappe.PermissionError)


def is_credit_note_submit_check(doc, ptype):
	return (
		ptype == "submit"
		and getattr(doc, "doctype", None) == SALES_INVOICE_DOCTYPE
		and cint(doc.get("is_return"))
	)


def is_credit_note_submit_action(doc, action):
	if action != "Submit":
		return False

	doc = parse_doc(doc)
	return doc.get("doctype") == SALES_INVOICE_DOCTYPE and cint(doc.get("is_return"))


def parse_doc(doc):
	if isinstance(doc, str):
		return json.loads(doc)

	return doc


def send_updated_docs(doc):
	from frappe.desk.form.save import send_updated_docs as default_send_updated_docs

	default_send_updated_docs(doc)
