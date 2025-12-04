Workflows
=========

This tutorial explains how ScholarFlux workflows enable multi-step data retrieval from academic APIs, with real examples using PubMed, Crossref, and OpenAlex.

.. admonition:: Reading Guide
   :class: tip

   **New to ScholarFlux?** Complete :doc:`getting_started` first, then return here.
   
   **Quick start (5 min)**: Read "Overview" and "Built-in Workflows" to understand PubMed's automatic workflow, then start querying.
   
   **Building custom workflows (20 min)**: Read through "Creating Custom Workflows" and one real-world example to learn the workflow pattern.
   
   **Advanced customization (15 min)**: Jump to "Best Practices" or "Advanced Customization" for extension points and production patterns.
   
   **Debugging workflow issues**: See "Workflow Error Handling" and "Troubleshooting" sections.
   
   **Production deployment**: After reading, see :doc:`caching_strategies` for workflow caching patterns and :doc:`production_deployment` for deployment configuration.

.. contents:: Table of Contents
   :local:
   :depth: 2

Prerequisites
-------------

- Complete :doc:`getting_started` for basic search patterns
- Understand :doc:`response_handling_patterns` for workflow error handling
- (Optional) Familiarity with :doc:`multi_provider_search` for concurrent workflows

Overview
--------

What are Workflows?
~~~~~~~~~~~~~~~~~~~

Some academic APIs require multiple requests to retrieve complete article data. For example:

- **PubMed**: Search for IDs → Fetch full records using those IDs
- **Crossref**: Search for articles → Fetch detailed metadata using DOIs
- **OpenAlex**: Search for seed papers → Fetch citation networks

ScholarFlux workflows automate these multi-step processes through the :class:`~scholar_flux.api.workflows.SearchWorkflow` class.

.. note::
   **Most users never interact with workflows directly.** PubMed's workflow is configured automatically—just use ``SearchCoordinator(provider_name="pubmed")`` and everything works transparently. Custom workflows are only needed for specialized multi-step retrieval patterns.

Why Use Workflows?
~~~~~~~~~~~~~~~~~~

**Without workflows:**

.. code-block:: python

   # Manual two-step process (tedious and error-prone)
   # Step 1: Search PubMed for IDs
   search_response = requests.get(
       'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
       params={'term': 'neuroscience', 'retmax': 20}
   )
   ids = parse_xml(search_response)['IdList']['Id']
   
   # Step 2: Fetch records using IDs
   fetch_response = requests.get(
       'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
       params={'id': ','.join(ids), 'retmode': 'xml'}
   )
   records = parse_xml(fetch_response)

**With workflows:**

.. code-block:: python

   # Automatic two-step process
   coordinator = SearchCoordinator(
       query="neuroscience",
       provider_name="pubmed"  # Workflow configured automatically
   )
   result = coordinator.search(page=1)
   # Returns complete records with abstracts and metadata

Workflow Architecture
---------------------

Understanding the Data Flow
~~~~~~~~~~~~~~~~~~~~~~~~~~~

ScholarFlux workflows coordinate multiple API calls with intelligent data passing between steps:

.. code-block:: text

   SearchCoordinator.search_page(page=1)
   ├─> Creates SearchResult container (holds query, provider, page)
   │
   └─> Calls SearchCoordinator.search()
       ├─> Workflow enabled? → Execute workflow
       │   │
       │   ├─> Step 1: WorkflowStep._run()
       │   │   ├─> Calls coordinator._search() internally
       │   │   ├─> Returns ProcessedResponse (or ErrorResponse)
       │   │   ├─> Cached by DataCacheManager ✓
       │   │   └─> Wrapped in StepContext
       │   │
       │   ├─> Step 2: WorkflowStep.pre_transform(ctx=Step1Context)
       │   │   ├─> Extracts data from Step 1's result
       │   │   ├─> Configures parameters for Step 2
       │   │   └─> Returns modified WorkflowStep
       │   │
       │   ├─> Step 2: WorkflowStep._run()
       │   │   ├─> Calls coordinator._search() with Step 1's data
       │   │   ├─> Returns ProcessedResponse (or ErrorResponse)
       │   │   ├─> Cached by DataCacheManager ✓
       │   │   └─> Wrapped in StepContext
       │   │
       │   └─> Returns final ProcessedResponse
       │
       └─> No workflow? → Call coordinator._search() directly

**Key Points:**

- **Each step is cached independently** by DataCacheManager
- **Errors at any step return ErrorResponse** with details
- **StepContext passes results between steps** without modifying coordinator
- **SearchResult (from search_page) adds query/provider/page context** for user convenience

Components Explained
~~~~~~~~~~~~~~~~~~~~

