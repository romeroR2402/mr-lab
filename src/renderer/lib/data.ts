import type { DataCategory } from "../../shared/types";

export const CATEGORY_LABEL: Record<DataCategory, string> = {
  photos: "Fotografías",
  videos: "Videos",
  documents: "Documentos",
  contacts: "Contactos",
  backups: "Respaldos locales",
  files: "Archivos",
};
export const CATEGORY_ORDER: DataCategory[] = ["photos", "videos", "documents", "contacts", "backups", "files"];

export function fmtBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  let f = n;
  for (const u of ["B", "KB", "MB", "GB", "TB"]) {
    if (f < 1024 || u === "TB") return `${f.toFixed(u === "B" ? 0 : 1)} ${u}`;
    f /= 1024;
  }
  return String(n);
}
