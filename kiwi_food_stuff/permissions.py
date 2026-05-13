import json

import frappe
from frappe import _
from frappe.utils import cint


SETTINGS_DOCTYPE = "Kiwi Food Stuff Settings"
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
	"""Deny normal delete permission unless the settings role allows it."""
	if ptype != "delete":
		return None

	user = user or frappe.session.user

	if is_unrestricted_user(user):
		return None

	if has_settings_delete_access(user):
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