**WorkflowStep**: Defines behavior for a single step

.. code-block:: python

   class WorkflowStep(BaseModel):
       provider_name: str = "my_provider"
       search_parameters: dict = {}   # kwargs for _search()
       config_parameters: dict = {}   # overrides for SearchAPIConfig
       
       def pre_transform(self, ctx: StepContext) -> "WorkflowStep":
           """Modify step based on previous results (optional)"""
           
       def _run(self, step_number: int, coordinator, ctx: StepContext) -> StepContext:
           """Execute the step (required)"""
           
       def post_transform(self, ctx: StepContext) -> StepContext:
           """Modify results after execution (optional)"""

**StepContext**: Carries results between steps

.. code-block:: python

   @dataclass
   class StepContext:
       step_number: int              # Which step this is (0, 1, 2...)
       step: WorkflowStep            # The WorkflowStep instance
       result: ProcessedResponse     # The API response (or ErrorResponse)

**SearchWorkflow**: Orchestrates all steps

.. code-block:: python

   class SearchWorkflow(BaseModel):
       steps: List[WorkflowStep]     # Steps to execute in order
       stop_on_error: bool = True    # Halt workflow on step failure?
       
       def _run(self, coordinator) -> WorkflowResult:
           """Execute all steps sequentially"""

Parameter Types
~~~~~~~~~~~~~~~

When customizing workflow steps, two parameter types control behavior:

**1. search_parameters** - Arguments passed to ``coordinator._search()``

.. code-block:: python

   # passed to SearchCoordinator._search() in the current workflow on execution
   search_parameters = {
       'page': 1,                    # Which page to retrieve
       'normalize_records': True,    # Apply field normalization?
       'from_cache': True            # Use cached results?
   }

**2. config_parameters** - Overrides for ``SearchAPIConfig``

.. code-block:: python

   # used to update the `SearchAPIConfig` temporarily when required
   config_parameters = {
       'request_delay': 0.1,         # Rate limiting delay
       'records_per_page': 50,       # Results per page
       'id': '12345,67890',          # API-specific parameter (e.g., PubMed IDs)
       'endpoint': 'works/doi'       # API endpoint path
   }

.. tip::
   Use ``search_parameters`` to control ScholarFlux behavior. Use ``config_parameters`` to customize the API request itself.

Built-in Workflows
------------------

PubMed Search→Fetch (Automatic)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

PubMed requires two API calls: eSearch (get IDs) → eFetch (get records).

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   # PubMed workflow is automatically configured
   coordinator = SearchCoordinator(
       query="gene therapy",
       provider_name="pubmed"
   )
   
   # Single call executes two-step workflow transparently
   result = coordinator.search(page=1)
   
   if result:
       print(f"Retrieved {len(result.data)} records")
       for record in result.data[:3]:
           print(f"Title: {record.get('MedlineCitation.Article.ArticleTitle')}")
           print(f"Abstract: {record.get('MedlineCitation.Article.Abstract.AbstractText')}")
           print()

**What happens behind the scenes:**

1. **Step 1 (eSearch)**: 
   - Provider: ``pubmed`` 
   - Retrieves list of PubMed IDs matching query
   - Returns ProcessedResponse with IDs in ``metadata['IdList']['Id']``
   - **Cached** ✓

2. **Step 2 (eFetch)**:
   - Provider: ``pubmedefetch`` (different endpoint!)
   - Extracts IDs from Step 1's metadata
   - Fetches complete records for those IDs
   - Returns ProcessedResponse with full articles
   - **Cached** ✓

3. **Result**: Full article metadata including abstracts, preserved search metadata

.. note::
   **Provider Switching**: Workflows can use different providers for different steps. PubMed uses ``pubmed`` for eSearch and ``pubmedefetch`` for eFetch because they have different base URLs and configurations. Rate limiting is handled independently for each provider.

.. tip::
   ScholarFlux preserves metadata from Step 1 (total results, query info) in the final response, so you get both complete article data and search context.

Custom Workflows
----------------

When to Create Custom Workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You need a custom workflow when:

- ✅ An API requires multiple steps to get complete data
- ✅ You need to filter/transform data between steps
- ✅ You want to aggregate results from multiple searches
- ✅ You need to use results from one search to guide the next

You DON'T need a custom workflow when:

- ❌ Simple single-step retrieval (use ``SearchCoordinator`` directly)
- ❌ Querying multiple providers (use :class:`~scholar_flux.api.MultiSearchCoordinator`)
- ❌ Just caching results (use :doc:`caching_strategies`)

Creating Custom Workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~

Build custom workflows by subclassing :class:`~scholar_flux.api.workflows.WorkflowStep`:

