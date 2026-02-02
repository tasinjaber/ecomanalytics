import Link from "next/link";

const DASHBOARD_URL = process.env.NEXT_PUBLIC_DASHBOARD_URL || "http://localhost:8501";
const TRIAL_URL = process.env.NEXT_PUBLIC_TRIAL_URL || "#pricing";

function Icon({ name }: { name: "chart" | "users" | "box" | "cloud" | "spark" | "shield" }) {
  const common = "h-5 w-5 text-indigo-200";
  switch (name) {
    case "chart":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none">
          <path
            d="M4 19V5m0 14h16M8 15l3-4 3 3 4-6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "users":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none">
          <path
            d="M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0ZM4 20a8 8 0 0 1 16 0"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "box":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none">
          <path
            d="M21 8l-9-5-9 5 9 5 9-5Zm-18 0v10l9 5 9-5V8"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "cloud":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none">
          <path
            d="M7 18h10a4 4 0 0 0 0-8 5.5 5.5 0 0 0-10.6 1.7A3.5 3.5 0 0 0 7 18Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "spark":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2l1.6 5.3L19 9l-5.4 1.7L12 16l-1.6-5.3L5 9l5.4-1.7L12 2Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "shield":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2l8 4v6c0 5-3.4 9.4-8 10-4.6-.6-8-5-8-10V6l8-4Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
  }
}

function SectionTitle({ eyebrow, title, desc }: { eyebrow?: string; title: string; desc?: string }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      {eyebrow ? (
        <p className="text-xs font-semibold tracking-widest text-indigo-200/80 uppercase">{eyebrow}</p>
      ) : null}
      <h2 className="mt-3 text-3xl sm:text-4xl font-semibold tracking-tight text-white">{title}</h2>
      {desc ? <p className="mt-3 text-base sm:text-lg text-white/70">{desc}</p> : null}
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/80">
      {children}
    </span>
  );
}

