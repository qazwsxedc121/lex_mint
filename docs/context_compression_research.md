# Context Compression Research

Reference document for future implementation of automatic context compression and management strategies. Based on analysis of LobeChat, Chatbox, OpenCode, Claude Code, and LangGraph native options.

---

## Current Implementation Status

Two context management mechanisms exist in `src/agents/simple_llm.py`:

### Separator-Based Context Filtering (lines 487-510)

- User manually inserts a `"role": "separator"` message into the conversation
- On next LLM call, only messages **after** the last separator are sent
- Acts as a manual context reset -- discards everything before the separator
- No automatic triggering

### Max Rounds Truncation (lines 436-484)

- Per-assistant `max_rounds` config in `config/models_config.yaml` (currently all `null`)
- When enabled, keeps only the most recent N rounds (1 round = 1 user + 1 assistant message)
- Always preserves the system prompt
- Simple arithmetic: `keep_count = max_rounds * 2`

### What We Don't Have Yet

- Pre-LLM token counting
- Automatic sliding window based on token limits
- LLM-driven context compression / summarization
- Token limit enforcement or overflow detection

---

## LobeChat Approach

**Prompt-driven structured summarization with reversible compression groups and configurable model.**

> Source: `learn_proj/lobehub/` -- based on direct source code analysis of the monorepo.

### Complete Pipeline

```
User sends message
  -> GeneralChatAgent: user_input phase
  -> shouldCompress(messages, { maxWindowToken }) checks token threshold
  -> Exceeds threshold? -> emit 'compress_context' instruction
  -> createCompressionGroup (DB: create group record, mark messages with messageGroupId)
  -> chainCompressContext (build compression prompt from system + formatted history)
  -> Stream LLM call to generate structured summary
  -> finalizeCompression (save summary content to DB)
  -> CompressedGroupRoleTransform (wrap summary in XML tag, convert role to 'user' for LLM)
```

### Token Counting + Threshold

**File:** `packages/agent-runtime/src/utils/tokenCounter.ts`

- Compression check runs **before** each LLM call, not after
- Default threshold: `128,000 * 0.5 = 64,000 tokens`
- Configurable via `compressionConfig.maxWindowToken` per agent

```typescript
export const DEFAULT_MAX_CONTEXT = 128_000;   // 128k tokens
export const DEFAULT_THRESHOLD_RATIO = 0.5;    // triggers at 50%
```

**Differentiated token counting strategy:**
- **Assistant messages**: uses exact value from `metadata.usage.totalOutputTokens` (API-reported)
- **User/System messages**: uses `tokenx` library estimation (no exact value available)
- This is a practical optimization -- use exact values where available, estimate elsewhere

### Structured Compression via Prompt Engineering

**File:** `packages/prompts/src/prompts/compressContext/index.ts`

LobeChat's "structured compression" is entirely **prompt-driven** -- the LLM is instructed to output a structured summary with fixed sections. There is no code-level topic segmentation or message grouping algorithm.

**Required output sections (omit empty ones):**

| Section | Purpose |
|---------|---------|
| Context | Background and setup, 1-2 sentences max |
| Key Information | Facts, specs, technical details, names, file paths, URLs |
| Decisions & Conclusions | Agreed solutions, approaches, final conclusions |
| Action Items | Tasks, next steps, pending items |
| Code & Technical | Preserved essential code snippets in code blocks |

**Three-tier rule system in the prompt:**

- **MUST**: Same language as conversation; preserve ALL technical terms, code identifiers, file paths, proper nouns exactly; maintain factual accuracy; keep essential code snippets
- **SHOULD**: 60-80% compression ratio (summary = 20-40% of original); bullet points; chronological order; consolidate repeated info
- **MAY**: Omit greetings/pleasantries/filler; combine related points; abbreviate obvious context

**Design intent** (stated in prompt): "The summary will be injected into a new conversation as context. Recipient should be able to continue the conversation seamlessly." -- the goal is conversation continuity, not just note-taking.

### Message Formatting Before Compression

**File:** `packages/prompts/src/prompts/chatMessages/index.ts`

Messages are formatted as XML before being sent to the compression LLM:

```xml
<chat_history>
<user>How do I set up authentication?</user>
<assistant>You can use JWT tokens...</assistant>
</chat_history>
```

The chain assembly (`packages/prompts/src/chains/compressContext.ts`):
- System message = structured compression prompt (rules + output format)
- User message = `<chat_history>...</chat_history>` + "Please compress the above conversation history."

### Three-Layer Important Content Preservation

**Layer 1: LLM judgment (prompt-driven)**
- The MUST rules in the compression prompt instruct the LLM to preserve technical terms, code, file paths, proper nouns
- Effectiveness depends entirely on LLM capability -- no programmatic guarantee

**Layer 2: Pinned messages (user-controlled)**
- Users can mark messages as favorite/pinned
- Pinned messages are extracted separately and stored in `pinnedMessages` array on the compressedGroup
- These are NOT fed into the summarization -- they are preserved verbatim alongside the summary

