import type { SourceReader } from "./types";
import { FixtureSource } from "./fixtureSource";
import { MysqlSource } from "./mysqlSource";
import { PostgresSource } from "./postgresSource";

let instance: SourceReader | null = null;

export function getSource(): SourceReader {
  if (instance) return instance;
  const adapter = process.env.SOURCE_ADAPTER;
  if (adapter === "mysql") {
    instance = new MysqlSource();
  } else if (adapter === "postgres") {
    instance = new PostgresSource();
  } else {
    instance = new FixtureSource();
  }
  return instance;
}

export type { SourceReader };
