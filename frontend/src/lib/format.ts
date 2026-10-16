export function timeAgo(iso: string): string {
  const s = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  return d < 7 ? `${d}d` : new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function eventDate(iso?: string | null, tz?: string): string {
  if (!iso) return "Date TBA";
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
    timeZone: tz || undefined,
  });
}

export function deadline(iso?: string | null): string | null {
  if (!iso) return null;
  const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return "Closed";
  if (days === 0) return "Closes today";
  if (days === 1) return "Closes tomorrow";
  return `Closes in ${days} days`;
}

const COMP: Record<string, string> = {
  unpaid: "Unpaid", paid: "Paid", revenue_share: "Rev share", negotiable: "Negotiable",
};
export function compensation(type: string, amount?: string | null, currency?: string): string {
  if (type === "paid" && amount) {
    const n = Number(amount);
    try {
      return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "INR", maximumFractionDigits: 0 }).format(n);
    } catch {
      return `${currency} ${n}`;
    }
  }
  return COMP[type] ?? type;
}

export const label = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function initials(name?: string | null): string {
  return (name ?? "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}
