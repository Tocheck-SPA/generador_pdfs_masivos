import type { SourceReader } from "./types";
import { FixtureSource } from "./fixtureSource";
import { PostgresSource } from "./postgresSource";

let instance: SourceReader | null = null;

export function getSource(): SourceReader {
  if (instance) return instance;
  instance =
    process.env.SOURCE_ADAPTER === "postgres"
      ? new PostgresSource()
      : new FixtureSource();
  return instance;
}

export type { SourceReader };
