from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]

api_path = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "api.py"
)

trace_path = (
    ROOT
    / "IA_Local"
    / "scripts"
    / "enterprise_ai"
    / "traceability.py"
)

api = api_path.read_text(encoding="utf-8")
trace = trace_path.read_text(encoding="utf-8")

ast.parse(api)
ast.parse(trace)

assert "def bind(self, trace_id: str)" in trace
assert "with self.bind(trace_id):" in trace

start = api.index(
    '@router.post("/api/enterprise/chat/stream")'
)

end = api.index(
    '@router.get("/api/enterprise/memories")',
    start,
)

route = api[start:end]

assert "traceability.scope(" not in route
assert "components.traceability.start(" in route
assert "components.traceability.bind(" in route

assert "event = next(stream_iter)" in route
assert "close_stream()" in route

assert route.count(
    'event_type == "done"'
) == 1

assert 'finish_trace("completed")' in route
assert 'finish_trace("cancelled")' in route

assert "components.service.chat(" in route

assert (
    "with components.traceability.bind("
    in route
)

assert (
    "result = components.service.chat("
    in route
)

done_branch = route[
    route.index('event_type == "done"'):
]

complete_pos = done_branch.index(
    'finish_trace("completed")'
)

yield_pos = done_branch.index(
    "yield json.dumps(",
    complete_pos,
)

return_pos = done_branch.index(
    "return",
    yield_pos,
)

assert complete_pos < yield_pos < return_pos

next_pos = route.index(
    "event = next(stream_iter)"
)

bind_before_next = route.rfind(
    "with components.traceability.bind(",
    0,
    next_pos,
)

assert bind_before_next >= 0

yield_after_next = route.index(
    "yield json.dumps(",
    next_pos,
)

assert bind_before_next < next_pos < yield_after_next

print(
    "R10_24A2_STREAM_TRACE_CONTEXT=PASS"
)
print(
    "TRACE_BIND_HELPER=PASS"
)
print(
    "PER_RESUME_BIND=PASS"
)
print(
    "FALLBACK_TRACE_CONTEXT=PASS"
)
print(
    "TRACE_COMPLETED_BEFORE_DONE=PASS"
)