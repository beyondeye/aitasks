from dataclasses import dataclass, field


@dataclass
class AnnotationRange:
    start_line: int
    end_line: int
    task_ids: list[str] = field(default_factory=list)
    commit_hashes: list[str] = field(default_factory=list)
    commit_messages: list[str] = field(default_factory=list)


@dataclass
class FileExplainData:
    file_path: str
    annotations: list[AnnotationRange] = field(default_factory=list)
    commit_timeline: list[dict] = field(default_factory=list)
    generated_at: str = ""
    is_binary: bool = False


@dataclass
class TaskDetailContent:
    task_id: str
    plan_content: str = ""
    task_content: str = ""
    has_plan: bool = False
    has_task: bool = False


@dataclass
class ExplainRunInfo:
    run_dir: str
    directory_key: str
    timestamp: str
    file_count: int = 0
