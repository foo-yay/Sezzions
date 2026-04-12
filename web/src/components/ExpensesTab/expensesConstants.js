function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function nowTimeISO() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export const EXPENSE_CATEGORIES = [
  "Advertising",
  "Car and Truck Expenses",
  "Commissions and Fees",
  "Contract Labor",
  "Depreciation",
  "Insurance (Business)",
  "Interest (Mortgage/Other)",
  "Legal and Professional Services",
  "Office Expense",
  "Rent or Lease (Vehicles/Equipment)",
  "Rent or Lease (Other Business Property)",
  "Repairs and Maintenance",
  "Supplies",
  "Taxes and Licenses",
  "Travel",
  "Meals (Deductible)",
  "Utilities",
  "Wages (Not Contract Labor)",
  "Other Expenses",
];

export const initialExpenseForm = {
  expense_date: todayISO(),
  expense_time: nowTimeISO(),
  amount: "",
  vendor: "",
  description: "",
  category: "",
  user_id: "",
  notes: "",
};

export const initialExpenseColumnFilters = {
  expense_date: [],
  category: [],
  vendor: [],
  user_name: [],
  amount: [],
  notes: [],
};

export const expenseTableColumns = [
  { key: "expense_date", label: "Date", sortable: true },
  { key: "category", label: "Category", sortable: true },
  { key: "vendor", label: "Vendor", sortable: true },
  { key: "user_name", label: "User", sortable: true },
  { key: "amount", label: "Amount", sortable: true },
  { key: "notes", label: "Notes", sortable: true },
];

export const expensesPageSize = 100;
export const expensesFallbackPageSize = 500;