.. code-block:: python

   from scholar_flux.api.workflows import WorkflowStep, SearchWorkflow, StepContext
   from scholar_flux.api.models import ProcessedResponse
   from scholar_flux.utils import generate_iso_timestamp
   from typing import Optional
   
   class MySearchStep(WorkflowStep):
       """Step 1: Search for records"""
       
       provider_name: Optional[str] = "my_provider"
   
   class MyFetchStep(WorkflowStep):
       """Step 2: Fetch detailed data"""
       
       provider_name: Optional[str] = "my_provider"
       
       def pre_transform(
           self,
           ctx: Optional[StepContext] = None,
           *args,
           **kwargs
       ) -> "MyFetchStep":
           """Extract data from previous step to configure this step"""
           
           # Validate context type
           self._verify_context(ctx)
           
           # Extract data from Step 1
           if ctx and ctx.result:
               previous_results = ctx.result.data or []
               
               # Extract IDs for Step 2
               ids = [r['id'] for r in previous_results if r.get('id')]
               
               # Configure this step to use those IDs
               self.config_parameters = {'ids': ids}
           
           return self
       
       def _run(
           self,
           step_number: int,
           search_coordinator,
           ctx: Optional[StepContext] = None,
           *args,
           **kwargs
       ) -> StepContext:
           """Execute Step 2 using IDs from Step 1"""
           
           # Get IDs configured in pre_transform
           ids = self.config_parameters.get('ids', [])
           
           # Fetch records using IDs
           responses = [
               search_coordinator.parameter_search(id=id_value)
               for id_value in ids
           ]
           
           # Combine results
           combined_data = [
               record
               for response in responses if response
               for record in (response.data or [])
           ]
           
           # Create final response
           final_response = ProcessedResponse(
               response=responses[0].response if responses else None,
               processed_records=combined_data,
               metadata={'count': len(combined_data)},
               created_at=generate_iso_timestamp()
           )
           
           # Return as StepContext
           return StepContext(
               step_number=step_number,
               step=self.model_copy(),
               result=final_response
           )

   # Create and use workflow
   workflow = SearchWorkflow(steps=[MySearchStep(), MyFetchStep()])
   coordinator = SearchCoordinator(
       query="test",
       provider_name="my_provider",
       workflow=workflow
   )
   
   result = coordinator.search(page=1)

**Key Customization Points:**

1. **pre_transform()**: Modify step configuration based on previous results
2. **_run()**: Execute the step's main logic
3. **post_transform()**: Transform results after execution (optional)
4. **with_context()**: Temporarily modify coordinator for step scope (advanced)

Real-World Example 1: Crossref DOI Enrichment
----------------------------------------------

This workflow searches Crossref, then fetches detailed metadata for each DOI.

Complete Implementation
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from scholar_flux.api.workflows import WorkflowStep, SearchWorkflow, StepContext
   from scholar_flux.api import SearchCoordinator, ProcessedResponse
   from scholar_flux.api.models import SearchAPIConfig
   from scholar_flux.utils.helpers import generate_iso_timestamp
   from typing import Optional
   from pydantic import Field
   
   
   class PreprocessStep(WorkflowStep):
       """Step 1: Search Crossref for articles"""
       
       provider_name: Optional[str] = Field(
           default="crossref",
           description="Provider for initial search"
       )
   
   
   class EnrichmentStep(WorkflowStep):
       """Step 2: Fetch detailed metadata using DOIs from Step 1"""
       
       provider_name: Optional[str] = Field(
           default="crossref",
           description="Provider for DOI-based retrieval"
       )
       
       def pre_transform(
           self,
           ctx: Optional[StepContext] = None,
           provider_name: Optional[str] = None,
           search_parameters: Optional[dict] = None,
           config_parameters: Optional[dict] = None,
           *args,
           **kwargs
       ) -> "EnrichmentStep":
           """Extract DOIs from Step 1 results"""
           
           # Validate we have context
           self._verify_context(ctx)
           
           # Get results from preprocessing step
           preprocessed_result = ctx.result.data or [] if ctx and ctx.result else []
           
           if not preprocessed_result:
               raise TypeError(
                   f"Step 1 produced no records. Cannot continue."
               )
           
           # Extract DOIs
           dois = [r['DOI'] for r in preprocessed_result if r.get('DOI')]
           
           # Configure for DOI-based retrieval
           # Note: Using config_parameters to override SearchAPIConfig
           self.search_parameters = {"parameters": {"dois": dois}}
           
           return self
       
       def _run(
           self,
           step_number: int,
           search_coordinator,
           ctx: Optional[StepContext] = None,
           verbose: Optional[bool] = True,
           *args,
           **kwargs
       ) -> StepContext:
           """Fetch detailed metadata for each DOI"""
           
           # Get DOI list from pre_transform
           doi_list = self.search_parameters["parameters"]["dois"]
           
           # Fetch each DOI individually
           # Note: parameter_search() allows custom endpoint paths
           processed_responses = [
               search_coordinator.parameter_search(
                   endpoint="works/" + doi,
                   **kwargs
               )
               for doi in doi_list if doi
           ]
           
           # Combine all records
           combined_records = [
               record
               for response in processed_responses
               if response and response.data
               for record in response.data
           ]
           
           # Create final response
           final_response = ProcessedResponse(
               response=processed_responses[0].response if processed_responses else None,
               processed_records=combined_records,
               metadata={
                   'total_dois': len(doi_list),
                   'enriched_records': len(combined_records)
               },
               created_at=generate_iso_timestamp()
           )
           
           return StepContext(
               step_number=step_number,
               step=self.model_copy(),
               result=final_response
           )

