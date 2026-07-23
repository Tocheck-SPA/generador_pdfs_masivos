// Migration runner for the Neon (operational) database.
// Usage: DATABASE_URL=postgres://... node scripts/migrate.mjs
// Applies every .sql file in database/migrations in lexical order,
// tracking applied files in a schema_migrations table (idempotent).
import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const migrationsDir = path.join(__dirname, "..", "database", "migrations");
const seedsDir = path.join(__dirname, "..", "database", "seeds");

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    console.error("DATABASE_URL no está definida. Aborta.");
    process.exit(1);
  }
  let pg;
  try {
    pg = await import("pg");
  } catch {
    console.error("Falta la dependencia 'pg'. Ejecuta: npm i pg -w apps/web  (o npm i pg en la raíz)");
    process.exit(1);
  }
  const { Client } = pg.default ?? pg;
  const client = new Client({ connectionString: url });
  await client.connect();
  try {
    await client.query(
      `CREATE TABLE IF NOT EXISTS schema_migrations (
         filename TEXT PRIMARY KEY,
         applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
       )`
    );
    const withSeeds = process.argv.includes("--seed");
    const dirs = withSeeds ? [migrationsDir, seedsDir] : [migrationsDir];
    for (const dir of dirs) {
      let files = [];
      try {
        files = (await readdir(dir)).filter((f) => f.endsWith(".sql")).sort();
      } catch {
        continue;
      }
      for (const file of files) {
        const key = `${path.basename(dir)}/${file}`;
        const { rowCount } = await client.query(
          "SELECT 1 FROM schema_migrations WHERE filename = $1",
          [key]
        );
        if (rowCount > 0) {
          console.log(`= ya aplicada: ${key}`);
          continue;
        }
        const sql = await readFile(path.join(dir, file), "utf8");
        await client.query("BEGIN");
        try {
          await client.query(sql);
          await client.query("INSERT INTO schema_migrations (filename) VALUES ($1)", [key]);
          await client.query("COMMIT");
          console.log(`+ aplicada: ${key}`);
        } catch (e) {
          await client.query("ROLLBACK");
          console.error(`x error en ${key}:`, e.message);
          throw e;
        }
      }
    }
    console.log("Migraciones completas.");
  } finally {
    await client.end();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
