export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-MX", { dateStyle: "short", timeStyle: "medium" });
}

export function maskId(id: string | null | undefined, mask: boolean): string {
  if (!id) return "—";
  if (!mask || id.length <= 6) return id;
  return `${id.slice(0, 3)}${"•".repeat(Math.min(8, id.length - 6))}${id.slice(-3)}`;
}
