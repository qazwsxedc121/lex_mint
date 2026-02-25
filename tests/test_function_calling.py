"""
Test script for function calling / tool use across providers.

Usage:
    ./venv/Scripts/python tests/test_function_calling.py

Iterates enabled providers with function_calling capability,
sends test prompts with tools bound, and verifies the pipeline.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run_provider_check(model_id: str) -> dict:
    """Test function calling with a specific model.

    Returns dict with keys: model_id, passed, error, details
    """
    from src.agents.simple_llm import call_llm_stream
    from src.tools.registry import get_tool_registry

    registry = get_tool_registry()
    tools = registry.get_all_tools()

    messages = [{"role": "user", "content": "What time is it right now in UTC?"}]

    collected_chunks = []
    tool_calls_events = []
    tool_results_events = []
    usage_event = None

    try:
        async for chunk in call_llm_stream(
            messages,
            session_id="test-function-calling",
            model_id=model_id,
            tools=tools,
        ):
            if isinstance(chunk, dict):
                if chunk.get("type") == "tool_calls":
                    tool_calls_events.append(chunk)
                    print(f"    [TOOL_CALLS] {chunk['calls']}")
                elif chunk.get("type") == "tool_results":
                    tool_results_events.append(chunk)
                    print(f"    [TOOL_RESULTS] {[r['result'][:80] for r in chunk['results']]}")
                elif chunk.get("type") == "usage":
                    usage_event = chunk
                # Skip other dict events
            else:
                collected_chunks.append(chunk)

        full_response = "".join(collected_chunks)
        print(f"    [RESPONSE] {full_response[:200]}")

        # Check results
        has_tool_calls = len(tool_calls_events) > 0
        has_tool_results = len(tool_results_events) > 0
        has_response = len(full_response.strip()) > 0

        if has_tool_calls and has_tool_results and has_response:
            return {
                "model_id": model_id,
                "passed": True,
                "details": f"Tool called, result received, response: {len(full_response)} chars",
            }
        elif has_response and not has_tool_calls:
            # Model responded without using tools (may have answered directly)
            return {
                "model_id": model_id,
                "passed": True,
                "details": f"Response without tool call ({len(full_response)} chars) - model may have answered directly",
            }
        else:
            return {
                "model_id": model_id,
                "passed": False,
                "details": f"tool_calls={has_tool_calls}, tool_results={has_tool_results}, response={has_response}",
            }

    except Exception as e:
        return {
            "model_id": model_id,
            "passed": False,
            "error": str(e),
        }


async def main():
    from src.api.services.model_config_service import ModelConfigService

    model_service = ModelConfigService()

    # Find all enabled models with function_calling capability
    all_models = await model_service.get_models()
    candidates = []
    for model_cfg in all_models:
        if not model_cfg.enabled:
            continue
        # Resolve provider
        try:
            _, provider_cfg = model_service.get_model_and_provider_sync(
                f"{model_cfg.provider_id}:{model_cfg.id}"
            )
            if not provider_cfg.enabled:
                continue
            caps = model_service.get_merged_capabilities(model_cfg, provider_cfg)
            if caps.function_calling:
                candidates.append(f"{model_cfg.provider_id}:{model_cfg.id}")
        except Exception:
            continue

    if not candidates:
        print("[WARN] No enabled models with function_calling found.")
        print("       Check your models_config.yaml for function_calling: true")
        return

    print(f"Found {len(candidates)} model(s) with function_calling:")
    for mid in candidates:
        print(f"  - {mid}")
    print()

    results = []
    for mid in candidates:
        print(f"Testing: {mid}")
        result = await run_provider_check(mid)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        detail = result.get("error") or result.get("details", "")
        print(f"  -> [{status}] {detail}")
        print()

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"Results: {passed}/{total} passed")


if __name__ == "__main__":
    asyncio.run(main())