function Card({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="group rounded-2xl border border-white/10 bg-white/[0.03] p-6 shadow-glow transition hover:border-white/20">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-500/10 ring-1 ring-indigo-500/20">
          {icon}
        </div>
        <h3 className="text-base font-semibold text-white">{title}</h3>
      </div>
      <p className="mt-3 text-sm text-white/70">{desc}</p>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className="relative">
      <div className="pointer-events-none absolute inset-0 grid-bg opacity-60" />

      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-6 py-8">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-400 to-cyan-300 shadow-glow" />
          <span className="text-sm font-semibold tracking-wide text-white">Firebolt Analytics</span>
        </div>
        <nav className="hidden items-center gap-6 text-sm text-white/70 md:flex">
          <a className="hover:text-white" href="#features">
            Features
          </a>
          <a className="hover:text-white" href="#pricing">
            Pricing
          </a>
          <a className="hover:text-white" href="#who">
            Who is this for
          </a>
        </nav>
        <div className="flex items-center gap-3">
          <Link
            href={DASHBOARD_URL}
            className="hidden rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-white hover:bg-white/10 md:inline-flex"
          >
            View Analytics Dashboard
          </Link>
          <Link
            href={TRIAL_URL}
            className="inline-flex rounded-lg bg-white px-4 py-2 text-sm font-semibold text-ink-950 hover:bg-white/90"
          >
            Start Free Trial
          </Link>
        </div>
      </header>

      {/* HERO */}
      <section className="relative mx-auto max-w-6xl px-6 pb-16 pt-10 sm:pt-14">
        <div className="mx-auto max-w-3xl text-center">
          <div className="flex flex-wrap justify-center gap-2">
            <Pill>Cloud-native</Pill>
            <Pill>Analytics-first</Pill>
            <Pill>AI-ready</Pill>
          </div>
          <h1 className="mt-6 text-4xl font-semibold tracking-tight text-white sm:text-6xl">
            Turn E-commerce Data into Actionable Insights
          </h1>
          <p className="mt-5 text-base text-white/70 sm:text-lg">
            A cloud-native analytics platform built for sales, customer, and product intelligence.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href={TRIAL_URL}
              className="inline-flex w-full justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold text-ink-950 hover:bg-white/90 sm:w-auto"
            >
              Start Free Trial
            </Link>
            <Link
              href={DASHBOARD_URL}
              className="inline-flex w-full justify-center rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-white hover:bg-white/10 sm:w-auto"
            >
              View Analytics Dashboard
            </Link>
          </div>
        </div>

        <div className="mx-auto mt-12 grid max-w-5xl grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-xs text-white/60">Sales analytics</p>
            <p className="mt-2 text-2xl font-semibold text-white">Revenue, orders, growth</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-xs text-white/60">Customer intelligence</p>
            <p className="mt-2 text-2xl font-semibold text-white">Retention, segments, LTV</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-xs text-white/60">Product performance</p>
            <p className="mt-2 text-2xl font-semibold text-white">Top items, demand, trends</p>
          </div>
        </div>
      </section>

      {/* TRUST */}
      <section className="relative mx-auto max-w-6xl px-6 py-10">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-10 text-center">
          <p className="text-sm text-white/70">Designed for data-driven teams and analytics-first organizations</p>
        </div>
      </section>

      {/* VALUE PROPS */}
      <section className="relative mx-auto max-w-6xl px-6 py-16" id="value">
        <SectionTitle
          eyebrow="Value"
          title="Built for Modern E-commerce Analytics"
          desc="Get the clarity you need for sales decisions, customer understanding, and product optimization."
        />
        <div className="mx-auto mt-10 grid max-w-4xl grid-cols-1 gap-3 sm:grid-cols-2">
          {[
            "Analyze sales trends and revenue growth",
            "Understand customer behavior and retention",
            "Identify top-performing products",
            "Explore user activity and page views",
          ].map((t) => (
            <div
              key={t}
              className="rounded-xl border border-white/10 bg-white/[0.02] px-5 py-4 text-sm text-white/80"
            >
              {t}
            </div>
          ))}
        </div>
      </section>

      {/* HOW WE DO IT */}
      <section className="relative bg-ink-900/60 py-16">
        <div className="mx-auto max-w-6xl px-6">
          <SectionTitle
            eyebrow="How we do it"
            title="We combine scalable cloud analytics, efficient data pipelines, and intelligent queries"
            desc="to help businesses make faster and better decisions."
          />
          <p className="mx-auto mt-6 max-w-3xl text-center text-sm text-white/70">
            Powered by columnar OLAP technology and Python-based analytics.
          </p>
        </div>
      </section>

      {/* FEATURES GRID */}
      <section className="relative mx-auto max-w-6xl px-6 py-16" id="features">
        <SectionTitle eyebrow="Features" title="Everything you need to go from data to decisions" />
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card
            icon={<Icon name="chart" />}
            title="Sales Analytics"
            desc="Revenue trends, order volumes, growth metrics."
          />
          <Card icon={<Icon name="users" />} title="Customer Insights" desc="Repeat customers, behavior patterns." />
          <Card
            icon={<Icon name="box" />}
            title="Product Performance"
            desc="Top products, low-performing items."
          />
          <Card icon={<Icon name="cloud" />} title="Scalable Backend" desc="Cloud-native OLAP database." />
          <Card icon={<Icon name="spark" />} title="AI-Ready Architecture" desc="Easy integration with ML models." />
          <Card icon={<Icon name="shield" />} title="Secure & Flexible" desc="Full data ownership." />
        </div>
      </section>

      {/* WHO IS THIS FOR */}
      <section className="relative mx-auto max-w-6xl px-6 py-16" id="who">
        <SectionTitle
          eyebrow="Who is this for"
          title="Designed for teams who need insight, not just data."
        />
        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { title: "Business Managers", desc: "Sales & revenue decisions" },
            { title: "Data Analysts", desc: "Deeper reporting & monitoring" },
            { title: "Marketing Teams", desc: "Customer insights & campaign targeting" },
            { title: "Product Teams", desc: "Product optimization & performance" },
          ].map((c) => (
            <div key={c.title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-6">
              <p className="text-base font-semibold text-white">{c.title}</p>
              <p className="mt-2 text-sm text-white/70">{c.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* PRICING */}
      <section className="relative mx-auto max-w-6xl px-6 py-16" id="pricing">
        <SectionTitle
          eyebrow="Pricing"
          title="Simple plans for learning and evaluation"
          desc="UI only — no payment logic."
        />
        <div className="mt-10 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {[
            {
              name: "Free Trial",
              price: "14-day access",
              bullets: ["Core analytics", "Limited data volume"],
              cta: "Try Free Trial",
              href: TRIAL_URL,
              featured: false,
            },
            {
              name: "Pro",
              price: "Full analytics",
              bullets: ["Advanced queries", "AI-ready features"],
              cta: "View Analytics Dashboard",
              href: DASHBOARD_URL,
              featured: true,
            },
            {
              name: "Enterprise",
              price: "Custom",
              bullets: ["Custom data pipelines", "Advanced ML models", "Dedicated analytics support"],
              cta: "Contact",
              href: "#",
              featured: false,
            },
          ].map((p) => (
            <div
              key={p.name}
              className={[
                "rounded-2xl border p-6 shadow-glow",
                p.featured
                  ? "border-indigo-400/30 bg-indigo-500/10"
                  : "border-white/10 bg-white/[0.03]",
              ].join(" ")}
            >
              <p className="text-sm font-semibold text-white">{p.name}</p>
              <p className="mt-2 text-2xl font-semibold text-white">{p.price}</p>
              <ul className="mt-4 space-y-2 text-sm text-white/70">
                {p.bullets.map((b) => (
                  <li key={b} className="flex gap-2">
                    <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-white/60" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={p.href}
                className={[
                  "mt-6 inline-flex w-full justify-center rounded-xl px-4 py-2 text-sm font-semibold",
                  p.featured ? "bg-white text-ink-950 hover:bg-white/90" : "bg-white/10 text-white hover:bg-white/15",
                ].join(" ")}
              >
                {p.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="relative mx-auto max-w-6xl px-6 pb-20 pt-6">
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-10 text-center shadow-glow">
          <h3 className="text-2xl font-semibold text-white">Ready to explore your data?</h3>
          <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href={TRIAL_URL}
              className="inline-flex w-full justify-center rounded-xl bg-white px-6 py-3 text-sm font-semibold text-ink-950 hover:bg-white/90 sm:w-auto"
            >
              Try Free Trial
            </Link>
            <Link
              href={DASHBOARD_URL}
              className="inline-flex w-full justify-center rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-white hover:bg-white/10 sm:w-auto"
            >
              View Live Dashboard
            </Link>
          </div>
        </div>
      </section>

      <footer className="relative border-t border-white/10 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
          <p className="text-xs text-white/60">© {new Date().getFullYear()} Firebolt Analytics</p>
          <div className="flex gap-4 text-xs text-white/60">
            <a href="#features" className="hover:text-white">
              Features
            </a>
            <a href="#pricing" className="hover:text-white">
              Pricing
            </a>
            <a href="#who" className="hover:text-white">
              Who is this for
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}




