# /api/workflows/search_workflow.py
"""
Implements the workflow steps, runner, and context necessary for orchestrating a workflow that retrieves and
processes API responses using a sequential methodology. These classes form the base of how a workflow is designed
and can be used directly to create a multi-step workflow or subclassed to further customize the functionality of
the workflow.

Classes:
    StepContext: Defines the step context to be transferred to the next step in a workflow to modify its function
    WorkflowStep: Contains the necessary logic and instructions for executing the current step of the SearchWorkflow
    WorkflowResult: Class that holds the history and final result of a workflow after successful execution
    SearchWorkflow: Defines and fully executes a workflow and the steps used to arrive at the final result
"""
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

from scholar_flux.api.models import ProcessedResponse, ErrorResponse
from scholar_flux.api.base_coordinator import BaseCoordinator

logger = logging.getLogger(__name__)


class WorkflowStep(BaseWorkflowStep):
    """
    Defines a specific step in a workflow and indicates its processing metadata and execution instructions before,
    during, and after the execution of the `search` procedure in this step of the `SearchWorkflow`.

        Args:
            provider_name: Optional[str]: Allows for the modification of the current provider for multifaceted searches
            **search_parameters:  defines optional keyword arguments to pass to SearchCoordinator._search()
            **config_parameters:  defines optional keyword arguments that modify the step's SearchAPIConfig
            **description (str): An optional description explaining the execution and/or purpose of the current step
    """

    provider_name: Optional[str] = Field(default=None, description="The provider to use for this step.")
    search_parameters: Dict[str, Any] = Field(default_factory=dict, description="API search parameters for this step.")
    config_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Optional config parameters for this step."
    )
    description: Optional[str] = None

    @field_validator("provider_name", mode="after")
    def format_provider_name(cls, v) -> str:
        """Helper method used to format the inputted provider name using name normalization after type checking"""
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
        """
        Overrides the `pre_transform of the base workflow step to allow for the modification of runtime search
        behavior to modify the current search and its behavior.

        Args:
            ctx (Optional[StepContext]): Defines the inputs that are used by the current SearcWorkflowStep to modify
                                         its function before execution.
            provider_name: Optional[str]: Allows for the modification of the current provider for multifaceted searches
            **search_parameters:  defines optional keyword arguments to pass to SearchCoordinator._search()
            **config_parameters:  defines optional keyword arguments that modify the step's SearchAPIConfig

        Returns:
            SearchWorkflowStep: A modified or copied version of the current search workflow step
        """

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
        """
        Helper method that validates whether the current `ctx` is a StepContext before returning the result

        Args:
            ctx (StepContext): The context to verify as a StepContext
        Returns:
            StepContext: The same step context to be passed to the next step of the current workflow

        Raises:
            TypeError: If the current `ctx` is not a StepContext
        """
        self._verify_context(ctx)
        return ctx  # Identity: returns context unchanged


class StepContext(BaseStepContext):
    """
    Helper class that holds information on the Workflow step, step number, and its results after execution.
    This StepContext is passed before and after the execution of a SearchWorkflowStep to dynamically aid in
    the modification of the functioning of each step at runtime.

    Args:
        step_number (int): Indicate the order in which the step is executed for a particular step context
        step (WorkflowStep): Defines the instructions for response retrieval, processing, and pre/post transforms for
                             each step of a workflow. This value defines both the step taken to arrive at the result.
        result (Optional[ProcessedResponse | ErrorResponse]): Indicates the result that was retrieved and processed in
                                                              the current step
    """

    step_number: int
    step: WorkflowStep
    result: Optional[ProcessedResponse | ErrorResponse] = Field(
        default=None,
        description="The response result received after the step's execution.",
    )


class WorkflowResult(BaseWorkflowResult):
    """
    Helper class that encapsulates the result and history in an object

    Args:
        history (List[StepContext]): Defines the context of steps and results taken to arrive at a particular result
        result (Any): The final result after the execution of a workflow
    """

    history: List[StepContext]
    result: Any


class SearchWorkflow(BaseWorkflow):
    """
    Front-end SearchWorkflow class that is further refined for particular providers base on subclassing.
    This class defines the full workflow used to arrive at a result and records the history of each search
    at any particular step.

    Args:
        steps (List[WorkflowStep]): Defines the steps to be iteratively executed to arrive at a result.
        history (List[StepContext]): Defines the full context of all steps taken and results recorded to arrive at the
                                     final result on the completion of an executed workflow.
    """

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
        """
        Similarly enables the current workflow instance to executed like a function. This method calls the `_run`
        private method under the hood to initiate the workflow.

        Args:
            *args: Positional input parameters used to modify the behavior of a workflow at runtime
            *kwargs: keyword_parameters input parameters used to modify the behavior of a workflow at runtime

        Returns:
            WorkflowResult: The final result of a SearchWorkflow when its execution and retrieval is successful.
        """
        return self._run(*args, **kwargs)


__all__ = [
    "StepContext",
    "WorkflowStep",
    "WorkflowResult",
    "SearchWorkflow",
]
