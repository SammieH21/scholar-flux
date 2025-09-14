from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Any
from abc import ABC
from typing_extensions import Self
import logging

logger = logging.getLogger(__name__)


class BaseStepContext(BaseModel):
    """Base class for step contexts"""


class BaseWorkflowStep(BaseModel):
    """Base class for workflow steps"""

    additional_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional keyword parameters to specify for this step.",
    )

    def pre_transform(self, ctx: Any, *args, **kwargs) -> Self:
        return self.model_copy()

    def post_transform(self, ctx: Any, *args, **kwargs) -> Any:
        return ctx

    def _verify_context(self, ctx: Any):
        if not isinstance(ctx, BaseStepContext):
            msg = (f"Expected the `ctx` of the current workflow to be a StepContext. "
                   f"Received: {type(ctx).__name__}")
            logger.error(msg)
            raise TypeError(msg)


class BaseWorkflowResult(BaseModel):
    """Base class for returning the results from a Workflow"""


class BaseWorkflow(BaseModel, ABC):
    def _run(self, *positional_parameters, **keyword_parameters) -> BaseWorkflowResult:
        """Internal method to run the workflow steps."""
        raise NotImplementedError

    def __call__(self, *args, **kwargs) -> BaseWorkflowResult:
        """Enable instance to be called like a function."""
        return self._run(*args, **kwargs)
