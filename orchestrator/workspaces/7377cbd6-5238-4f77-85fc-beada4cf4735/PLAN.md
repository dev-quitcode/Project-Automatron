---
project_name: "InvoiceDashboardMVP"
stack: "Next.js 14 + Prisma + SQLite + Tailwind CSS"
root_dir: "/workspace"
global_rules:
  - "STRICT: Use App Router only; all routes live under /workspace/app."
  - "STRICT: Use Prisma with SQLite at /workspace/prisma/dev.db; never introduce external services."
  - "STRICT: Keep MVP single-user with no authentication, roles, or multi-tenant logic."
  - "STRICT: Use server actions or route handlers for writes; do not call SQLite directly from client components."
  - "STRICT: Every UI file must use Tailwind utility classes only; do not add CSS files beyond generated globals.css."
  - "STRICT: Validate all form input with Zod before database writes."
  - "STRICT: Dates must be stored as DateTime in Prisma and rendered in YYYY-MM-DD format."
  - "STRICT: Docker deploy must run the production Next.js server on port 3000."
  - "STRICT: Do not run `npx tailwindcss init`; rely on the existing scaffolded Tailwind setup already present in /workspace."
  - "STRICT: Preserve the existing scaffold in /workspace and only add or edit files required by this MVP."
---

# План Реалізації: InvoiceDashboardMVP

## Фаза 1: Перевірка scaffold та залежностей
- [ ] **Verify existing Next.js scaffold in `/workspace`**: Confirm the current app already has the required App Router and Tailwind baseline before making feature changes.
    - *Context*: Inspect `/workspace/package.json` and verify `next` is 14.x, `react` and `react-dom` are installed, and routes live under `/workspace/app`. Confirm `/workspace/app/layout.tsx`, `/workspace/app/page.tsx`, `/workspace/app/globals.css`, `/workspace/tailwind.config.ts` or equivalent scaffolded Tailwind config, and `/workspace/tsconfig.json` exist. Do not regenerate the app.

- [ ] **Install missing MVP dependencies only**: Add Prisma, Zod, date formatting, and seed tooling without altering the scaffold.
    - *Context*: In `/workspace`, run `npm install --no-audit --no-fund @prisma/client prisma zod date-fns` and `npm install -D --no-audit --no-fund tsx` only if these packages are not already present in `/workspace/package.json`. Do not install a separate SQLite driver.

- [ ] **Initialize Prisma for SQLite if not already initialized**: Create Prisma config and environment file for local database storage.
    - *Context*: If `/workspace/prisma/schema.prisma` does not exist, run `npx prisma init --datasource-provider sqlite`. Set `DATABASE_URL="file:./dev.db"` in `/workspace/.env`. Confirm Prisma files live under `/workspace/prisma`.

- [ ] **Define Prisma data model**: Add tables for customers, invoices, invoice items, and payments with relations and status fields.
    - *Context*: Edit `/workspace/prisma/schema.prisma`. Create models `Customer`, `Invoice`, `InvoiceItem`, and `Payment`. Use enum `InvoiceStatus` with `DRAFT`, `SENT`, `PAID`, `OVERDUE`. Include fields: `Customer{id, name, email?, createdAt}`, `Invoice{id, invoiceNumber, customerId, issueDate, dueDate, status, notes?, createdAt}`, `InvoiceItem{id, invoiceId, description, quantity, unitPrice}`, `Payment{id, invoiceId, amount, paymentDate, method}`. Add `@unique` on `invoiceNumber` and relation fields on both sides.

- [ ] **Run initial Prisma migration**: Create SQLite DB and generate Prisma client from the schema.
    - *Context*: Run `npx prisma migrate dev --name init` from `/workspace`. Confirm `/workspace/prisma/dev.db` exists and Prisma client is generated under `/workspace/node_modules/@prisma/client`.

## Фаза 2: Базова серверна інфраструктура
- [ ] **Create shared Prisma client module**: Add a singleton Prisma client helper for server-side imports.
    - *Context*: Create `/workspace/lib/prisma.ts`. Export `prisma` using the `globalThis` singleton pattern recommended for Next.js development. Import `PrismaClient` from `@prisma/client`.

