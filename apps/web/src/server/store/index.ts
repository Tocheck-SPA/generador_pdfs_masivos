import type { JobStore } from "./types";
import { MemoryStore } from "./memoryStore";
import { PgStore } from "./pgStore";

let instance: JobStore | null = null;

export function getStore(): JobStore {
  if (instance) return instance;
  instance = process.env.DATABASE_URL ? new PgStore() : new MemoryStore();
  return instance;
}

export type { JobStore };
