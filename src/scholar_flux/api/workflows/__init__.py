# api/workflows
"""The scholar_flux.api.workflows module contains the core logic for integrating workflows into the SearchCoordinator,
and, in doing so, allows for customizable, integrated, workflows that allow extraneous steps to occur throughout the
process.

Examples include:
    1) Searching for articles of a particular type in customized year ranges
    2) Performing several searches and aggregating the results into one Processed Response
    3) Using the parameters of a previous search to guide how a subsequent search is performed

Modules:
    models: Contains the core components needed to build a workflow. This includes:
        1) BaseWorkflow - the overarching runnable that orchestrates each step of a workflow integrating context
        2) BaseWorkflowStep - the core component that corresponds to a single search or action
        3) BaseStepContext - Passed to future steps to allow integration of the results of previous steps into
                             the workflow logic at the current step in a workflow
        4) BaseWorkflowResult - The result that is returned at the completion of a workflow. This step
                                contains the results from all steps (`history`) as well as the result from the
                                final step (`result`)
    search_workflow: Contains the default classes from which workflows are further subclassed and instantiated.
                     These classes, by default, are designed to perform in a similar manner as a regular call to
                     SearchCoordinator.search(...). This module includes:
        1) SearchWorkflow - The first concrete workflow. Allows each call to SearchCoordinator._search to occur,
                            step by step, in a custom workflow
        2) WorkflowStep - Contains the core logic indicate what providers and default parameter overrides will be
                          used to perform the next search
        3) StepContext - Basic wrapper holding the results of each step as well as its step number and WorkflowStep
        4) WorkflowResult - Will contain the history of each of the steps in the SearchWorkflow. Also stores the
                            result of each search in the `result` attribute
    pubmed_workflow: Contains the necessary steps for interacting with the Pubmed API. Note that this API generally
                     requires a 2-step workflow. The first step retrieves the IDs of articles given a query (eSearch).
                     The second step uses these IDs to fetch actual abstracts/records and supporting information.

                     To account for this, the PubMedSearchStep and PubmedFetchStep are each created two encompass
                     these two steps in a reusable format and is later defined in a pre-created workflow for later use
    WORKFLOW_DEFAULTS: Currently contains the pubmed workflow for retrieving data from articles from PubMed.
                       This implementation will also contain future workflows that allow searches via
                       SearchCoordinator.search to be further customized.

    Example use:

       >>> from scholar_flux.api import SearchCoordinator, SearchAPI
       >>> from scholar_flux.sessions import CachedSessionManager
       >>> from scholar_flux.api.workflows import WORKFLOW_DEFAULTS, SearchWorkflow
       # PubMed requires an API key - Is read automatically from the user's environment variable list if available
       >>> api = SearchAPI.from_defaults(query = 'Machine Learning in Hospitals', provider_name='pubmed', session = CachedSessionManager(user_agent='sam_research', backend='redis').configure_session())
        # THE WORKFLOW is read automatically from the WORKFLOW defaults
       >>> pubmed_search = SearchCoordinator(api)
       >>> isinstance(pubmed_search, SearchWorkflow)
       # OUTPUT: True
       >>> pubmed_workflow = WORKFLOW_DEFAULTS.get('pubmed')
       >>> pubmed_search_with_workflow = SearchCoordinator(api, workflow = pubmed_workflow)
       # Each comparison is identical given how the workflows are read
       >>> assert pubmed_search.workflow == pubmed_workflow == pubmed_search_with_workflow.workflow
       # assuming that an API key is available:
       >>> response = pubmed_search.search(page = 1, use_workflow = True) # The workflow is used automatically

"""
from scholar_flux.api.workflows.models import (
    BaseStepContext,
    BaseWorkflowStep,
    BaseWorkflowResult,
    BaseWorkflow,
)
from scholar_flux.api.workflows.search_workflow import (
    StepContext,
    WorkflowStep,
    WorkflowResult,
    SearchWorkflow,
)
from scholar_flux.api.workflows.pubmed_workflow import PubMedSearchStep, PubMedFetchStep, PubMedSearchWorkflow
from scholar_flux.api.workflows.workflow_defaults import WORKFLOW_DEFAULTS

__all__ = [
    "BaseStepContext",
    "BaseWorkflowStep",
    "BaseWorkflow",
    "BaseWorkflowResult",
    "StepContext",
    "WorkflowStep",
    "WorkflowResult",
    "SearchWorkflow",
    "PubMedSearchStep",
    "PubMedFetchStep",
    "PubMedSearchWorkflow",
    "WORKFLOW_DEFAULTS",
]
