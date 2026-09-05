# 00 — Idea Library: pick your hero document (9 options)

Your team picks ONE document type and lives with it all day: you generate it,
corrupt it, parse it, and grade it. The pipeline architecture never changes;
only three files do (see the swap map in the root README).

The **GST invoice is the pre-built reference** — pick it if you want zero
template work and maximum time on parsing and eval. Every other idea means
building your own template + generator + validators from the invoice code, so
budget M2 time accordingly. Effort: S = small tweak of the invoice code,
M = real template and rules work.

Convention all specs follow: name date fields with `date` in the key
(`date`, `due_date`, `order_date`) — the eval harness normalizes them by name.

---

## 1 · GST Invoice — reference build, effort: done
The repo as shipped. Fields, chaos, validators, checkpoint dataset: all working.
Catchable tags: `total_digit_swap, cgst_wrong_math, gstin_missing`.

## 2 · Salary Payslip — effort: S/M
- **Fields:** employer, employee, emp_code, pan, month, earnings (basic, hra, other_allowance), deductions (pf, professional_tax, tds), gross, total_deductions, net_pay
- **Format rules:** PAN = `AAAAA9999A`; emp_code pattern of your choice, stated in your spec
- **Math rules:** gross = Σ earnings; total_deductions = Σ deductions; net_pay = gross − total_deductions; pf = 12% of basic (tolerance ₹1)
- **Chaos ideas:** net that ignores one deduction; PF computed on gross instead of basic; PAN with a digit in a letter slot; transposed digits in net_pay; professional tax for the wrong state slab
- **Catchable tags** (pass to `eval.py --catchable`): `net_pay_mismatch,pan_malformed,pf_on_gross`

## 3 · Retail / Restaurant Receipt — effort: S
- **Fields:** merchant, gstin, receipt_no, date, items (name, qty, price, amount), service_charge, cgst, sgst, round_off, total, upi_ref
- **Format rules:** GSTIN checksum; UPI ref = 12 digits
- **Math rules:** service_charge = stated % of item subtotal; total = subtotal + service charge + taxes + round_off; |round_off| < 1
- **Chaos ideas:** round_off applied but total not rounded; service charge % printed ≠ % applied; UPI ref 11 digits; item price/amount swapped
- **Catchable tags** (pass to `eval.py --catchable`): `service_charge_wrong,roundoff_wrong,total_mismatch`

## 4 · E-Way Bill — effort: M
- **Fields:** ewb_no, generated_date, valid_until_date, consignor_gstin, consignee_gstin, vehicle_no, distance_km, doc_value
- **Format rules:** EWB = 12 digits; vehicle matches `AA00AA0000` (e.g. KA01AB1234); both GSTINs pass checksum
- **Math rules:** validity days = ceil(distance_km / 200); valid_until = generated + validity days
- **Chaos ideas:** validity date off by a day; vehicle number with letter/digit swapped; consignor GSTIN == consignee GSTIN; distance 0
- **Catchable tags** (pass to `eval.py --catchable`): `validity_date_wrong,distance_missing,gstin_missing`

## 5 · Bank Cheque — effort: M
- **Fields:** payee, date, amount_figures, amount_words, account_no, ifsc, micr, cheque_no
- **Format rules:** IFSC = `AAAA0` + 6 alphanumerics; MICR = 9 digits; cheque_no = 6 digits
- **Math rules:** amount_words must equal amount_figures (write the number-to-Indian-words converter; this cross-check is the whole point of picking this card)
- **Chaos ideas:** words say "lakh" figures say thousand; stale date (> 3 months old); missing payee; figures with transposed digits
- **Note:** hardest extraction of the library — handwriting-style fonts optional, words-vs-figures validation mandatory
- **Catchable tags** (pass to `eval.py --catchable`): `words_figures_mismatch,ifsc_malformed,payee_missing`

## 6 · Fixed Deposit Receipt — effort: S/M
- **Fields:** bank, depositor, pan, fd_no, principal, rate_pct, open_date, maturity_date, tenure_months, maturity_amount
- **Format rules:** PAN = `AAAAA9999A`
- **Math rules:** maturity_amount = principal × (1 + rate/400)^(4 × tenure_months/12), tolerance ₹1; maturity_date = open_date + tenure
- **Chaos ideas:** maturity computed with simple interest; tenure printed 12, dates say 15 months; PAN with digit in letter slot
- **Catchable tags** (pass to `eval.py --catchable`): `maturity_math_wrong,rate_missing,tenure_mismatch`

## 7 · Purchase Order — effort: S
- **Fields:** buyer, supplier_gstin, po_no, order_date, delivery_date, items (description, qty, rate, amount), subtotal, total
- **Format rules:** GSTIN checksum; PO no pattern of your choice, stated in your spec
- **Math rules:** delivery_date ≥ order_date; subtotal = Σ items; per-line qty × rate = amount
- **Chaos ideas:** delivery before order; duplicate PO numbers across the batch; qty 0 with nonzero amount
- **Catchable tags** (pass to `eval.py --catchable`): `delivery_before_order,total_mismatch,po_no_missing`

## 8 · Electricity Bill — effort: M
- **Fields:** consumer_no, billing_month, units, slab_lines (slab, units, rate, amount), fixed_charge, arrears, bill_date, due_date, total
- **Format rules:** consumer_no = 10 digits
- **Math rules:** slab amounts = units × slab rate with correct slab split; due_date = bill_date + 15 days; total = slabs + fixed + arrears
- **Chaos ideas:** units split across slabs wrongly; due date = bill date; arrears added twice; total off by exactly the fixed charge
- **Catchable tags** (pass to `eval.py --catchable`): `slab_math_wrong,units_mismatch,due_date_wrong`

## 9 · Student Marksheet — effort: S
- **Fields:** student, roll_no, exam, subjects (name, max_marks, obtained), total_max, total_obtained, percentage, grade
- **Format rules:** roll_no pattern of your choice; obtained ≤ max per subject
- **Math rules:** totals = sums; percentage = obtained/max × 100 to 2dp; grade consistent with your stated band table
- **Chaos ideas:** percentage from wrong total; obtained > max; grade one band off; a subject line in a regional script

---

Chose a non-invoice card? Copy `SPEC_TEMPLATE.md`, fill it in 10 minutes, and
pin it next to your keyboard — your generator, validators, and `--catchable`
list all come from it. If your spec and your code disagree, your eval is
grading a document that doesn't exist.
- **Catchable tags** (pass to `eval.py --catchable`): `total_not_sum,percentage_wrong,grade_band_wrong`

