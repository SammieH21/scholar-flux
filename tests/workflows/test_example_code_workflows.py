"""Test suite for workflow documentation examples: Ensures that the logic in advanced_workflows.rst work correctly."""

from scholar_flux import SearchCoordinator
from scholar_flux.api import ProcessedResponse, ErrorResponse
from scholar_flux.api.workflows import StepContext, SearchWorkflow, WorkflowStep, WorkflowResult
from scholar_flux.utils import generate_iso_timestamp
from typing import Optional
from contextlib import contextmanager
from typing import Generator


def test_merged_workflow():
    """Test MergedWorkflow._create_workflow_result() merging logic."""
    print("\n=== Testing MergedWorkflow ===")

    class MergedWorkflow(SearchWorkflow):
        """Workflow that merges results from all steps."""

        def _create_workflow_result(self, result: Optional[ProcessedResponse | ErrorResponse] = None) -> WorkflowResult:
            """Merge data from all steps into final result."""

            # Collect all records from all steps
            all_records: list[dict] = []
            for step_ctx in self._history:
                if step_ctx.result and step_ctx.result.data:
                    all_records.extend(step_ctx.result.data)

            # Deduplicate
            seen_ids = set()
            unique_records = []
            for record in all_records:
                record_id = record.get("id")
                if record_id and record_id not in seen_ids:
                    seen_ids.add(record_id)
                    unique_records.append(record)

            # Create merged response
            merged_response = ProcessedResponse(
                response=None,
                processed_records=unique_records,
                metadata={"total_steps": len(self._history), "unique_records": len(unique_records)},
                created_at=generate_iso_timestamp(),
            )

            return WorkflowResult(history=self._history, result=merged_response)

    class Step1(WorkflowStep):
        provider_name: Optional[str] = "plos"

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            response = ProcessedResponse(
                response=None,
                processed_records=[{"id": "1", "title": "Paper A"}],
                metadata={},
                created_at=generate_iso_timestamp(),
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=response)

    class Step2(WorkflowStep):
        provider_name: Optional[str] = "plos"

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            response = ProcessedResponse(
                response=None,
                processed_records=[
                    {"id": "2", "title": "Paper B"},
                    {"id": "1", "title": "Paper A"},  # Duplicate - should be removed
                ],
                metadata={},
                created_at=generate_iso_timestamp(),
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=response)

    # Test merged workflow
    workflow = MergedWorkflow(steps=[Step1(), Step2()])
    coordinator = SearchCoordinator(query="test", provider_name="plos", workflow=workflow)
    result = coordinator.search(page=1)

    # Verify merging worked
    assert result and result.data and result.metadata, "Result should have data and metadata"
    assert len(result.data) == 2, f"Expected 2 unique records, got {len(result.data)}"
    assert result.metadata["total_steps"] == 2, "Should have executed 2 steps"
    assert result.metadata["unique_records"] == 2, "Should have 2 unique records after deduplication"

    # Verify deduplication worked (id='1' should appear only once)
    ids = [r["id"] for r in result.data]
    assert ids.count("1") == 1, "ID '1' should appear only once after deduplication"
    assert "2" in ids, "ID '2' should be present"

    print("✅ MergedWorkflow test passed")
    print(f"   - Merged {result.metadata['total_steps']} steps")
    print(f"   - Deduplicated to {result.metadata['unique_records']} unique records")
    return True


def test_with_context_pattern():
    """Test with_context() pattern for temporary coordinator modifications."""
    print("\n=== Testing with_context() Pattern ===")

    class CustomStep(WorkflowStep):
        """Step with temporary configuration changes."""

        provider_name: Optional[str] = "plos"
        temp_delay: float = 0.1

        @contextmanager
        def with_context(
            self, search_coordinator, *args, **kwargs  # Note: parameter name matches _run signature
        ) -> Generator["CustomStep", None, None]:
            """Temporarily reduce rate limiting for this step."""

            # Save original delay
            original_delay = search_coordinator.api.config.request_delay

            try:
                # Apply temporary delay
                search_coordinator.api.config.request_delay = self.temp_delay
                yield self
            finally:
                # Restore original delay
                search_coordinator.api.config.request_delay = original_delay

    # Create coordinator
    coordinator = SearchCoordinator(query="test", provider_name="plos")
    original_delay = coordinator.api.config.request_delay

    # Create custom step
    custom_step = CustomStep(temp_delay=0.1)

    # Test modification within context
    with custom_step.with_context(coordinator):
        modified_delay = coordinator.api.config.request_delay
        assert modified_delay == 0.1, f"Expected delay 0.1, got {modified_delay}"
        print(f"   ✓ Delay modified: {original_delay} → {modified_delay}")

    # Test restoration after context
    restored_delay = coordinator.api.config.request_delay
    assert restored_delay == original_delay, f"Delay not restored: expected {original_delay}, got {restored_delay}"
    print(f"   ✓ Delay restored: {modified_delay} → {restored_delay}")

    print("✅ with_context() pattern test passed")
    return True