- [ ] **Create formatting and invoice math utilities**: Add helpers for currency, date formatting, and invoice total calculations.
    - *Context*: Create `/workspace/lib/format.ts` with `formatCurrency(amount: number)` using `Intl.NumberFormat` and `formatDate(date: Date | string)` using `date-fns/format` with `yyyy-MM-dd`. Create `/workspace/lib/invoices.ts` with `calculateInvoiceTotal(items)`, `calculateAmountPaid(payments)`, and `calculateBalance(items, payments)`.

- [ ] **Create Zod validation schemas**: Define exact schemas for customer, invoice, item, and payment form payloads.
    - *Context*: Create `/workspace/lib/validators.ts`. Export `customerSchema`, `invoiceItemSchema`, `invoiceSchema`, and `paymentSchema`. `invoiceSchema` must validate `customerId`, `invoiceNumber`, `issueDate`, `dueDate`, `status`, optional `notes`, and `items` array with minimum length 1. Use `z.coerce.number()` for numeric inputs and `z.enum(["DRAFT","SENT","PAID","OVERDUE"])` for status.

- [ ] **Seed database with demo data**: Add a deterministic seed script for dashboard and list views.
    - *Context*: Create `/workspace/prisma/seed.ts` using Prisma client from `@prisma/client`. Insert 3 customers, 5 invoices, multiple invoice items, and 2 payments. Include at least 1 paid invoice, 1 unpaid invoice, and 1 overdue invoice. Update `/workspace/package.json` with `"prisma": { "seed": "tsx prisma/seed.ts" }` and add script `"db:seed": "prisma db seed"`.

## Фаза 3: Data access and dashboard logic
- [ ] **Implement dashboard query functions**: Add server-side functions to compute KPI cards and recent invoices.
    - *Context*: Create `/workspace/lib/queries/dashboard.ts`. Export `getDashboardStats()` and `getRecentInvoices(limit = 5)`. Use `prisma.invoice.findMany({ include: { customer: true, items: true, payments: true } })`. Compute `revenue` as sum of payment amounts, `unpaid` as remaining balances for invoices with `dueDate >= today`, and `overdue` as remaining balances for invoices with `dueDate < today`.

- [ ] **Implement customer and invoice query functions**: Add reusable read functions for pages.
    - *Context*: Create `/workspace/lib/queries/customers.ts` with `getCustomers()` ordered by `createdAt desc`. Create `/workspace/lib/queries/invoices.ts` with `getInvoices()` and `getInvoiceById(id: number)`, both including `customer`, `items`, and `payments`. Order invoice lists by `createdAt desc`.

## Фаза 4: Server actions for writes
- [ ] **Create customer server action**: Add a server action to create a customer from form data.
    - *Context*: Create `/workspace/app/customers/actions.ts` with `'use server'`. Export `createCustomer(formData: FormData)`. Read `name` and `email`, validate with `customerSchema`, call `prisma.customer.create`, then `revalidatePath("/")` and `revalidatePath("/customers")`.

- [ ] **Create invoice and payment server actions**: Add server actions to create invoices with nested items and record payments.
    - *Context*: Create `/workspace/app/invoices/actions.ts` with `'use server'`. Export `createInvoice(formData: FormData)` and `createPayment(formData: FormData)`. `createInvoice` must read `customerId`, `invoiceNumber`, `issueDate`, `dueDate`, `status`, `notes`, and `itemsJson`, parse `itemsJson` with `JSON.parse`, validate with `invoiceSchema`, and call `prisma.invoice.create({ data: { ..., items: { create: [...] } } })`. `createPayment` must read `invoiceId`, `amount`, `paymentDate`, and `method`, validate with `paymentSchema`, and call `prisma.payment.create`. Revalidate `/`, `/invoices`, and `/invoices/[id]` as appropriate.

## Фаза 5: Shared UI shell and components
- [ ] **Update application layout and navigation**: Add a minimal shell with header and nav links.
    - *Context*: Edit existing `/workspace/app/layout.tsx` to render app title `Invoice Dashboard` and navigation links to `/`, `/customers`, and `/invoices` using `next/link`. Preserve the scaffolded HTML structure and import of `globals.css`. Use Tailwind classes such as `max-w-6xl mx-auto p-6`.

