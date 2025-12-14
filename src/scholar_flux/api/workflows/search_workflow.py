# /api/workflows/search_workflow.py
"""Implements the workflow steps, runner, and context necessary for orchestrating a workflow that retrieves and
processes API responses using a sequential methodology. These classes form the base of how a workflow is designed and
can be used directly to create a multi-step workflow or subclassed to further customize the functionality of the
workflow.

Classes:
    StepContext: Defines the step context to be transferred to the next step in a workflow to modify its function
    WorkflowStep: Contains the necessary logic and instructions for executing the current step of the SearchWorkflow
    WorkflowResult: Class that holds the history and final result of a workflow after successful execution
    SearchWorkflow: Defines and fully executes a workflow and the steps used to arrive at the final result

"""
from __future__ import annotations
from pydantic import Field, PrivateAttr, field_validator
from scholar_flux.api.models import ProviderConfig
from typing import Dict, Any, Optional, List, Generator
from contextlib import contextmanager
from typing_extensions import Self
import logging
from scholar_flux.api.workflows.models import (
    BaseStepContext,
    BaseWorkflowStep,
    BaseWorkflow,
    BaseWorkflowResult,
)

from scholar_flux.api.models import ProcessedResponse, ErrorResponse
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.base_coordinator import BaseCoordinator
from scholar_flux.exceptions import NoRecordsAvailableException

logger = logging.getLogger(__name__)