```typescript
// packages/database/src/models/message.ts (lines 847-870)
const pinnedMessages = groupMsgIds
  .filter((id) => favoriteMap.get(id) === true)
  .map((id) => {
    const m = messageMap.get(id);
    return { content: m.content, id: m.id, role: m.role, ... };
  });
```

**Layer 3: Original messages retained (reversible compression)**
- Messages are NOT deleted from the database -- only marked with `messageGroupId`
- UI shows two tabs: Summary (generated) and History (original conversation)
- User can **cancel compression** to fully restore original messages

```typescript
// Mark as compressed (soft, reversible)
await this.db.update(messages)
  .set({ messageGroupId: groupId })
  .where(inArray(messages.id, messageIds));

// Cancel: unmark messages
await this.db.update(messages)
  .set({ messageGroupId: null })
  .where(inArray(messages.id, messageIds));
```

### Compressed Summary Injection into LLM

**File:** `packages/context-engine/src/processors/CompressedGroupRoleTransform.ts`

The compressedGroup is transformed before sending to the LLM:
- Role changed from `compressedGroup` to `user` (models don't understand custom roles)
- Content wrapped in `<compressed_history_summary>` XML tag to distinguish from real user messages

```typescript
if (msg.role === 'compressedGroup') {
  return {
    ...msg,
    content: `<compressed_history_summary>\n${msg.content}\n</compressed_history_summary>`,
    role: 'user',
  };
}
```

### Conversation Tree Integrity After Compression

**File:** `packages/conversation-flow/src/indexing.ts`

After compression, new messages need to link correctly in the conversation tree:
- The compressedGroup stores `lastMessageId` (the last message before compression)
- New messages whose `parentId` points to `lastMessageId` are automatically redirected to the compressedGroup node
- This prevents orphaned messages after compression

### Configurable Summarization Model

- Compression can use a different (cheaper/faster) model than the main chat model
- Configured via `modelRuntimeConfig.compressionModel` with separate `model` and `provider` fields
- Allows cost optimization: e.g., use GPT-4o-mini for compression while using Claude for main conversation

### What LobeChat Does NOT Have

- **No topic-based segmentation** -- all messages are compressed into a single summary in one pass
- **No sliding window** -- the current codebase uses threshold-based compression, not `historyCount`-based windowing (this may have existed in older versions)
- **No incremental/running summary** -- each compression generates a fresh summary from all messages
- **No per-message importance scoring** -- importance is determined by LLM judgment and user pinning, not algorithmic scoring

### Key Takeaway

LobeChat's approach is a well-engineered **prompt-driven structured summarization** system. The sophistication lies in: (1) the carefully designed compression prompt with three-tier rules, (2) the three-layer content preservation mechanism (LLM + pinned + reversible), and (3) production-grade concerns like streaming UI updates, conversation tree integrity, and configurable compression model. However, it does NOT implement topic-based segmentation or algorithmic importance scoring -- these would need to be designed from scratch if desired.

---

## Chatbox Approach

**Simple sliding window with manual LLM compression.**

### Sliding Window

- Default: last 6 messages (`maxContextMessageCount`)
- User-configurable in settings
- Simple and predictable

### Manual LLM Compression

- User-triggered only -- no automatic compression
- Archives old messages into a "thread"
- Thread is replaced with a system prompt + compressed summary
- Compressed summary includes continuation-ready instructions so the LLM can pick up where it left off

### Key Takeaway

Simplest approach. Good baseline -- sliding window covers most cases, manual compression as escape hatch for long conversations.

---

## OpenCode Approach

**Agent-oriented with overflow detection and tool output pruning.**

### Overflow Detection

- Monitors context usage, triggers at ~95% of context window capacity
- More aggressive threshold than Claude Code (95% vs 75%)

### Tool Output Pruning

- Targets large tool outputs (file reads, command results, etc.)
- Protects the most recent 40K tokens of tool output from pruning
- Only prunes if savings exceed 20K tokens (avoids thrashing)
- Replaces pruned outputs with `[output too long, was trimmed]` placeholder

### Compaction Agent

- Dedicated agent generates a detailed continuation prompt
- Summary includes: current task, completed steps, remaining work, key findings
- Acts as a "handoff document" for the next context window

### Plugin System

- Dynamic context pruning via plugins
- Allows custom pruning strategies per tool type

### Key Takeaway

Tool output pruning is highly relevant for agent systems where tool calls dominate context. The compaction agent pattern produces high-quality summaries because it is purpose-built for continuation.

---

## Claude Code Approach

**Auto-compact with hierarchical context management.**

### Auto-Compact

- Triggers at ~75% context window usage
- Automatic -- no user intervention needed
- Conservative threshold leaves headroom for the response

### `/compact` Command

- Manual trigger with optional custom focus (e.g., `/compact focus on the auth refactor`)
- Achieves 50-87% token savings depending on conversation length
- Custom focus allows the user to control what gets preserved

### Task Tool (Hierarchical Context)

- Spawns sub-agents with fresh 200K context windows
- Parent agent delegates complex sub-tasks to child agents
- Each child gets a clean context, returns only the result
- Effectively multiplies available context

### Context Editing

- Automated removal of stale tool call results
- 84% token reduction reported in some cases
- Keeps conversation structure but removes large intermediate outputs

### Key Takeaway

The hierarchical sub-agent pattern is the most scalable approach. Auto-compact at 75% is a good default threshold. The combination of automatic + manual compression gives users control without requiring attention.

---

## LangGraph Native Options

**Most directly applicable to our stack.**

### `trim_messages` Utility

Built-in LangChain utility for token-based message windowing:

```python
from langchain_core.messages import trim_messages

trimmed = trim_messages(
    messages,
    max_tokens=4000,
    token_counter=model.get_num_tokens,  # or len for simple char count
    strategy="last",           # keep most recent messages
    start_on="human",          # ensure window starts with a human message
    include_system=True,       # always preserve system prompt
    allow_partial=False,       # don't split messages mid-content
)
```

- Drop-in replacement for raw message lists
- Supports both `"first"` and `"last"` strategies
- Handles system message preservation automatically

### `SummarizationNode` from `langmem`

Pre-built LangGraph node for automatic summarization:

```python
from langmem import SummarizationNode

summarization_node = SummarizationNode(
    model=summarization_model,
    max_tokens=384,
    max_tokens_before_summary=2000,
    max_summary_tokens=128,
)

# Wire into the graph
graph.add_node("summarize", summarization_node)
graph.add_edge("chat", "summarize")
```

- Runs as a post-chat node in the graph
- Maintains a running summary in graph state
- Configurable token thresholds for when to trigger
- Summary is injected as a system message on next turn

### Custom Summarization Node

For more control, build a custom node using `RemoveMessage`:

```python
from langchain_core.messages import RemoveMessage

def summarize_conversation(state):
    summary_prompt = f"Summarize this conversation:\n{format_messages(state['messages'])}"
    summary = model.invoke(summary_prompt)

    # Remove old messages, keep summary
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {
        "messages": delete_messages,
        "summary": summary.content,
    }
```

- Full control over summarization prompt and strategy
- `RemoveMessage` cleanly removes messages from LangGraph state
- Can preserve specific messages (e.g., last 2) alongside the summary

### Key Takeaway

`trim_messages` is the lowest-effort win -- can be added immediately as a safety net. `SummarizationNode` from `langmem` provides automatic summarization without custom code. Custom nodes give full control for our specific needs (markdown storage, YAML frontmatter).

---

## Recommended Implementation Strategy

A phased approach, ordered by impact and complexity:

### Phase 1: Safety Net (Low effort)

- **Add `trim_messages`** before every LLM call as a hard token limit
- Prevents context overflow errors immediately
- No UX changes needed

### Phase 2: Token Counting + Awareness (Medium effort)

- **Count tokens before LLM calls** using the model's tokenizer
- Log token usage to `logs/server.log` for monitoring
- Surface token count in the frontend (optional)

### Phase 3: Automatic Summarization (Higher effort)

- **Add a summarization step** when token count exceeds threshold (e.g., 75% of model's context window)
- Use `SummarizationNode` or a custom LangGraph node
- Store running summary in conversation YAML frontmatter
- Inject summary as context on next turn

### Phase 4: Tool Output Pruning (Agent-specific)

- **Prune large tool outputs** from older turns
- Protect recent tool outputs (last N tokens)
- Replace pruned outputs with placeholder text
- Most relevant if/when tool usage becomes heavy

### Phase 5: Hierarchical Context (Advanced)

- **Sub-agent delegation** for complex multi-step tasks
- Each sub-agent gets a fresh context window
- Parent coordinates and aggregates results

---

## Future TODO Checklist

- [ ] Add `trim_messages` as a safety net before LLM calls
- [ ] Implement pre-LLM token counting and logging
- [ ] Enable `max_rounds` defaults in `models_config.yaml` as interim measure
- [ ] Build automatic summarization node (evaluate `langmem.SummarizationNode` vs custom)
- [ ] Design summary storage format in conversation YAML frontmatter
- [ ] Add configurable compression threshold (default: 75% of context window)
- [ ] Support configurable summarization model (use cheaper model for compression)
- [ ] Add tool output pruning for agent workflows
- [ ] Surface token usage metrics in frontend
- [ ] Evaluate topic-based segmentation (custom design -- LobeChat does NOT implement this despite earlier notes)
- [ ] Consider three-layer preservation: LLM prompt rules + user pinning + reversible compression
- [ ] Use XML tag wrapping (`<compressed_history_summary>`) to distinguish summary from real messages
