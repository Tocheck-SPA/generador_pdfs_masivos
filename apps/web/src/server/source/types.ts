import type {
  CountResult,
  ResponseRef,
  SourceCompany,
  SourceEvaluationPoint,
  SourceFilters,
  SourceForm,
  SourceSnapshotStatus,
} from "@/lib/types";

export interface SourceReader {
  listCompanies(): Promise<SourceCompany[]>;
  listForms(companyId: number): Promise<SourceForm[]>;
  listEvaluationPoints(
    filters: Omit<SourceFilters, "evaluationPointIds">
  ): Promise<SourceEvaluationPoint[]>;
  countResponses(filters: SourceFilters): Promise<CountResult>;
  listResponseIds(filters: SourceFilters): Promise<ResponseRef[]>;
  getSnapshotStatus(
    companyId: number,
    dateFrom: string,
    dateToExclusive: string
  ): Promise<SourceSnapshotStatus>;
}
