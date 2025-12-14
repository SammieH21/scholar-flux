# /api/workflows/pubmed_workflow.py
"""The scholar_flux.api.workflows.pubmed_workflow module defines the core steps for retrieving records from PubMed API.

These two steps integrate into a single workflow to consolidate the two-step article/abstract retrieval process into a
single step that involves the automatic execution of a workflow.

Classes:
    PubmedSearchStep:
        The first of two steps in the article/metadata response retrieval process involving ID retrieval
    PubmedFetchStep:
        The second of two steps in the article/metadata response retrieval process that resolves IDs into
        their corresponding article data and metadata.

Note that this workflow is further defined in the workflow_defaults.py module and is automatically retrieved
when creating a new SearchCoordinator when `provider_name=pubmed`. The `SearchCoordinator.search()` method
will then automatically retrieve records and metadata without the need to directly execute either step if
workflows are enabled in the SearchCoordinator.

"""
from __future__ import annotations
from pydantic import Field
from typing import Optional, List
from scholar_flux.api.models import ProcessedResponse, ErrorResponse, SearchAPIConfig
from scholar_flux.api.workflows.search_workflow import StepContext, WorkflowStep, SearchWorkflow, WorkflowResult
from scholar_flux.exceptions import NoRecordsAvailableException
from scholar_flux.api.base_coordinator import BaseCoordinator
import logging

logger = logging.getLogger(__name__)


class PubMedSearchStep(WorkflowStep):
    """Initial step of the PubMed workflow that retrieves the IDs of articles/abstracts matching the query.

    The equivalent of this step is the retrieval of a single page from the PubMed API without the use of a workflow.
    The default search/config parameter settings can be overridden to customize how the workflow step is executed.

    After retrieving the IDs of records that match the current query and page, the workflow will pass these IDs
    as context to the following `PubMedFetchStep` which will then resolve each ID into its associated actual article
    and/or abstract.

    """

    provider_name: Optional[str] = "pubmed"
    step_number: Optional[int] = 0
    description: Optional[str] = "Retrieves IDs of records matching a particular query from the PubMed database."


class PubMedFetchStep(WorkflowStep):
    """Next and final step of the PubMed workflow that uses the eFetch API to resolve article/abstract Ids.

    These ids are retrieved from the metadata of the previous step and are used as input to eFetch to retrieve their
    associated articles and/or abstracts.

    Args:
        provider_name (Optional[str]):
            Defines the `pubmed` eFetch API as the location where the next/final request will be sent.

    """

    provider_name: Optional[str] = "pubmedefetch"
    step_number: Optional[int] = 1
    description: Optional[str] = "Fetches each record/article corresponding to a PubMed ID from the PubmedSearchStep."

    def pre_transform(
        self,
        ctx: Optional[StepContext] = None,
        provider_name: Optional[str] = None,
        search_parameters: Optional[dict] = None,
        config_parameters: Optional[dict] = None,
    ) -> "PubMedFetchStep":
        """Overrides the `pre_transform` of the SearchWorkflow step to use the IDs retrieved from the previous step as
        input parameters for the PubMed eFetch API request.

        Args:
            ctx (Optional[StepContext]): Defines the inputs that are used by the current PubmedWorkflowStep to modify
                                         its function before execution.
            provider_name: Optional[str]: Provided for API compatibility. Is uses `pubmedefetch` by default.
            search_parameters: defines optional keyword arguments to pass to SearchCoordinator._search()
            config_parameters: defines optional keyword arguments that modify the step's SearchAPIConfig

        Returns:
            PubmedFetchWorkflowStep: A modified or copied version of the current pubmed workflow step

        """

        # PUBMED_FETCH takes precedence,
        provider_name = self.provider_name or provider_name

        config_parameters = (config_parameters or {}) | (
            SearchAPIConfig.from_defaults(provider_name).model_dump() if provider_name else {}
        )

        # PubMed allows near instantaneous requests between eSearch and eFetch within 10 req/s
        config_parameters["request_delay"] = 0.1

        if ctx:
            self._verify_context(ctx)
            if not ctx.result:
                err = (
                    "The `PubMedFetchStep` of the current workflow cannot continue, because the previous step did "
                    "not execute successfully."
                )
                if isinstance(ctx.result, ErrorResponse):
                    err += f" Error: {ctx.result.message}"
                else:
                    err += " The result from the previous step is `None`."
                raise RuntimeError(err)

            metadata = getattr(ctx.result, "metadata", None) or {}
            id_list = metadata.get("IdList") or {}
            ids = id_list.get("Id") or {}
            config_parameters["id"] = ",".join(ids) or "" if ids else None

            if not config_parameters["id"]:
                raise NoRecordsAvailableException("The metadata from the PubMed eSearch step returned no record IDs.")

            config_parameters["records_per_page"] = len(ids)

        search_parameters = (ctx.step.search_parameters if ctx else {}) | (search_parameters or {})

        if not search_parameters.get("page"):
            search_parameters["page"] = 1

        model = super().pre_transform(
            ctx,
            search_parameters=search_parameters,
            config_parameters={k: v for k, v in config_parameters.items() if v is not None},
        )
        pubmed_fetch_step = PubMedFetchStep(**model.model_dump())

        return pubmed_fetch_step


