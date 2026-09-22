"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ApiStatus } from "@/components/api-status";
import { API_URL, ApiError } from "@/lib/api";

const links = [
  ["/", "Inference"],
  ["/experiments", "Experiments"],
  ["/multilingual", "Multilingual"],
  ["/models", "Models"],
  ["/about", "About"],
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="RouteGuard home">
          <span className="brand-mark" aria-hidden="true">
            RG
          </span>
          <span>
            <strong>RouteGuard</strong>
            <small>Routing console</small>
          </span>
        </Link>
        <nav aria-label="Primary navigation">
          {links.map(([href, label], index) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={active ? "active" : ""}
                aria-current={active ? "page" : undefined}
              >
                <span className="nav-index" aria-hidden="true">
                  0{index + 1}
                </span>
                {label}
              </Link>
            );
          })}
        </nav>
        <ApiStatus />
      </aside>
      <main id="main" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lede">{description}</p>
      </div>
      {action}
    </header>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state">
      <span aria-hidden="true">—</span>
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

/**
 * Presents a failure with advice that matches its cause: a dead API and an
 * unreachable model backend need different things from the reader.
 */
export function ErrorState({ error }: { error: unknown }) {
  const api = error instanceof ApiError ? error : null;
  const message = error instanceof Error ? error.message : String(error);

  let title = "Request failed";
  let hint = "";
  if (api?.code === "unreachable" || api?.code === "timeout") {
    title = "Cannot reach the RouteGuard API";
    hint = `Start it with: uvicorn apps.api.main:app --reload (expected at ${API_URL})`;
  } else if (api?.code === "backend_unavailable") {
    title = "The configured model backend is unavailable";
    hint =
      "The API is running, but the model it routed to could not be reached or built. " +
      "Start that model server, set the required API key, or switch to the simulated demo configuration.";
  } else if (api?.status === 404) {
    title = "Not found";
  } else if (api?.code === "validation_error" || api?.status === 400) {
    title = "The request was rejected";
  }

  return (
    <div className="error-state" role="alert">
      <strong>{title}</strong>
      <p>{message}</p>
      {hint && <p>{hint}</p>}
    </div>
  );
}
