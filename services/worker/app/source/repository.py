"""Interfaz aislada de acceso a la fuente. El generador de PDF NO conoce SQL."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    AdditionalAnswerRow,
    ObservationOptionRow,
    QuestionAnswerRow,
    ReportFilters,
    ResponseCount,
    ResponseHeader,
    ResponseImageRow,
    ResponseSignatureRow,
    SourceAsset,
    SourceCompany,
    SourceEvaluationPoint,
    SourceForm,
    TicketRow,
)


class SourceRepository(ABC):
    @abstractmethod
    def list_companies(self) -> list[SourceCompany]: ...

    @abstractmethod
    def list_forms(self, company_id: int) -> list[SourceForm]: ...

    @abstractmethod
    def list_evaluation_points(self, filters: ReportFilters) -> list[SourceEvaluationPoint]: ...

    @abstractmethod
    def count_responses(self, filters: ReportFilters) -> ResponseCount: ...

    @abstractmethod
    def list_response_ids(self, filters: ReportFilters) -> list[int]: ...

    @abstractmethod
    def get_response_headers(self, response_ids: list[int]) -> list[ResponseHeader]: ...

    @abstractmethod
    def get_response_questions(self, response_ids: list[int]) -> list[QuestionAnswerRow]: ...

    @abstractmethod
    def get_response_images(self, response_ids: list[int]) -> list[ResponseImageRow]: ...

    @abstractmethod
    def get_response_signatures(self, response_ids: list[int]) -> list[ResponseSignatureRow]: ...

    @abstractmethod
    def get_additional_answers(self, response_ids: list[int]) -> list[AdditionalAnswerRow]: ...

    @abstractmethod
    def get_observation_options(self, response_ids: list[int]) -> list[ObservationOptionRow]: ...

    @abstractmethod
    def get_tickets(self, response_ids: list[int]) -> list[TicketRow]: ...

    @abstractmethod
    def resolve_asset(self, path: str) -> SourceAsset: ...
