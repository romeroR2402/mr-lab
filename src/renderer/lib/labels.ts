import type { CheckStatus } from "../../shared/types";

export const COMM_LABEL: Record<string, string> = {
  online: "En línea",
  offline: "Fuera de línea",
  unauthorized: "Sin autorizar",
  no_permissions: "Sin permisos USB",
  recovery: "Modo recovery",
  sideload: "Modo sideload",
  bootloader: "Bootloader",
  connecting: "Conectando",
  unknown: "Desconocido",
};

export const AUTH_LABEL: Record<string, string> = {
  authorized: "Autorizado",
  unauthorized: "No autorizado",
  pending: "Pendiente de confirmar",
  not_paired: "No emparejado",
  locked: "Bloqueado por el titular",
  no_permissions: "Sin permisos del SO",
  not_applicable: "No aplica",
  unknown: "Desconocido",
};

export const CONN_LABEL: Record<string, string> = {
  usb: "USB",
  network: "Red (Wi-Fi)",
  emulator: "Emulador",
  unknown: "Desconocida",
};

export const STATUS_LABEL: Record<CheckStatus, string> = {
  ok: "Correcto",
  warning: "Advertencia",
  error: "Falla",
  info: "Información",
  unavailable: "No disponible",
};

export const CASE_STATUS: Record<string, string> = {
  open: "Abierto",
  in_progress: "En proceso",
  waiting_client: "En espera del cliente",
  completed: "Completado",
  not_recoverable: "Sin recuperación posible",
  closed: "Cerrado",
};

export const AUTH_TYPES: Record<string, string> = {
  owner: "Propietario del dispositivo",
  legal_rep: "Representante legal",
  company: "Empresa titular",
  court_order: "Orden judicial",
};

export const DEVICE_TYPES: Record<string, string> = {
  android: "Android",
  ios: "iPhone (iOS)",
  ipados: "iPad (iPadOS)",
  other: "Otro",
};

export function commTone(state: string): Tone {
  if (state === "online") return "ok";
  if (["recovery", "sideload", "bootloader", "connecting"].includes(state)) return "warning";
  return "error";
}

export function authTone(state: string): Tone {
  if (state === "authorized") return "ok";
  if (["pending", "not_applicable"].includes(state)) return "warning";
  return "error";
}

export type Tone = "ok" | "warning" | "error" | "info" | "muted" | "accent";