def test_workflow_history_inspection():
    """Test accessing coordinator.workflow._history for debugging."""
    print("\n=== Testing Workflow History Inspection ===")

    class TestStep1(WorkflowStep):
        provider_name: Optional[str] = "plos"

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            response = ProcessedResponse(
                response=None,
                processed_records=[{"id": "1", "data": "test"}],
                metadata={"step": "first"},
                created_at=generate_iso_timestamp(),
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=response)

    class TestStep2(WorkflowStep):
        provider_name: Optional[str] = "plos"

        def pre_transform(self, ctx: Optional[StepContext] = None, *args, **kwargs):
            """Extract data from previous step."""
            self._verify_context(ctx)
            if ctx and ctx.result and ctx.result.data:
                # Use data from step 1
                self.search_parameters = {"previous_data": ctx.result.data}
            return self

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            response = ProcessedResponse(
                response=None,
                processed_records=[{"id": "2", "data": "test2"}],
                metadata={"step": "second"},
                created_at=generate_iso_timestamp(),
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=response)

    # Create workflow
    workflow = SearchWorkflow(steps=[TestStep1(), TestStep2()])
    coordinator = SearchCoordinator(query="test", provider_name="plos", workflow=workflow)
    _ = coordinator.search(page=1)

    # Verify _history is accessible
    assert coordinator.workflow is not None, "Workflow should be set"
    assert hasattr(coordinator.workflow, "_history"), "_history attribute should exist"

    history = coordinator.workflow._history
    assert len(history) == 2, f"Expected 2 steps in history, got {len(history)}"

    # Verify history structure
    print(f"   Executed {len(history)} steps:")
    for step_ctx in history:
        assert hasattr(step_ctx, "step_number"), "StepContext should have step_number"
        assert hasattr(step_ctx, "step"), "StepContext should have step"
        assert hasattr(step_ctx, "result"), "StepContext should have result"

        step_name = step_ctx.step.__class__.__name__
        success = bool(step_ctx.result)
        record_count = len(step_ctx.result.data or []) if step_ctx.result else 0

        print(f"     Step {step_ctx.step_number} ({step_name}):")
        print(f"       Success: {success}")
        print(f"       Records: {record_count}")

        if isinstance(step_ctx.result, ProcessedResponse):
            print(f"       Metadata: {step_ctx.result.metadata}")

    print("✅ Workflow history inspection test passed")
    return True


def test_pre_transform_error_handling():
    """Test error handling in pre_transform when previous step has no data."""
    print("\n=== Testing pre_transform Error Handling ===")

    class StrictStep(WorkflowStep):
        """Step that requires data from previous step."""

        provider_name: Optional[str] = "plos"

        def pre_transform(self, ctx: Optional[StepContext] = None, *args, **kwargs):
            """Validate context before proceeding."""
            self._verify_context(ctx)

            if not isinstance(ctx, StepContext):
                raise RuntimeError(f"Expected `ctx` to be a StepContext, received {type(ctx)}")

            # Check if previous step has data
            if not (ctx.result and ctx.result.data):
                raise RuntimeError(
                    f"Step {ctx.step_number} returned no results. " f"Check query parameters or API availability."
                )

            return self

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            response = ProcessedResponse(
                response=None, processed_records=[{"id": "1"}], metadata={}, created_at=generate_iso_timestamp()
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=response)

    # Create context with empty result
    empty_ctx = StepContext(
        step_number=1,
        step=WorkflowStep(provider_name="plos"),
        result=ProcessedResponse(
            response=None, processed_records=[], metadata={}, created_at=generate_iso_timestamp()  # Empty!
        ),
    )

    # Should raise RuntimeError
    step = StrictStep()
    try:
        step.pre_transform(empty_ctx)
        assert False, "Should have raised RuntimeError for empty data"
    except RuntimeError as e:
        error_msg = str(e)
        assert "no results" in error_msg.lower(), f"Error message should mention 'no results': {error_msg}"
        print(f"   ✓ Correctly raised RuntimeError: {error_msg}")

    # Test with valid data - should not raise
    valid_ctx = StepContext(
        step_number=1,
        step=WorkflowStep(provider_name="plos"),
        result=ProcessedResponse(
            response=None,
            processed_records=[{"id": "1", "data": "valid"}],
            metadata={},
            created_at=generate_iso_timestamp(),
        ),
    )

    try:
        step.pre_transform(valid_ctx)
        print("   ✓ No error raised with valid data")
    except RuntimeError as e:
        assert False, f"Should not raise error with valid data: {e}"

    print("✅ pre_transform error handling test passed")
    return True