class PubMedSearchWorkflow(SearchWorkflow):
    """SearchWorkflow implementation for PubMed's two-step article retrieval process.

    PubMed's API requires a two-step retrieval process:

    1. **eSearch (PubMedSearchStep)**: Searches for articles matching the query and returns a list of article IDs
       along with metadata about the search (query info, pagination, result counts, etc.)
    2. **eFetch (PubMedFetchStep)**: Takes the article IDs from step 1 and retrieves the full article data
       including abstracts, authors, and other detailed information.

    This workflow coordinates both steps automatically and ensures that metadata from the initial eSearch
    is preserved in the final result, providing consumers with both the full article data and the search context.

    """

    steps: List[WorkflowStep] = Field(default_factory=lambda: [PubMedSearchStep(), PubMedFetchStep()])

    def _run(
        self,
        search_coordinator: BaseCoordinator,
        verbose: bool = True,
        **keyword_parameters,
    ) -> WorkflowResult:
        """Executes the PubMed workflow and catches edge-cases where successful eSearches return no records for a
        query."""
        try:
            return super()._run(search_coordinator, verbose, **keyword_parameters)
        except NoRecordsAvailableException as e:
            if not (self._history and self._history[0] and self._history[0].result):
                raise RuntimeError(
                    f"The PubMed Workflow failed without the retrieval of an initial eSearch response: {e}"
                )
            logger.info(f"{e} Halting the PubMed eFetch step and returning the processed eSearch response...")
            return WorkflowResult(history=self._history, result=self._history[0].result)

    def _create_workflow_result(self, result: Optional[ProcessedResponse | ErrorResponse] = None) -> WorkflowResult:
        """Updates the metadata field of the PubMed eFetch search result with eSearch metadata if available.

        This method overrides the base implementation to handle PubMed's two-step workflow where:
        1. The eSearch step (history[-2]) retrieves article IDs and returns metadata
        2. The eFetch step (history[-1]) retrieves full article data but typically has empty metadata

        By copying metadata from eSearch to the final eFetch result, we ensure that important information like
        ID lists, query details, and pagination info are preserved in the final workflow result. This maintains
        consistency with user expectations and allows downstream consumers to access complete search context.

        Args:
            result: Optional result to use instead of the last step's result from history

        Returns:
            WorkflowResult: The workflow result containing eSearch metadata and records from the initial eFetch step.

        """
        result = self._history[-1].result if result is None and self._history else result

        # Otherwise, replace the empty metadata field with that of the initial search where possible
        esearch_ctx = self._history[-2] if len(self._history) >= 2 else None
        efetch_ctx = self._history[-1] if esearch_ctx else None

        if (
            isinstance(esearch_ctx, StepContext)
            and isinstance(efetch_ctx, StepContext)
            and isinstance(esearch_ctx.step, PubMedSearchStep)
            and isinstance(efetch_ctx.step, PubMedFetchStep)
            and isinstance(result, ProcessedResponse)
            and isinstance(esearch_ctx.result, ProcessedResponse)
            and esearch_ctx.result.metadata
            and not result.metadata
        ):
            # PubMedFetchStep generally does not have metadata
            result.metadata = esearch_ctx.result.metadata

        return WorkflowResult(history=self._history, result=result)


__all__ = ["PubMedSearchStep", "PubMedFetchStep", "PubMedSearchWorkflow"]
