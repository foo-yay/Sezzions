export function normalizeUserForm(form) {
  return {
    name: form.name || "",
    email: form.email || "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function getUserColumnValue(user, columnKey) {
  if (columnKey === "status") {
    return user.is_active ? "Active" : "Inactive";
  }

  return String(user[columnKey] || "");
}