- [ ] **Create dashboard stat card and invoice table components**: Build the reusable display components for KPIs and invoice lists.
    - *Context*: Create `/workspace/components/stat-card.tsx` exporting `StatCard({ title, value, tone })` with `tone: "default" | "warning" | "danger"`. Create `/workspace/components/invoice-table.tsx` accepting invoices including `id`, `invoiceNumber`, `customer`, `items`, and `payments`, plus optional `linkInvoiceNumber?: boolean`. Render columns: invoice number, customer, issue date, due date, status, total, paid, balance. Use helpers from `/workspace/lib/format.ts` and `/workspace/lib/invoices.ts`. When `linkInvoiceNumber` is true, wrap invoice number with `next/link` to `/invoices/[id]`.

## Фаза 6: Dashboard and customer pages
- [ ] **Build dashboard home page**: Replace the scaffolded landing page with KPI cards and recent invoices.
    - *Context*: Edit existing `/workspace/app/page.tsx` as an async server component. Call `getDashboardStats()` and `getRecentInvoices(5)`. Render 3 `StatCard` components for revenue, unpaid, and overdue, then render `InvoiceTable` below.

- [ ] **Build customers page with create form**: Show customer list and a simple add-customer form.
    - *Context*: Create `/workspace/app/customers/page.tsx` as an async server component. Use `getCustomers()` and `createCustomer`. Render a `<form action={createCustomer}>` with inputs named `name` and `email`, then render a customer table with name, email, and created date.

## Фаза 7: Invoice pages
- [ ] **Build invoices list page**: Show all invoices and link to invoice detail pages.
    - *Context*: Create `/workspace/app/invoices/page.tsx` as an async server component using `getInvoices()`. Render a `next/link` button to `/invoices/new` and reuse `InvoiceTable` with `linkInvoiceNumber={true}`.

- [ ] **Build new invoice page with dynamic item rows**: Add a client form that serializes invoice items into `itemsJson`.
    - *Context*: Create `/workspace/app/invoices/new/page.tsx` and `/workspace/components/new-invoice-form.tsx`. The page must fetch customers server-side via `getCustomers()` and pass them to the client component. In the client component, manage item row state with `description`, `quantity`, and `unitPrice`, and write `JSON.stringify(items)` into a hidden input named `itemsJson` before submit to `createInvoice`.

- [ ] **Build invoice detail page with payment form**: Show invoice header, items, totals, payments, and add-payment form.
    - *Context*: Create `/workspace/app/invoices/[id]/page.tsx`. Read `params.id`, convert to number, and call `getInvoiceById(id)`. Render invoice metadata, item rows, payment history, computed totals, and a `<form action={createPayment}>` with hidden `invoiceId` plus fields `amount`, `paymentDate`, and `method`.

## Фаза 8: Docker and MVP verification
- [ ] **Add Docker production files**: Create Dockerfile and .dockerignore for containerized deployment.
    - *Context*: Create `/workspace/Dockerfile` using `node:20-alpine`. Copy `package*.json`, run `npm ci --no-audit --no-fund`, copy source, run `npx prisma generate`, run `npm run build`, and start with `npm run start`. Create `/workspace/.dockerignore` excluding `node_modules`, `.next`, `npm-debug.log*`, and local logs.

- [ ] **Add docker-compose for local deploy path**: Define a single service that exposes the app on port 3000 with persisted SQLite storage.
    - *Context*: Create `/workspace/docker-compose.yml`. Build from `.` and expose `3000:3000`. Mount a named volume or bind mount for `/app/prisma`. Set environment variable `DATABASE_URL=file:./dev.db` so Prisma resolves SQLite inside the mounted prisma directory.

- [ ] **Add README runbook and verify MVP flow**: Document local dev, seeding, Docker commands, and run final manual checks.
    - *Context*: Create `/workspace/README.md` with exact commands: `npm install`, `npx prisma migrate dev`, `npm run db:seed`, `npm run dev`, and `docker compose up --build`. Include route list `/`, `/customers`, `/invoices`, and `/invoices/new`. Then execute `npm run db:seed` and verify dashboard cards render non-zero demo values, recent invoices load, customer creation writes to SQLite, invoice creation with at least 1 item succeeds, payment creation updates balance, and Docker starts on port 3000 without auth.