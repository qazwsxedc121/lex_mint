#!/usr/bin/env python3
"""Run CRUD-RAG end-to-end benchmark (retrieve + generate + score)."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import jieba
import yaml
from langchain_core.messages import HumanMessage

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.services.model_config_service import ModelConfigService  # noqa: E402
from src.api.services.rag_service import RagResult, RagService  # noqa: E402


TASK_TO_QUERY_FIELD: Dict[str, str] = {
    "event_summary": "event",
    "continuing_writing": "beginning",
    "hallu_modified": "newsBeginning",
    "questanswer_1doc": "questions",
    "questanswer_2docs": "questions",
    "questanswer_3docs": "questions",
}

TASK_TO_GT_FIELD: Dict[str, str] = {
    "event_summary": "summary",
    "continuing_writing": "continuing",
    "hallu_modified": "hallucinatedMod",
    "questanswer_1doc": "answers",
    "questanswer_2docs": "answers",
    "questanswer_3docs": "answers",
}

TASK_TO_PROMPT_TEMPLATE: Dict[str, str] = {
    "event_summary": "summary.txt",
    "continuing_writing": "continue_writing.txt",
    "hallu_modified": "hallu_mod.txt",
    "questanswer_1doc": "quest_answer.txt",
    "questanswer_2docs": "quest_answer.txt",
    "questanswer_3docs": "quest_answer.txt",
}


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be an object: {path}")
    return data


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _read_prompt_templates(prompt_dir: Path) -> Dict[str, str]:
    templates: Dict[str, str] = {}
    needed = set(TASK_TO_PROMPT_TEMPLATE.values()) | {"quest_eval_gen.txt", "quest_eval_answer.txt"}
    for filename in sorted(needed):
        file_path = prompt_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template missing: {file_path}")
        templates[filename] = file_path.read_text(encoding="utf-8")
    return templates


def _extract_response_text(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    pattern = re.compile(r"<response>\s*(.*?)\s*</response>", flags=re.IGNORECASE | re.DOTALL)
    matches = pattern.findall(text)
    if matches:
        return "\n".join(m.strip() for m in matches if m.strip()).strip()
    return text


def _extract_response_blocks(raw: str) -> List[str]:
    pattern = re.compile(r"<response>\s*(.*?)\s*</response>", flags=re.IGNORECASE | re.DOTALL)
    blocks = [m.strip() for m in pattern.findall(str(raw or "")) if m.strip()]
    if blocks:
        return blocks
    text = str(raw or "").strip()
    return [text] if text else []


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    content = str(text or "").strip()
    if not content:
        return None
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
    content = fenced or content
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = content.find("{")
    while start >= 0:
        depth = 0
        for idx in range(start, len(content)):
            ch = content[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    snippet = content[start : idx + 1]
                    try:
                        parsed = json.loads(snippet)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        break
        start = content.find("{", start + 1)
    return None


def _tokenize_zh(text: str) -> List[str]:
    return [tok for tok in jieba.cut(str(text or "")) if tok.strip()]


def _get_ngrams(tokens: Sequence[str], n: int) -> Counter:
    if n <= 0 or len(tokens) < n:
        return Counter()
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


def _bleu_scores(pred: str, ref: str) -> Dict[str, float]:
    pred_tokens = _tokenize_zh(pred)
    ref_tokens = _tokenize_zh(ref)
    if not pred_tokens or not ref_tokens:
        return {"bleu": 0.0, "bleu_1": 0.0, "bleu_2": 0.0, "bleu_3": 0.0, "bleu_4": 0.0}

    precisions: List[float] = []
    for n in (1, 2, 3, 4):
        pred_ngrams = _get_ngrams(pred_tokens, n)
        ref_ngrams = _get_ngrams(ref_tokens, n)
        if not pred_ngrams:
            precisions.append(0.0)
            continue
        overlap = 0
        for gram, count in pred_ngrams.items():
            overlap += min(count, ref_ngrams.get(gram, 0))
        precisions.append(overlap / max(1, sum(pred_ngrams.values())))

    if min(precisions) <= 0:
        bleu = 0.0
    else:
        pred_len = len(pred_tokens)
        ref_len = len(ref_tokens)
        if pred_len == 0:
            bleu = 0.0
        else:
            bp = 1.0 if pred_len > ref_len else math.exp(1.0 - (ref_len / pred_len))
            bleu = bp * math.exp(sum(math.log(p) for p in precisions) / 4.0)

    return {
        "bleu": float(bleu),
        "bleu_1": float(precisions[0]),
        "bleu_2": float(precisions[1]),
        "bleu_3": float(precisions[2]),
        "bleu_4": float(precisions[3]),
    }


def _lcs_len(a: Sequence[str], b: Sequence[str]) -> int:
    if not a or not b:
        return 0
    dp = [0] * (len(b) + 1)
    for tok_a in a:
        prev = 0
        for idx_b, tok_b in enumerate(b, start=1):
            cur = dp[idx_b]
            if tok_a == tok_b:
                dp[idx_b] = prev + 1
            else:
                dp[idx_b] = max(dp[idx_b], dp[idx_b - 1])
            prev = cur
    return dp[-1]


def _rouge_l(pred: str, ref: str) -> float:
    pred_tokens = _tokenize_zh(pred)
    ref_tokens = _tokenize_zh(ref)
    if not pred_tokens or not ref_tokens:
        return 0.0
    lcs = _lcs_len(pred_tokens, ref_tokens)
    if lcs <= 0:
        return 0.0
    precision = lcs / len(pred_tokens)
    recall = lcs / len(ref_tokens)
    if precision + recall <= 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def _word_f1(reference: str, prediction: str) -> float:
    ref_toks = _tokenize_zh(reference)
    pred_toks = _tokenize_zh(prediction)
    if not ref_toks or not pred_toks:
        return float(ref_toks == pred_toks)
    common = Counter(ref_toks) & Counter(pred_toks)
    same = sum(common.values())
    if same <= 0:
        return 0.0
    p = same / len(pred_toks)
    r = same / len(ref_toks)
    if p + r <= 0:
        return 0.0
    return 2.0 * p * r / (p + r)


def _build_search_documents(results: Sequence[RagResult]) -> str:
    parts: List[str] = []
    for idx, item in enumerate(results, start=1):
        body = str(item.content or "").strip()
        if not body:
            continue
        parts.append(f"[{idx}] {body}")
    return "\n\n".join(parts)


class LlmCaller:
    def __init__(
        self,
        *,
        model_id: str,
        temperature: float,
        max_tokens: int,
        disable_thinking: bool = False,
    ) -> None:
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.disable_thinking = disable_thinking
        self.model_service = ModelConfigService()
        self.llm = self.model_service.get_llm_instance(
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if self.disable_thinking:
            # DashScope/Qwen supports disabling thinking via extra_body.
            self.llm = self.llm.bind(extra_body={"enable_thinking": False})

    def invoke(self, prompt: str) -> str:
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        if isinstance(content, str):
            return content
        return str(content or "")


class QuestEvalScorer:
    def __init__(
        self,
        *,
        llm: LlmCaller,
        templates: Dict[str, str],
        cache: Optional[Dict[str, Any]] = None,
        max_questions: Optional[int] = None,
    ) -> None:
        self.llm = llm
        self.templates = templates
        self.cache = cache if cache is not None else {}
        self.max_questions = max_questions
        self.json_response_example = (
            '{"key_info": ["新增并网光伏发电容量1060万千瓦", "四分之一"], '
            '"question": ["2014年中国新增并网光伏发电容量是多少？", "2014年新增容量约占全球的几分之几？"]}'
        )

    def _question_generation(self, ground_truth_text: str) -> Dict[str, Any]:
        prompt = self.templates["quest_eval_gen.txt"].format(
            json_response=self.json_response_example,
            news=ground_truth_text,
        )
        raw = self.llm.invoke(prompt)
        parsed = _extract_first_json_object(raw)
        if not parsed:
            raise ValueError("quest_eval_gen returned non-JSON payload")
        questions = parsed.get("question")
        if not isinstance(questions, list):
            raise ValueError("quest_eval_gen JSON missing 'question' list")
        cleaned_questions = [str(item).strip() for item in questions if str(item).strip()]
        if self.max_questions is not None and self.max_questions > 0:
            cleaned_questions = cleaned_questions[: self.max_questions]
        parsed["question"] = cleaned_questions
        return parsed

    def _question_answer(self, context_text: str, questions: Sequence[str]) -> List[str]:
        prompt = self.templates["quest_eval_answer.txt"].format(
            context=context_text,
            questions=json.dumps(list(questions), ensure_ascii=False),
        )
        raw = self.llm.invoke(prompt)
        answers = _extract_response_blocks(raw)
        if len(answers) < len(questions):
            answers.extend(["无法推断"] * (len(questions) - len(answers)))
        if len(answers) > len(questions):
            answers = answers[: len(questions)]
        return answers

    def score(
        self,
        *,
        cache_key: str,
        ground_truth_text: str,
        generated_text: str,
    ) -> Tuple[float, float, Dict[str, Any]]:
        if cache_key in self.cache:
            payload = dict(self.cache[cache_key])
        else:
            payload = self._question_generation(ground_truth_text)
            questions = payload.get("question") or []
            answers_gt4gt = self._question_answer(ground_truth_text, questions)
            payload["answers"] = answers_gt4gt
            self.cache[cache_key] = payload

        questions = [str(item).strip() for item in (payload.get("question") or []) if str(item).strip()]
        answers_gt4gt = [str(item).strip() for item in (payload.get("answers") or [])]
        if len(answers_gt4gt) != len(questions):
            answers_gt4gt = self._question_answer(ground_truth_text, questions)
            payload["answers"] = answers_gt4gt
            self.cache[cache_key] = payload
        answers_gm4gt = self._question_answer(generated_text, questions)

        valid_indices = [idx for idx, value in enumerate(answers_gt4gt) if value != "无法推断"]
        if not valid_indices:
            return 0.0, 0.0, {
                "questions_gt": questions,
                "answers_gt4gt": answers_gt4gt,
                "answers_gm4gt": answers_gm4gt,
            }

        gt_filtered = [answers_gt4gt[idx] for idx in valid_indices]
        gm_filtered = [answers_gm4gt[idx] for idx in valid_indices]
        if not gm_filtered:
            return 0.0, 0.0, {
                "questions_gt": questions,
                "answers_gt4gt": answers_gt4gt,
                "answers_gm4gt": answers_gm4gt,
            }

        undetermined_ratio = gm_filtered.count("无法推断") / max(1, len(gm_filtered))
        recall = 1.0 - undetermined_ratio

        non_undetermined_idx = [idx for idx, value in enumerate(gm_filtered) if value != "无法推断"]
        if not non_undetermined_idx:
            avg_f1 = 0.0
        else:
            gt_answered = [gt_filtered[idx] for idx in non_undetermined_idx]
            gm_answered = [gm_filtered[idx] for idx in non_undetermined_idx]
            avg_f1 = mean(_word_f1(gt, gm) for gt, gm in zip(gt_answered, gm_answered))

        return float(avg_f1), float(recall), {
            "questions_gt": questions,
            "answers_gt4gt": answers_gt4gt,
            "answers_gm4gt": answers_gm4gt,
        }


def _build_task_prompt(task_name: str, row: Dict[str, Any], search_documents: str, templates: Dict[str, str]) -> str:
    filename = TASK_TO_PROMPT_TEMPLATE[task_name]
    template = templates[filename]
    if task_name == "event_summary":
        return template.format(event=str(row.get("event", "")), search_documents=search_documents)
    if task_name == "continuing_writing":
        return template.format(beginning_text=str(row.get("beginning", "")), search_documents=search_documents)
    if task_name == "hallu_modified":
        return template.format(
            begin=str(row.get("newsBeginning", "")),
            hallu_continue=str(row.get("hallucinatedContinuation", "")),
            search_documents=search_documents,
        )
    return template.format(question=str(row.get("questions", "")), search_documents=search_documents)


def _summarize_cases(cases: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    valid = [row for row in cases if not row.get("error")]
    if not valid:
        return {
            "case_count": 0,
            "bleu": 0.0,
            "bleu_1": 0.0,
            "bleu_2": 0.0,
            "bleu_3": 0.0,
            "bleu_4": 0.0,
            "rouge_l": 0.0,
            "ragquesteval_f1": 0.0,
            "ragquesteval_recall": 0.0,
        }
    return {
        "case_count": len(valid),
        "bleu": mean(_safe_float(row.get("bleu")) for row in valid),
        "bleu_1": mean(_safe_float(row.get("bleu_1")) for row in valid),
        "bleu_2": mean(_safe_float(row.get("bleu_2")) for row in valid),
        "bleu_3": mean(_safe_float(row.get("bleu_3")) for row in valid),
        "bleu_4": mean(_safe_float(row.get("bleu_4")) for row in valid),
        "rouge_l": mean(_safe_float(row.get("rouge_l")) for row in valid),
        "ragquesteval_f1": mean(_safe_float(row.get("ragquesteval_f1")) for row in valid),
        "ragquesteval_recall": mean(_safe_float(row.get("ragquesteval_recall")) for row in valid),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CRUD end-to-end benchmark.")
    parser.add_argument("--config", type=Path, default=Path("config/benchmarks/crud_e2e_v1.yaml"))
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task names override.")
    parser.add_argument("--per-task-max", type=int, default=None, help="Cap number of samples per task.")
    parser.add_argument("--modes", type=str, default=None, help="Comma-separated retrieval modes.")
    parser.add_argument("--model-id", type=str, default="qwen3.5-plus", help="Generation model id.")
    parser.add_argument("--questeval-model-id", type=str, default=None, help="Judge model id, default=model-id.")
    parser.add_argument("--disable-thinking", action="store_true", help="Force disable model thinking mode.")
    parser.add_argument("--max-questions", type=int, default=None, help="Optional max questions in quest-eval.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory.")
    parser.add_argument("--disable-ragquesteval", action="store_true", help="Skip quest-eval scoring.")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup only, skip calls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_all = _load_yaml(args.config)

    protocol_cfg = cfg_all.get("protocol", {}) if isinstance(cfg_all.get("protocol"), dict) else {}
    dataset_cfg = cfg_all.get("dataset", {}) if isinstance(cfg_all.get("dataset"), dict) else {}
    retrieval_cfg = cfg_all.get("retrieval", {}) if isinstance(cfg_all.get("retrieval"), dict) else {}
    generation_cfg = cfg_all.get("generation", {}) if isinstance(cfg_all.get("generation"), dict) else {}
    metrics_cfg = cfg_all.get("metrics", {}) if isinstance(cfg_all.get("metrics"), dict) else {}

    protocol_name = str(protocol_cfg.get("name") or "crud_e2e_v1")
    dataset_path = Path(str(dataset_cfg.get("split_dataset_path") or "learn_proj/CRUD_RAG/data/crud_split/split_merged.json"))
    prompt_dir = REPO_ROOT / "learn_proj" / "CRUD_RAG" / "src" / "prompts"
    kb_ids = [str(item).strip() for item in (retrieval_cfg.get("kb_ids") or []) if str(item).strip()]
    if not kb_ids:
        raise ValueError("retrieval.kb_ids must not be empty.")

    tasks = _split_csv(args.tasks) if args.tasks else list(dataset_cfg.get("tasks") or [])
    if not tasks:
        raise ValueError("No tasks configured.")

    per_task_max = args.per_task_max
    if per_task_max is None:
        cfg_max = dataset_cfg.get("per_task_max")
        per_task_max = int(cfg_max) if cfg_max is not None else 20

    modes = _split_csv(args.modes) if args.modes else [str(item).strip() for item in (retrieval_cfg.get("modes") or ["hybrid"]) if str(item).strip()]
    if not modes:
        modes = ["hybrid"]

    top_k = int(retrieval_cfg.get("top_k") or 8)
    score_threshold = _safe_float(retrieval_cfg.get("score_threshold"), 0.65)
    bm25_min_term_coverage = _safe_float(retrieval_cfg.get("bm25_min_term_coverage"), 0.35)
    temperature = _safe_float(generation_cfg.get("temperature"), 0.1)
    max_new_tokens = int(generation_cfg.get("max_new_tokens") or 1280)
    disable_thinking = bool(generation_cfg.get("disable_thinking", False) or args.disable_thinking)
    runtime_model_id = str(generation_cfg.get("runtime_model_id") or "").strip() or None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (Path("data/benchmarks") / f"{protocol_name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    templates = _read_prompt_templates(prompt_dir)
    split_data = _load_json(dataset_path)

    eval_model_id = args.model_id
    questeval_model_id = args.questeval_model_id or eval_model_id
    ragquesteval_enabled = not args.disable_ragquesteval and bool((metrics_cfg.get("ragquesteval") or {}).get("enabled", True))

    manifest = {
        "protocol_name": protocol_name,
        "config_path": str(args.config),
        "dataset_path": str(dataset_path),
        "tasks": tasks,
        "per_task_max": per_task_max,
        "modes": modes,
        "kb_ids": kb_ids,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "bm25_min_term_coverage": bm25_min_term_coverage,
        "eval_model_id": eval_model_id,
        "questeval_model_id": questeval_model_id,
        "temperature": temperature,
        "max_new_tokens": max_new_tokens,
        "disable_thinking": disable_thinking,
        "runtime_model_id": runtime_model_id,
        "ragquesteval_enabled": ragquesteval_enabled,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print(f"dry_run_ok output_dir={output_dir}")
        return

    rag_service = RagService()
    retrieval_runtime_cfg = rag_service.rag_config_service.config.retrieval
    retrieval_runtime_cfg.top_k = top_k
    retrieval_runtime_cfg.score_threshold = score_threshold
    retrieval_runtime_cfg.bm25_min_term_coverage = bm25_min_term_coverage
    retrieval_runtime_cfg.query_transform_enabled = False
    retrieval_runtime_cfg.query_transform_mode = "none"

    llm = LlmCaller(
        model_id=eval_model_id,
        temperature=temperature,
        max_tokens=max_new_tokens,
        disable_thinking=disable_thinking,
    )
    questeval_llm = llm if questeval_model_id == eval_model_id else LlmCaller(
        model_id=questeval_model_id,
        temperature=temperature,
        max_tokens=max_new_tokens,
        disable_thinking=disable_thinking,
    )
    try:
        _ = llm.invoke("Reply with OK.")
    except Exception as exc:
        raise RuntimeError(
            f"Model call preflight failed for '{eval_model_id}'. "
            "Check API key/provider config first."
        ) from exc

    cache_path = output_dir / "questeval_cache.json"
    questeval_cache: Dict[str, Any] = {}
    if cache_path.exists():
        try:
            loaded = _load_json(cache_path)
            if isinstance(loaded, dict):
                questeval_cache = loaded
        except Exception:
            questeval_cache = {}
    quest_scorer = QuestEvalScorer(
        llm=questeval_llm,
        templates=templates,
        cache=questeval_cache,
        max_questions=args.max_questions,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        global_summary: Dict[str, Any] = {
            "protocol_name": protocol_name,
            "model_id": eval_model_id,
            "questeval_model_id": questeval_model_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode_summaries": {},
        }

        for mode in modes:
            retrieval_runtime_cfg.retrieval_mode = mode
            mode_cases: Dict[str, List[Dict[str, Any]]] = {}
            mode_task_metrics: Dict[str, Dict[str, float]] = {}
            mode_valid_cases = 0

            for task_name in tasks:
                rows = list(split_data.get(task_name) or [])
                rows = rows[: max(1, int(per_task_max))]
                task_cases: List[Dict[str, Any]] = []
                print(f"mode={mode} task={task_name} cases={len(rows)}")

                for idx, row in enumerate(rows, start=1):
                    case_id = str(row.get("ID") or f"{task_name}_{idx:05d}")
                    query_field = TASK_TO_QUERY_FIELD[task_name]
                    gt_field = TASK_TO_GT_FIELD[task_name]
                    query_text = str(row.get(query_field) or "").strip()
                    ground_truth = str(row.get(gt_field) or "").strip()
                    if not query_text or not ground_truth:
                        task_cases.append({"id": case_id, "error": "missing query or ground_truth"})
                        continue

                    if task_name == "hallu_modified" and ground_truth == '\",\"msg\":\"request openai failed\"':
                        task_cases.append({"id": case_id, "error": "invalid ground_truth marker"})
                        continue

                    try:
                        retrieved, diagnostics = loop.run_until_complete(
                            rag_service.retrieve_with_diagnostics(
                                query=query_text,
                                kb_ids=kb_ids,
                                top_k=top_k,
                                score_threshold=score_threshold,
                                runtime_model_id=runtime_model_id,
                            )
                        )
                        search_documents = _build_search_documents(retrieved)
                        prompt = _build_task_prompt(task_name, row, search_documents, templates)
                        generated_raw = llm.invoke(prompt)
                        generated_text = _extract_response_text(generated_raw)

                        bleu = _bleu_scores(generated_text, ground_truth)
                        rouge_l = _rouge_l(generated_text, ground_truth)
                        quest_f1 = 0.0
                        quest_recall = 0.0
                        quest_log: Dict[str, Any] = {}
                        if ragquesteval_enabled:
                            try:
                                quest_f1, quest_recall, quest_log = quest_scorer.score(
                                    cache_key=f"{task_name}:{case_id}",
                                    ground_truth_text=ground_truth,
                                    generated_text=generated_text,
                                )
                            except Exception as quest_exc:
                                quest_log = {"error": str(quest_exc)}
                                quest_f1 = 0.0
                                quest_recall = 0.0

                        task_cases.append(
                            {
                                "id": case_id,
                                "query": query_text,
                                "ground_truth": ground_truth,
                                "generated_text": generated_text,
                                "retrieved_count": len(retrieved),
                                "bleu": bleu["bleu"],
                                "bleu_1": bleu["bleu_1"],
                                "bleu_2": bleu["bleu_2"],
                                "bleu_3": bleu["bleu_3"],
                                "bleu_4": bleu["bleu_4"],
                                "rouge_l": rouge_l,
                                "ragquesteval_f1": quest_f1,
                                "ragquesteval_recall": quest_recall,
                                "diagnostics": diagnostics,
                                "quest_eval": quest_log,
                            }
                        )
                    except Exception as exc:
                        task_cases.append({"id": case_id, "error": str(exc)})

                mode_cases[task_name] = task_cases
                mode_task_metrics[task_name] = _summarize_cases(task_cases)
                mode_valid_cases += int(mode_task_metrics[task_name]["case_count"])
                cache_path.write_text(json.dumps(questeval_cache, ensure_ascii=False, indent=2), encoding="utf-8")
                print(
                    "mode={mode} task={task} bleu={bleu:.4f} rouge_l={rouge:.4f} ragquesteval_recall={recall:.4f}".format(
                        mode=mode,
                        task=task_name,
                        bleu=mode_task_metrics[task_name]["bleu"],
                        rouge=mode_task_metrics[task_name]["rouge_l"],
                        recall=mode_task_metrics[task_name]["ragquesteval_recall"],
                    )
                )

            mode_summary = {
                "mode": mode,
                "task_metrics": mode_task_metrics,
                "overall": {
                    "bleu": mean(_safe_float(v.get("bleu")) for v in mode_task_metrics.values()) if mode_task_metrics else 0.0,
                    "rouge_l": mean(_safe_float(v.get("rouge_l")) for v in mode_task_metrics.values()) if mode_task_metrics else 0.0,
                    "ragquesteval_f1": mean(_safe_float(v.get("ragquesteval_f1")) for v in mode_task_metrics.values()) if mode_task_metrics else 0.0,
                    "ragquesteval_recall": mean(_safe_float(v.get("ragquesteval_recall")) for v in mode_task_metrics.values()) if mode_task_metrics else 0.0,
                    "task_count": len(mode_task_metrics),
                },
            }
            global_summary["mode_summaries"][mode] = mode_summary

            (output_dir / f"mode_{mode}_cases.json").write_text(
                json.dumps(mode_cases, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (output_dir / f"mode_{mode}_summary.json").write_text(
                json.dumps(mode_summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if mode_valid_cases <= 0:
                raise RuntimeError(
                    f"No valid cases for mode '{mode}'. Check API key/model config. "
                    f"See {output_dir / f'mode_{mode}_cases.json'}."
                )

        if modes:
            first_mode = modes[0]
            first_summary = global_summary["mode_summaries"][first_mode]
            compare_friendly = {
                "protocol_name": protocol_name,
                "mode": first_mode,
                "model_id": eval_model_id,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "task_metrics": first_summary["task_metrics"],
                "overall": first_summary["overall"],
            }
            (output_dir / "summary.json").write_text(
                json.dumps(compare_friendly, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        (output_dir / "summary_all_modes.json").write_text(
            json.dumps(global_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"saved={output_dir}")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
