from __future__ import annotations
from typing import Optional
from scholar_flux.api.models import SearchAPIConfig
from scholar_flux.api.workflows.search_workflow import StepContext, WorkflowStep
import logging 
logger = logging.getLogger(__name__)


class PubMedSearchStep(WorkflowStep):
    provider_name: Optional[str] = "pubmed"


class PubMedFetchStep(WorkflowStep):
    provider_name: Optional[str] = "pubmedefetch"

    def pre_transform(
        self,
        ctx: Optional[StepContext] = None,
        provider_name: Optional[str] = None,
        search_parameters: Optional[dict] = None,
        config_parameters: Optional[dict] = None,
    ) -> "PubMedFetchStep":

        # PUBMED_FETCH takes precedence,
        provider_name = self.provider_name or provider_name

        config_parameters = (config_parameters or {}) | (
            SearchAPIConfig.from_defaults(provider_name).model_dump() if provider_name else {}
        )

        config_parameters["request_delay"] = 0

        if ctx:
            self._verify_context(ctx)
            ids = getattr(ctx.result, "metadata", {}).get("IdList", {}).get("Id")
            config_parameters["id"] = ",".join(ids) or "" if ids else None

            if not config_parameters["id"]:
                msg =(f"The metadata from the pubmed search is not in the expected format: "
                      f"{ctx.result.__dict__ if ctx.result else ctx}")

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
