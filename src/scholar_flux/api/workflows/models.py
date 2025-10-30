# /api/workflows/models.py
"""Module that implements the base classes used by scholar_flux workflows to implement the customizable, multi-step
retrieval and processing of API responses.

Classes:
    BaseStepContext: Base class for step contexts
    BaseWorkflowStep: Base class for workflow steps
    BaseWorkflowResult: Base class for returning the results from a Workflow
    BaseWorkflow: Base class for defining and fully executing a workflow

"""
from __future__ import annotations
from pydantic import BaseModel, Field
from contextlib import contextmanager
from typing import Dict, Generator, Any
from abc import ABC
from typing_extensions import Self
import logging

logger = logging.getLogger(__name__)


class BaseStepContext(BaseModel):
    """Base class for step contexts.

    Passed between workflow steps to communicate the context and history of the current workflow before and after the
    execution of each step.

    """


class BaseWorkflowStep(BaseModel):
    """Base class for workflow steps.

    Used to define the behavior and actions of each step in a workflow

    Args:
        additional_kwargs (Dict[str, Any]):
            A dictionary of optional keyword parameters used to modify the functionality of future WorkflowStep
            subclass instances.

    """

    additional_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional keyword parameters to specify for this step.",
    )

    def pre_transform(self, ctx: Any, *args, **kwargs) -> Self:
        """Defines the optional transformation to the BaseWorkflowStep that can occur before executing the workflow step
        to generate and modify its behavior.

        Args:
            ctx (Any): Defines the inputs that are used by the BaseWorkflowStep to modify its function before execution
            *args: Optional positional arguments to pass to change runtime behavior
            **kwargs: Optional keyword arguments to pass to change runtime behavior

        Returns:
            BaseWorkflowStep: A modified or copied version of the original BaseWorkflowStep

        """
        return self.model_copy()

    def _run(self, *args, **kwargs) -> Any:
        """Basic method that executes the current step of the workflow. This step is to be overridden in subclasses.

        Args:
            *args: Positional input parameters used to modify the behavior of the workflow step at runtime
            **kwargs: keyword_parameters input parameters used to modify the behavior of the workflow step at runtime

        """
        raise NotImplementedError()

    def __call__(self, *args, **kwargs) -> Any:
        """Enables the current workflow step instance to be executed like a function.

        This method calls the `BaseWorkflowStep._run()` private method under the hood to run the current step.

        Args:
            *args: Positional input parameters used to modify the behavior of the workflow step at runtime
            **kwargs: keyword_parameters input parameters used to modify the behavior of the workflow step at runtime

        """
        return self._run(*args, **kwargs)

    def post_transform(self, ctx: Any, *args, **kwargs) -> Any:
        """Defines the optional transformation to the results that are retrieved after executing the workflow step to
        modify its output.

        Args:
            ctx (Any): Defines the inputs that are used by the BaseWorkflowStep after execution to modify its output.
            *args: Optional positional arguments to pass to change its output behavior
            **args: Optional keyword arguments to pass to change its output behavior

        Returns:
            BaseWorkflowStep: A modified or copied version of the output to be returned or prepared for the next step

        """
        return ctx

    def _verify_context(self, ctx: Any) -> None:
        """Helper method for verifying the context to ensure that the correct inputs are received before step execution.

        Args:
            ctx (Any): Item to be checked and verified as a BaseWorkflowStep or subclass

        Returns:
            None: If the current context is the correct type

        Raises:
            TypeError: If the type of the context received is not a BaseStepContext or subclass

        """
        if not isinstance(ctx, BaseStepContext):
            msg = f"Expected the `ctx` of the current workflow to be a StepContext. " f"Received: {type(ctx).__name__}"
            logger.error(msg)
            raise TypeError(msg)

    @contextmanager
    def with_context(self, *args, **kwargs) -> Generator[Self, None, None]:
        """Helper method to be overridden by subclasses to customize the behavior of the workflow step.

        Base classes implementing `with_context` should ideally use a context manager to be fully compatible
        as an override for current method.

        Yields:
            Self: The current workflow step within a context

        """
        yield self


class BaseWorkflowResult(BaseModel):
    """Base class for returning the results from a Workflow."""


class BaseWorkflow(BaseModel, ABC):
    """Base class for defining and fully executing a workflow."""

    def _run(self, *positional_parameters, **keyword_parameters) -> BaseWorkflowResult:
        """Internal method that is implemented to run all workflow steps.

        Args:
            *positional_parameters: Positional input parameters used to modify the behavior of a workflow at runtime
            **keyword_parameters: keyword_parameters input parameters used to modify the behavior of a workflow at runtime

        Returns:
            BaseWorkflowResult: The final result of a workflow when its execution is successful.

        Raises:
            NotImplementedError: The actual behavior of the BaseWorkflow is to be implemented by subclasses

        """
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> BaseWorkflowResult:
        """Enables the current workflow instance to executed like a function. This method calls the `_run` private
        method under the hood to initiate the workflow.

        Args:
            *args: Positional input parameters used to modify the behavior of a workflow at runtime
            **kwargs: keyword_parameters input parameters used to modify the behavior of a workflow at runtime

        Returns:
            BaseWorkflowResult: The final result of a workflow when its execution is successful.

        """
        return self._run(*args, **kwargs)


__all__ = [
    "BaseStepContext",
    "BaseWorkflowStep",
    "BaseWorkflowResult",
    "BaseWorkflow",
]