Usage Example
~~~~~~~~~~~~~

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.sessions import CachedSessionManager
   
   # Create enrichment workflow
   enrichment_workflow = SearchWorkflow(
       steps=[PreprocessStep(), EnrichmentStep()]
   )
   
   # Configure coordinator
   session_manager = CachedSessionManager(
       backend="redis",
       user_agent="Research/1.0 (mailto:user@institution.edu)"
   )
   
   coordinator = SearchCoordinator(
       query="machine learning healthcare",
       provider_name="crossref",
       workflow=enrichment_workflow,
       session=session_manager()
   )
   
   # Execute workflow
   result = coordinator.search(page=1)
   
   if result:
       print(f"✅ Enriched {len(result.data)} records")
       print(f"Metadata: {result.metadata}")
   else:
       print(f"❌ Error: {result.error} - {result.message}")

.. note::
   **Caching Behavior**: Both Step 1 (search) and Step 2 (enrichment) results are cached independently. If you run the same query again, both steps will be retrieved from cache instantly.

Real-World Example 2: OpenAlex Citation Network
------------------------------------------------

This workflow builds citation networks by:
1. Finding seed papers
2. Retrieving papers that cite them
3. Retrieving papers they cite

Complete Implementation
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from scholar_flux.api.workflows import WorkflowStep, SearchWorkflow, StepContext
   from scholar_flux.api import SearchCoordinator, ProcessedResponse
   from scholar_flux.utils.helpers import generate_iso_timestamp
   from typing import Optional
   from pydantic import Field
   
   
   class SeedPaperStep(WorkflowStep):
       """Step 1: Find seed papers matching the query"""
       
       provider_name: Optional[str] = "openalex"
   
   
   class CitationStep(WorkflowStep):
       """Step 2 (and 3): Fetch citation network data"""
       
       provider_name: Optional[str] = "openalex"
       citation_parameter: str = Field(
           default="cited_by",
           description="'cited_by' or 'cites' for citation direction"
       )
       record_limit: Optional[int] = Field(
           default=None,
           description="Max records to fetch per seed paper"
       )
       
       def pre_transform(
           self,
           ctx: Optional[StepContext] = None,
           *args,
           **kwargs
       ) -> "CitationStep":
           """Extract OpenAlex IDs from previous results"""
           
           self._verify_context(ctx)
           
           # Get seed papers from previous step
           if ctx and ctx.result:
               seed_papers = ctx.result.data or []
               
               # Extract OpenAlex IDs
               openalex_ids = [
                   p.get('id') for p in seed_papers 
                   if p.get('id')
               ]
               
               # Store for _run()
               self.search_parameters = {'openalex_ids': openalex_ids}
           
           return self
       
       def _run(
           self,
           step_number: int,
           search_coordinator,
           ctx: Optional[StepContext] = None,
           *args,
           **kwargs
       ) -> StepContext:
           """Fetch citations for each seed paper"""
           
           openalex_ids = self.search_parameters.get('openalex_ids', [])
           
           all_citations = []
           
           for oa_id in openalex_ids:
               # Build filter for this paper's citations
               filter_param = f"{self.citation_parameter}:{oa_id}"
               
               # Fetch citations
               response = search_coordinator.parameter_search(
                   filter=filter_param,
                   per_page=self.record_limit or 25,
                   **kwargs
               )
               
               if response and response.data:
                   all_citations.extend(response.data[:self.record_limit] if self.record_limit else response.data)
           
           # Deduplicate by OpenAlex ID
           seen_ids = set()
           unique_citations = []
           for citation in all_citations:
               citation_id = citation.get('id')
               if citation_id and citation_id not in seen_ids:
                   seen_ids.add(citation_id)
                   unique_citations.append(citation)
           
           # Create final response
           final_response = ProcessedResponse(
               response=None,  # Multiple API calls, no single response
               processed_records=unique_citations,
               metadata={
                   'seed_papers': len(openalex_ids),
                   'total_citations': len(all_citations),
                   'unique_citations': len(unique_citations),
                   'citation_direction': self.citation_parameter
               },
               created_at=generate_iso_timestamp()
           )
           
           return StepContext(
               step_number=step_number,
               step=self.model_copy(),
               result=final_response
           )
   
   
   class OpenAlexCitationWorkflow(SearchWorkflow):
       """Three-step workflow for building citation networks"""
       
       def _create_workflow_result(
           self, 
           result: Optional[ProcessedResponse] = None
       ) -> WorkflowResult:
           """Merge results from all citation steps"""
           
           # Use base implementation
           workflow_result = super()._create_workflow_result(result)
           
           # Optionally merge data from all steps
           if len(self._history) >= 3:
               seed_step = self._history[0]
               cited_by_step = self._history[1]
               cites_step = self._history[2]
               
               # Combine all unique papers
               all_papers = []
               seen_ids = set()
               
               for step_ctx in [seed_step, cited_by_step, cites_step]:
                   if step_ctx.result and step_ctx.result.data:
                       for paper in step_ctx.result.data:
                           paper_id = paper.get('id')
                           if paper_id and paper_id not in seen_ids:
                               seen_ids.add(paper_id)
                               all_papers.append(paper)
               
               # Create merged response
               merged_response = ProcessedResponse(
                   response=None,
                   processed_records=all_papers,
                   metadata={
                       'total_papers': len(all_papers),
                       'seed_papers': len(seed_step.result.data) if seed_step.result else 0,
                       'citing_papers': len(cited_by_step.result.data) if cited_by_step.result else 0,
                       'cited_papers': len(cites_step.result.data) if cites_step.result else 0
                   },
                   created_at=generate_iso_timestamp()
               )
               
               workflow_result.result = merged_response
           
           return workflow_result

