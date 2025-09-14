# api/models/workflows/workflow_defaults.py

from enum import Enum
from typing import Optional
from scholar_flux.api.workflows.search_workflow import SearchWorkflow
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.workflows.pubmed_workflow import PubMedSearchStep, PubMedFetchStep


class WORKFLOW_DEFAULTS(Enum):
    """Enumerated class specifying default workflows for different providers"""

    pubmed = SearchWorkflow(
        steps=[
            PubMedSearchStep(provider_name="pubmed"),
            PubMedFetchStep(provider_name="pubmedefetch"),
        ]
    )

    @classmethod
    def get(cls, workflow_name: str) -> Optional[SearchWorkflow]:
        """
        Attempt to retrieve a SearchWorkflow instance for the given workflow name.
        Will not throw an error if the workflow does not exist.

        Args:
            workflow_name (str): Name of the default Workflow

        Returns:
            SearchWorkflow: instance configuration for the workflow if it exists
        """

        if workflow_info := getattr(cls, ProviderConfig._normalize_name(workflow_name), None):
            return workflow_info.value
        return None


__all__ = ["WORKFLOW_DEFAULTS"]
