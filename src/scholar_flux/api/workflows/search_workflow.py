from __future__ import annotations
from pydantic import Field, PrivateAttr, field_validator
from scholar_flux.api.models import ProviderConfig
from typing import Dict, Any, Optional, List
from typing_extensions import Self
import logging
from scholar_flux.api.workflows.models import (
    BaseStepContext,
    BaseWorkflowStep,
    BaseWorkflow,
    BaseWorkflowResult,
)

from scholar_flux.api.models import ResponseResult
from scholar_flux.api.base_coordinator import BaseCoordinator

logger = logging.getLogger(__name__)


class WorkflowStep(BaseWorkflowStep):
    """Indicates the processing metadata and execution instructions for each step in a workflow"""

    provider_name: Optional[str] = Field(default=None, description="The provider to use for this step.")
    search_parameters: Dict[str, Any] = Field(default_factory=dict, description="API search parameters for this step.")
    config_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Optional config parameters for this step."
    )
    description: Optional[str] = None

    @field_validator('provider_name', mode = 'after')
    def format_provider_name(cls, v) -> str:
        if isinstance(v, str):
            v = ProviderConfig._normalize_name(v)
        return v

    def pre_transform(
        self,
        ctx: Optional[StepContext] = None,
        provider_name: Optional[str] = None,
        search_parameters: Optional[dict] = None,
        config_parameters: Optional[dict] = None,
    ) -> Self: 

        if ctx is not None:
            self._verify_context(ctx)
            provider_name = provider_name if provider_name is not None else ctx.step.provider_name
            search_parameters = (ctx.step.search_parameters if ctx else {}) | (search_parameters or {})
            config_parameters = (ctx.step.config_parameters if ctx else {}) | (config_parameters or {})

        return self.model_copy(
            update=dict(
                provider_name=provider_name or self.provider_name,
                search_parameters=search_parameters or self.search_parameters,
                config_parameters=config_parameters or self.config_parameters,
            )
        )

    def post_transform(self, ctx: StepContext, *args, **kwargs) -> StepContext:
        self._verify_context(ctx)
        return ctx  # Identity: returns context unchanged


class StepContext(BaseStepContext):
    """Worker class that holds information on the Wokflow step, step number, and its results after execution"""

    step_number: int
    step: WorkflowStep
    result: Optional[ResponseResult] = Field(
        default=None,
        description="The response result received after the step's execution.",
    )


class WorkflowResult(BaseWorkflowResult):
    """Helper class that encapsulates the result and history in an object"""

    history: List[StepContext]
    result: Any


class SearchWorkflow(BaseWorkflow):
    steps: List[WorkflowStep]
    _history: List[StepContext] = PrivateAttr(default_factory=lambda: [])

    def _run(
        self,
        search_coordinator: BaseCoordinator,
        verbose: bool = True,
        **keyword_parameters,
    ) -> WorkflowResult:
        """
        Executes the workflow using the provided search coordinator.

        Args:
            search_coordinator (BaseCoordinator): The search coordinator to use for executing the workflow.
            verbose (bool): Indicates whether logs of each step should be printed to the console
            search_parameters (bool): Parameters that will be passed to the search method of the search_coordinator

        Returns:
            List[StepContext]: A list of StepContext objects representing the state at each step.
        """
        i = 0
        result = None
        try:
            self._history.clear()
            ctx = None
            for i, step in enumerate(self.steps):
                # Apply pre-transform if it exists
                step = step.pre_transform(
                    ctx,
                    provider_name=step.provider_name,
                    search_parameters=step.search_parameters,
                    config_parameters=step.config_parameters,
                )

                with search_coordinator.api.with_config_parameters(**step.config_parameters):
                    step_search_parameters = step.search_parameters | keyword_parameters | step.additional_kwargs
                    if verbose:
                        logger.debug(f"step {i}: Config Parameters =  {search_coordinator.api.config}")
                        logger.debug(f"step {i}: Search Parameters = {step_search_parameters}")

                    # step_search_parameters |= dict(use_workflow=None)
                    search_result = search_coordinator._search(**step_search_parameters)

                    ctx = step.post_transform(StepContext(step_number=i, step=step.model_copy(), result=search_result))

                    self._history.append(ctx)
                    result = ctx.result

        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred during processing step {i}") from e

        return WorkflowResult(history=self._history, result=result)

    def __call__(self, *args, **kwargs) -> WorkflowResult:
        return self._run(*args, **kwargs)