Usage Example
~~~~~~~~~~~~~

.. code-block:: python

   from scholar_flux import CachedSessionManager
   
   # Create citation network workflow
   citation_workflow = OpenAlexCitationWorkflow(
       steps=[
           SeedPaperStep(),
           CitationStep(citation_parameter="cited_by"),  # Papers citing seeds
           CitationStep(citation_parameter="cites", record_limit=5)  # Papers cited by seeds
       ]
   )
   
   # Configure coordinator
   session_manager = CachedSessionManager(
       backend="redis",
       user_agent="Research/1.0 (mailto:user@institution.edu)"
   )
   
   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="openalex",
       workflow=citation_workflow,
       session=session_manager(),
       records_per_page=10
   )
   
   # Execute workflow
   result = coordinator.search(page=1)
   
   if result and result.data:
       print(f"Built citation network with {len(result.data)} unique papers")
       print(f"Metadata: {result.metadata}")
       
       # Analyze citation network
       import pandas as pd
       df = pd.DataFrame(result.data)
       print(f"\nPapers by type: {df.get('type', pd.Series()).value_counts()}")
   else:
       print(f"Error: {result.error}")

.. note::
   **Advanced Pattern**: This workflow overrides ``_create_workflow_result()`` to merge results from all three steps into a single unified response. This is an advanced customization technique for workflows that aggregate data from multiple steps.

Workflow Error Handling
-----------------------

How Errors Propagate
~~~~~~~~~~~~~~~~~~~~

When a workflow step fails, ScholarFlux returns an error response immediately:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.api import ErrorResponse, NonResponse
   
   coordinator = SearchCoordinator(
       query="test",
       provider_name="pubmed"
   )
   
   result = coordinator.search(page=1)
   
   # Check if workflow succeeded
   if result:
       print(f"✅ Workflow succeeded: {len(result.data)} records")
   elif isinstance(result, ErrorResponse):
       print(f"❌ API error: {result.message}")
       print(f"Status code: {result.status_code}")
   elif isinstance(result, NonResponse):
       print(f"❌ Network/config error: {result.message}")

**What happens on failure:**

- If **Step 1 fails**: Returns ErrorResponse immediately, no subsequent steps run
- If **Step 2 fails**: Returns ErrorResponse with details about Step 2's failure
- **Partial results are cached**: Step 1's successful result remains in cache

Accessing Workflow History
~~~~~~~~~~~~~~~~~~~~~~~~~~~

For debugging, you can inspect what steps succeeded before failure:

.. code-block:: python

   coordinator = SearchCoordinator(
       query="test",
       provider_name="pubmed"
   )
   
   result = coordinator.search(page=1)
   
   # Check workflow history
   if coordinator.workflow and coordinator.workflow._history:
       print(f"Executed {len(coordinator.workflow._history)} steps:")
       
       for step_ctx in coordinator.workflow._history:
           step_name = step_ctx.step.__class__.__name__
           success = bool(step_ctx.result)
           record_count = len(step_ctx.result.data or []) if step_ctx.result else 0
           
           print(f"  Step {step_ctx.step_number} ({step_name}):")
           print(f"    Success: {success}")
           print(f"    Records: {record_count}")
           
           if isinstance(step_ctx.result, ErrorResponse):
               print(f"    Error: {step_ctx.result.message}")

**Example output:**

.. code-block:: text

   Executed 2 steps:
     Step 0 (PubMedSearchStep):
       Success: True
       Records: 0  # eSearch returns IDs in metadata, not data
     Step 1 (PubMedFetchStep):
       Success: False
       Records: 0
       Error: HTTP 500: Internal server error

.. tip::
   The ``_history`` attribute is useful for debugging workflow failures, especially in complex multi-step workflows where you need to see exactly where the process failed.

Stop on Error Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Control whether workflows halt on first error:

.. code-block:: python

   from scholar_flux.api.workflows import SearchWorkflow
   
   # Stop on first error (default)
   workflow = SearchWorkflow(
       steps=[Step1(), Step2(), Step3()],
       stop_on_error=True
   )
   
   # Continue through all steps even if some fail
   workflow = SearchWorkflow(
       steps=[Step1(), Step2(), Step3()],
       stop_on_error=False  # All steps execute, history shows failures
   )

.. warning::
   With ``stop_on_error=False``, later steps may fail due to missing data from earlier steps. Use this carefully and check ``_history`` to see which steps succeeded.

Creating ErrorResponse for Testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When testing workflows, you may need to create ``ErrorResponse`` objects. ScholarFlux requires a response object:

.. code-block:: python

   from scholar_flux.api.models import ErrorResponse, ReconstructedResponse
   
   # Create a mock response for testing
   test_response = ReconstructedResponse.build(
       url="https://api.example.com/test",
       status_code=500,
       json={"status": "failure", "message": "Test error"}
   )
   
   # Create ErrorResponse with the mock response
   error = ErrorResponse(
       response=test_response,
       error="TestError",
       message="Intentional failure for testing"
   )

This pattern is useful when creating test workflows with simulated failures.

Best Practices
--------------

Workflow Design
~~~~~~~~~~~~~~~

**DO:**

- Keep steps focused on single responsibilities (one step = one API call or transformation)
- Use ``pre_transform()`` to pass data between steps cleanly
- Handle errors gracefully in ``_run()`` and provide informative error messages
- Validate context in ``pre_transform()`` with ``self._verify_context(ctx)``
- Use descriptive step class names that explain what the step does

**DON'T:**

- Make steps depend on external state outside the workflow
- Skip error handling (always check if previous results exist)
- Modify coordinator state directly in steps (use ``with_context()`` if needed)
- Create workflows for simple single-step retrieval (just use SearchCoordinator directly)

Type Safety
~~~~~~~~~~~

Use type annotations for better code quality and IDE support:

.. code-block:: python

   from typing import Optional
   from scholar_flux.api.workflows import WorkflowStep, StepContext
   from scholar_flux.api.models import ProcessedResponse
   
   class TypedStep(WorkflowStep):
       provider_name: Optional[str] = "plos"
       
       def pre_transform(
           self, 
           ctx: Optional[StepContext] = None,
           *args,
           **kwargs
       ) -> "TypedStep":
           """Validate context with type checking"""
           self._verify_context(ctx)
           
           # Type-safe context checking
           if not isinstance(ctx, StepContext):
               raise RuntimeError(f"Expected StepContext, got {type(ctx)}")
           
           # Type-safe data checking
           if not (ctx.result and ctx.result.data):
               raise RuntimeError("No data from previous step")
           
           return self
       
       def _run(
           self,
           step_number: int,
           search_coordinator,
           ctx: Optional[StepContext] = None,
           *args,
           **kwargs
       ) -> StepContext:
           """Execute with explicit return type"""
           
           # Use type annotations for collections
           records: list[dict] = []
           
           # ... step logic
           
           response = ProcessedResponse(
               response=None,
               processed_records=records,
               metadata={},
               created_at=generate_iso_timestamp()
           )
           
           return StepContext(
               step_number=step_number,
               step=self.model_copy(),
               result=response
           )

**Benefits of type annotations:**

- Catch errors early with ``mypy`` type checking
- Better IDE autocomplete and navigation
- Self-documenting code
- Easier refactoring