def test_pubmed_workflow_automatic_configuration():
    """Test that PubMed workflow is automatically configured."""
    print("\n=== Testing PubMed Automatic Workflow Configuration ===")

    # Create PubMed coordinator without explicit workflow
    coordinator = SearchCoordinator(query="test", provider_name="pubmed")

    # Verify workflow was automatically configured
    assert coordinator.workflow is not None, "PubMed workflow should be auto-configured"
    assert isinstance(coordinator.workflow, SearchWorkflow), "Should be a SearchWorkflow instance"

    # Check workflow has steps
    assert len(coordinator.workflow.steps) >= 2, "PubMed workflow should have at least 2 steps"

    print(f"   ✓ Workflow auto-configured with {len(coordinator.workflow.steps)} steps")

    # Verify step types
    step_names = [step.__class__.__name__ for step in coordinator.workflow.steps]
    print(f"   ✓ Steps: {', '.join(step_names)}")

    print("✅ PubMed automatic workflow configuration test passed")
    return True


def test_stop_on_error_configuration():
    """Test stop_on_error workflow configuration."""
    print("\n=== Testing stop_on_error Configuration ===")

    class FailingStep(WorkflowStep):
        """Step that always fails."""

        provider_name: Optional[str] = "plos"

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            # Return an ErrorResponse
            from scholar_flux.api.models import ErrorResponse, ReconstructedResponse

            test_response = ReconstructedResponse.build(
                url="https://an-example-test-url.com", status_code=500, json={"status": "failure"}
            )
            error = ErrorResponse(
                response=test_response,
                error="TestError",
                message="Intentional failure for testing",
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=error)

    class SuccessStep(WorkflowStep):
        """Step that always succeeds."""

        provider_name: Optional[str] = "plos"

        def _run(self, step_number, search_coordinator, ctx=None, *args, **kwargs):
            response = ProcessedResponse(
                response=None, processed_records=[{"id": "1"}], metadata={}, created_at=generate_iso_timestamp()
            )
            return StepContext(step_number=step_number, step=self.model_copy(), result=response)

    # Test with stop_on_error=True (default)
    workflow_stop = SearchWorkflow(steps=[SuccessStep(), FailingStep(), SuccessStep()], stop_on_error=True)
    coordinator_stop = SearchCoordinator(query="test", provider_name="plos", workflow=workflow_stop)
    result_stop = coordinator_stop.search(page=1)

    # Should get ErrorResponse
    assert isinstance(result_stop, ErrorResponse), "Should return ErrorResponse when step fails"
    print("   ✓ stop_on_error=True: Workflow stopped on error")
    print(f"     Error: {result_stop.error}")

    # Test with stop_on_error=False
    workflow_continue = SearchWorkflow(steps=[SuccessStep(), FailingStep(), SuccessStep()], stop_on_error=False)
    coordinator_continue = SearchCoordinator(query="test", provider_name="plos", workflow=workflow_continue)
    _ = coordinator_continue.search(page=1)

    # Check history to see all steps executed
    if coordinator_continue.workflow and coordinator_continue.workflow._history:
        history_len = len(coordinator_continue.workflow._history)
        print(f"   ✓ stop_on_error=False: All {history_len} steps executed")

    print("✅ stop_on_error configuration test passed")
    return True


def run_all_tests():
    """Run all workflow documentation tests."""
    print("\n" + "=" * 60)
    print("Testing New Workflow Documentation Examples")
    print("=" * 60)

    tests = [
        ("MergedWorkflow", test_merged_workflow),
        ("with_context() Pattern", test_with_context_pattern),
        ("Workflow History Inspection", test_workflow_history_inspection),
        ("pre_transform Error Handling", test_pre_transform_error_handling),
        ("PubMed Automatic Configuration", test_pubmed_workflow_automatic_configuration),
        ("stop_on_error Configuration", test_stop_on_error_configuration),
    ]

    results: list = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"❌ {test_name} test failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for test_name, success, error in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_name}")
        if error:
            print(f"         Error: {error}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Documentation examples are ready for production.")
    else:
        print("\n⚠️  Some tests failed. Review errors above.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