class WorkflowStep(BaseWorkflowStep):
    """Defines a specific step in a workflow and indicates its processing metadata and execution instructions before,
    during, and after the execution of the `search` procedure in this step of the `SearchWorkflow`.

    Args:
        provider_name: Optional[str]: The provider to use for this step. Allows for the modification of the current
                                      provider for multifaceted searches.
        search_parameters: API search parameters for this step. Defines optional keyword arguments to pass to
                           `SearchCoordinator._search()`
        config_parameters: Optional config parameters for this step. Defines optional keyword arguments that modify
                           the step's SearchAPIConfig.
        description (str): An optional description explaining the execution and/or purpose of the current step

    """

    provider_name: Optional[str] = Field(default=None, description="The provider to use for this step.")
    search_parameters: Dict[str, Any] = Field(default_factory=dict, description="API search parameters for this step.")
    config_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Optional config parameters for this step."
    )
    description: Optional[str] = None

    @field_validator("provider_name", mode="after")
    def format_provider_name(cls, v) -> str:
        """Helper method used to format the inputted provider name using name normalization after type checking."""
        if isinstance(v, str):
            v = ProviderConfig._normalize_name(v)

            if v not in provider_registry:
                logger.warning(
                    f"The provider, '{v}' doesn't exist in the registry. The default settings for the "
                    "SearchCoordinator will not be applied when applying this step in a workflow."
                )
        return v

    def _get_provider_config_defaults(self, provider_name: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Extracts the default parameters for a specific provider from the provider registry if available."""

        provider_name = provider_name or self.provider_name or ""

        if provider_config := provider_registry.get(provider_name):
            return provider_config.search_config_defaults()
        elif provider_name:
            logger.warning(f"Couldn't find a configuration for the provider, '{provider_name}'.")

        return None

    def pre_transform(
        self,
        ctx: Optional[StepContext] = None,
        provider_name: Optional[str] = None,
        search_parameters: Optional[dict] = None,
        config_parameters: Optional[dict] = None,
    ) -> Self:
        """Overrides the `pre_transform` of the base workflow step to allow for the modification of runtime search
        behavior to modify the current search and its behavior.

        This method will use the current configuration of the `WorkflowStep` by default (`provider_name`,
        `config_parameters`, `search_parameters`).

        If the `provider_name` is not specified, the context from the preceding workflow step, if available, is used to
        transform the current `WorkflowStep` before runtime.

        Args:
            ctx (Optional[StepContext]): Defines the inputs that are used by the current SearchWorkflowStep to modify
                                         its function before execution.
            provider_name: Optional[str]: Allows for the modification of the current provider for multifaceted searches
            **search_parameters:  defines optional keyword arguments to pass to SearchCoordinator._search()
            **config_parameters:  defines optional keyword arguments that modify the step's SearchAPIConfig

        Returns:
            SearchWorkflowStep: A modified or copied version of the current search workflow step

        """

        if ctx is not None:
            self._verify_context(ctx)

            if not provider_name:
                provider_name = self.provider_name if self.provider_name is not None else ctx.step.provider_name

            if provider_name and ctx.step.provider_name != provider_name:
                config_parameters = (
                    (self._get_provider_config_defaults(provider_name) or {})
                    | self.config_parameters
                    | (config_parameters or {})
                )
                search_parameters = self.search_parameters | (search_parameters or {})

            else:
                config_parameters = (
                    (ctx.step.config_parameters if ctx else {}) | self.config_parameters | (config_parameters or {})
                )
                search_parameters = (
                    (ctx.step.search_parameters if ctx else {}) | self.search_parameters | (search_parameters or {})
                )

        return self.model_copy(
            update=dict(
                provider_name=provider_name, search_parameters=search_parameters, config_parameters=config_parameters
            )
        )

    def _run(
        self,
        step_number: int,
        search_coordinator: BaseCoordinator,
        ctx: Optional[StepContext] = None,
        verbose: Optional[bool] = True,
        **keyword_parameters,
    ) -> StepContext:
        """Executes the current workflow step using the provided search coordinator and the context from past searches.

        Args:
            step_number (int): Indicates the order in which the current step is ran in a workflow
            search_coordinator (BaseCoordinator): The search coordinator to use for executing the workflow.
            ctx (Optional[StepContext]): The context from a previous step, if available.
            verbose (bool): Indicates whether logs of each step should be printed to the console.
            **keyword_parameters (bool): keyword mappings that are passed directly to `search_coordinator.search()`.

        """
        i = ctx.step_number if ctx is not None else step_number
        step_search_parameters = self.search_parameters | keyword_parameters | self.additional_kwargs
        if verbose:
            logger.debug(f"step {i}: Config Parameters =  {search_coordinator.api.config}")
            logger.debug(f"step {i}: Search Parameters = {step_search_parameters}")

        search_result = search_coordinator._search(**step_search_parameters)
        step_ctx = StepContext(step_number=i, step=self.model_copy(), result=search_result)
        return step_ctx

    @contextmanager
    def with_context(self, search_coordinator: BaseCoordinator) -> Generator[Self, None, None]:
        """Helper method that briefly changes the configuration of the search_coordinator with the step configuration.

        This method uses a context manager in addition to the `with_config_parameters` method of the SearchAPI to
        modify the search location, default api-specific parameters used, and other possible options that have an
        effect on SearchAPIConfig. This step is associated with the configuration for greater flexibility in overriding
        behavior.

        Args:
            search_coordinator (BaseCoordinator): The search coordinator to modify the configuration for

        Yields:
            WorkflowStep: The current step with the modification applied

        """
        with search_coordinator.api.with_config_parameters(**self.config_parameters):
            yield self

    def post_transform(self, ctx: StepContext, *args, **kwargs) -> StepContext:
        """Helper method that validates whether the current `ctx` is a StepContext before returning the result.

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
    """Helper class that holds information on the Workflow step, step number, and its results after execution. This
    StepContext is passed before and after the execution of a SearchWorkflowStep to dynamically aid in the modification
    of the functioning of each step at runtime.

    Args:
        step_number (int): Indicates the order in which the step is executed for a particular step context
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
    """Helper class that encapsulates the result and history in an object.

    Args:
        history (List[StepContext]): Defines the context of steps taken to arrive at the final result.
        result (Any): The final result after the execution of a workflow

    """

    history: List[StepContext]
    result: Any


class SearchWorkflow(BaseWorkflow):
    """Front-end SearchWorkflow class that is further refined for particular providers base on subclassing. This class
    defines the full workflow used to arrive at a result and records the history of each search at any particular step.

    Args:
        steps (List[WorkflowStep]): Defines the steps to be iteratively executed to arrive at a result.
        stop_on_error (bool): Defines whether to stop workflow step iteration when an error occurs in a preceding step.
                              If True, the workflow halts and the ErrorResponse from the previous step is returned.
        history (List[StepContext]): Defines the full context of all steps taken and results recorded to arrive at the
                                     final result on the completion of an executed workflow.

    """

    steps: List[WorkflowStep]
    stop_on_error: bool = True
    _history: List[StepContext] = PrivateAttr(default_factory=lambda: [])

    def _run(
        self,
        search_coordinator: BaseCoordinator,
        verbose: bool = True,
        **keyword_parameters,
    ) -> WorkflowResult:
        """Executes the workflow using the provided search coordinator.

        Args:
            search_coordinator (BaseCoordinator): The search coordinator to use for executing the workflow.
            verbose (bool): Indicates whether logs of each step should be printed to the console
            search_parameters (bool): Parameters that will be passed to the search method of the search_coordinator

        Returns:
            List[StepContext]: A list of StepContext objects representing the state at each step.

        Raises:
            RuntimeError: If an unexpected error occurs during a step
            NoRecordsAvailableException:
                When a successful response contains no records associated with a query and should halt further
                processing. This exception can be handled directly by subclasses to further tailor the logic of
                the workflow to an API.

        """
        i = 0
        result = None
        try:
            self._history.clear()
            ctx = None
            for i, workflow_step in enumerate(self.steps):
                # Apply pre-transform if it exists
                workflow_step = workflow_step.pre_transform(
                    ctx,
                    provider_name=workflow_step.provider_name,
                    search_parameters=workflow_step.search_parameters,
                    config_parameters=workflow_step.config_parameters,
                )

                # apply the execution workflow_step while temporarily changing config parameters
                with workflow_step.with_context(search_coordinator):

                    # performs the search using the configuration
                    preprocessed_ctx = workflow_step(
                        step_number=i,
                        search_coordinator=search_coordinator,
                        ctx=ctx,
                        verbose=verbose,
                        **keyword_parameters,
                    )

                    # apply post processing workflow_steps
                    ctx = workflow_step.post_transform(preprocessed_ctx)

                self._history.append(ctx)

                result = ctx.result

                if not ctx.result and self.stop_on_error:
                    logger.warning(f"Halting the current workflow and returning the result from step {i}...")
                    break

        except NoRecordsAvailableException:
            raise
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred during processing step {i}: {e}") from e

        return self._create_workflow_result(result)

    def _create_workflow_result(self, result: Optional[ProcessedResponse | ErrorResponse] = None) -> WorkflowResult:
        """Prepares the final workflow result from the workflow history."""
        result = self._history[-1].result if result is None and self._history else result
        return WorkflowResult(history=self._history, result=result)

    def __call__(self, *args, **kwargs) -> WorkflowResult:
        """Similarly enables the current workflow instance to executed like a function. This method calls the `_run`
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
