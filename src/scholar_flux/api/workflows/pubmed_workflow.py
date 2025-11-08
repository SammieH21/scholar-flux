# /api/workflows/pubmed_workflow.py
"""The scholar_flux.api.workflows.pubmed_workflow module defines the steps necessary to interact with the PubMed API and
retrieve articles/abstracts. These two steps integrate into a single workflow to consolidate the two-step retrieval
process into a single step involving the automatic execution of a workflow.

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
from typing import Optional
from scholar_flux.api.models import SearchAPIConfig, ErrorResponse
from scholar_flux.api.workflows.search_workflow import StepContext, WorkflowStep
import logging

logger = logging.getLogger(__name__)


class PubMedSearchStep(WorkflowStep):
    """Initial step of the PubMed workflow that only defines the provider name as the current option, allowing overrides
    in place of other settings. The equivalent of this step is the retrieval of a single page from the PubMed API
    without the use of a workflow.

    This step, retrieves the IDs of each record that matches the query and page. In the next step,
    the workflow takes these IDs as input and resolves them into their associated actual articles and abstracts.

    Args:
        provider_name (Optional[str]): Defines the `pubmed` eSearch API as the location where the request will be sent.

    """

    provider_name: Optional[str] = "pubmed"


class PubMedFetchStep(WorkflowStep):
    """Next and final step of the PubMed workflow that uses the eFetch API to resolve article/abstract Ids. These ids
    are retrieved from the metadata of the previous step and are used as input to eFetch to retrieve their associated
    articles and/or abstracts.

    Args:
        provider_name (Optional[str]):
            Defines the `pubmed` eFetch API as the location where the next/final request will be sent.

    """

    provider_name: Optional[str] = "pubmedefetch"

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

        config_parameters["request_delay"] = 0

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
            ids = getattr(ctx.result, "metadata", {}).get("IdList", {}).get("Id")
            config_parameters["id"] = ",".join(ids) or "" if ids else None

            if not config_parameters["id"]:
                msg = (
                    f"The metadata from the pubmed search is not in the expected format: "
                    f"{ctx.result.__dict__ if ctx.result else ctx}"
                )

                logger.error(msg)
                raise TypeError(msg)

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


__all__ = ["PubMedSearchStep", "PubMedFetchStep"]