Parameter Types Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~

**search_parameters** - Control ScholarFlux behavior:

.. code-block:: python

   search_parameters = {
       'page': 1,                     # Which page to retrieve
       'normalize_records': True,     # Apply field normalization?
       'from_request_cache': True,    # Use HTTP cache?
       'from_process_cache': True     # Use processing cache?
   }

**config_parameters** - Override SearchAPIConfig:

.. code-block:: python

   config_parameters = {
       'request_delay': 0.1,          # Rate limiting
       'records_per_page': 50,        # Results per page
       'id': '12345,67890',           # API-specific params
       'endpoint': 'works/',          # API endpoint path
       'filter': 'type:journal'       # API filters
   }

Caching Strategy
~~~~~~~~~~~~~~~~

Enable caching for expensive workflows to avoid re-executing all steps:

.. code-block:: python

   from scholar_flux import CachedSessionManager, DataCacheManager
   
   # HTTP caching (request-level)
   session = CachedSessionManager(backend='redis')
   
   # Result caching (processing-level)
   cache = DataCacheManager.with_storage('redis', namespace='my_workflow')
   
   coordinator = SearchCoordinator(
       query="test",
       workflow=my_workflow,
       session=session(),       # Each step's HTTP request cached
       cache_manager=cache      # Each step's processed result cached
   )
   
   # First run: executes all workflow steps
   result = coordinator.search(page=1)
   
   # Second run: all steps retrieved from cache (instant)
   result = coordinator.search(page=1)

**How workflow caching works:**

1. Each step calls ``coordinator._search()`` internally
2. Each ``_search()`` call checks DataCacheManager for cached results
3. If cached, the step returns immediately without making an API request
4. If not cached, the step executes and caches its result

.. tip::
   **Best practice**: Use Redis or MongoDB caching in production for persistent workflow results across sessions.

Testing Workflows
~~~~~~~~~~~~~~~~~

Test each step independently before testing the full workflow:

.. code-block:: python

   from scholar_flux.api.workflows import StepContext
   from scholar_flux.api import SearchCoordinator, ProcessedResponse
   
   # Test Step 1 independently
   step1 = MySearchStep()
   mock_coordinator = SearchCoordinator(
       provider_name='my_provider',
       query='test'
   )
   
   # Execute Step 1
   result = step1._run(
       step_number=1,
       search_coordinator=mock_coordinator,
       ctx=None
   )
   
   # Verify Step 1 output
   assert isinstance(result, StepContext)
   assert result.result
   assert len(result.result.data or []) > 0
   
   # Test Step 2 with Step 1's output
   step2 = MyFetchStep()
   step2 = step2.pre_transform(ctx=result)
   
   # Use with_context for scoped execution (if step implements it)
   with step2.with_context(mock_coordinator):
       step2_result = step2._run(
           step_number=2,
           search_coordinator=mock_coordinator,
           ctx=result
       )
   
   # Verify Step 2 output
   assert isinstance(step2_result, StepContext)
   assert step2_result.result
   assert len(step2_result.result.data or []) > 0

.. tip::
   Test steps individually first, then test the complete workflow. This makes debugging much easier.

Advanced Customization
----------------------

The with_context() Pattern
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``with_context()`` to temporarily modify coordinator settings for a step's scope:

.. code-block:: python

   from contextlib import contextmanager
   from typing import Generator
   from scholar_flux.api.workflows import WorkflowStep
   
   class CustomStep(WorkflowStep):
       """Step with temporary configuration changes"""
       
       provider_name: str = "plos"
       temp_delay: float = 0.1
       
       @contextmanager
       def with_context(
           self, 
           search_coordinator,
           *args,
           **kwargs
       ) -> Generator["CustomStep", None, None]:
           """Temporarily reduce rate limiting for this step"""
           
           # Save original delay
           original_delay = search_coordinator.api.config.request_delay
           
           try:
               # Apply temporary delay
               search_coordinator.api.config.request_delay = self.temp_delay
               yield self
           finally:
               # Restore original delay
               search_coordinator.api.config.request_delay = original_delay

**When to use with_context():**

- Temporarily modify rate limiting for specific steps
- Apply step-specific API configurations
- Scope expensive operations (logging, metrics)
- Test workflows with mock configurations

.. note::
   ``with_context()`` is an advanced pattern. Most workflows don't need it—use ``pre_transform()`` and ``config_parameters`` instead for simpler customization.

Overriding _create_workflow_result()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Override this method to customize how final results are assembled:

.. code-block:: python

   from scholar_flux.api.workflows import SearchWorkflow, WorkflowResult
   from scholar_flux.api.models import ProcessedResponse
   
   class MergedWorkflow(SearchWorkflow):
       """Workflow that merges results from all steps"""
       
       def _create_workflow_result(
           self,
           result: Optional[ProcessedResponse] = None
       ) -> WorkflowResult:
           """Merge data from all steps into final result"""
           
           # Collect all records from all steps
           all_records: list[dict] = []
           for step_ctx in self._history:
               if step_ctx.result and step_ctx.result.data:
                   all_records.extend(step_ctx.result.data)
           
           # Deduplicate
           seen_ids = set()
           unique_records = []
           for record in all_records:
               record_id = record.get('id')
               if record_id and record_id not in seen_ids:
                   seen_ids.add(record_id)
                   unique_records.append(record)
           
           # Create merged response
           merged_response = ProcessedResponse(
               response=None,
               processed_records=unique_records,
               metadata={
                   'total_steps': len(self._history),
                   'unique_records': len(unique_records)
               },
               created_at=generate_iso_timestamp()
           )
           
           return WorkflowResult(
               history=self._history,
               result=merged_response
           )
   
   class Step1(WorkflowStep):
       provider_name: str = "plos"
       
       def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
           response = ProcessedResponse(
               response=None,
               processed_records=[{'id': '1', 'title': 'Paper A'}],
               metadata={},
               created_at=generate_iso_timestamp()
           )
           return StepContext(step_number=step_number, step=self.model_copy(), result=response)
   
   class Step2(WorkflowStep):
       provider_name: str = "plos"
       
       def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
           response = ProcessedResponse(
               response=None,
               processed_records=[{'id': '2', 'title': 'Paper B'}],
               metadata={},
               created_at=generate_iso_timestamp()
           )
           return StepContext(step_number=step_number, step=self.model_copy(), result=response)

**Common use cases:**

- Merging results from multiple steps (like OpenAlex citation network)
- Copying metadata from early steps to final result (like PubMed)
- Aggregating statistics across all steps
- Deduplicating records from multiple sources

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**Issue**: "Step X produced no records. Cannot continue."

**Cause**: A step returned empty results, and the next step expected data.

**Solution**: 

.. code-block:: python

   def pre_transform(self, ctx: StepContext) -> "MyStep":
       self._verify_context(ctx)
       
       if not isinstance(ctx, StepContext):
           raise RuntimeError(f"Expected `ctx` to be a StepContext, received {type(ctx)}")
       
       # Check if previous step has data
       if not (ctx.result and ctx.result.data):
           raise RuntimeError(
               f"Step {ctx.step_number} returned no results. "
               f"Check query parameters or API availability."
           )
       
       # ... rest of pre_transform

**Issue**: Workflow runs but returns wrong data

**Cause**: Parameter passing between steps is incorrect.

**Solution**: Debug with ``_history``:

.. code-block:: python

   result = coordinator.search(page=1)
   
   # Inspect what each step received and returned
   for i, step_ctx in enumerate(coordinator.workflow._history):
       print(f"\n=== Step {i} ===")
       print(f"Step type: {step_ctx.step.__class__.__name__}")
       print(f"Config: {step_ctx.step.config_parameters}")
       print(f"Search params: {step_ctx.step.search_parameters}")
       if step_ctx.result:
           print(f"Records returned: {len(step_ctx.result.data or [])}")
           print(f"Metadata: {step_ctx.result.metadata}")

**Issue**: Workflow caching not working

**Cause**: Cache keys include all parameters, so slight differences prevent cache hits.

**Solution**: Use consistent parameters and namespaces:

.. code-block:: python

   # Use namespace to isolate workflow cache
   cache = DataCacheManager.with_storage(
       'redis',
       namespace='my_workflow_v1'  # Version namespace for cache isolation
   )

Next Steps
----------

**Related Guides:**

- :doc:`getting_started` - Foundation for workflow usage
- :doc:`response_handling_patterns` - Error handling in workflows
- :doc:`multi_provider_search` - Use workflows with multiple providers
- :doc:`schema_normalization` - Normalize workflow results
- :doc:`custom_providers` - Create workflows for new providers

**Advanced Topics:**

- :doc:`caching_strategies` - Cache expensive workflow results
- :doc:`production_deployment` - Deploy workflows in production

API Reference
-------------

- :class:`~scholar_flux.api.workflows.SearchWorkflow`
- :class:`~scholar_flux.api.workflows.WorkflowStep`
- :class:`~scholar_flux.api.workflows.StepContext`
- :class:`~scholar_flux.api.workflows.WorkflowResult`
- :class:`~scholar_flux.api.workflows.PubMedSearchStep`
- :class:`~scholar_flux.api.workflows.PubMedFetchStep`
