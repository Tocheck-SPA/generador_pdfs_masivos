import type { SourceReader } from "./types";

const MESSAGE =
  "PostgresSource no implementado en el web app; el worker usa la fuente real";

/**
 * Stub. The web app only needs fixtures for MVP counts. The real source
 * database is owned by the Python worker.
 */
export class PostgresSource implements SourceReader {
  listCompanies(): never {
    throw new Error(MESSAGE);
  }
  listForms(): never {
    throw new Error(MESSAGE);
  }
  listEvaluationPoints(): never {
    throw new Error(MESSAGE);
  }
  countResponses(): never {
    throw new Error(MESSAGE);
  }
  listResponseIds(): never {
    throw new Error(MESSAGE);
  }
}
