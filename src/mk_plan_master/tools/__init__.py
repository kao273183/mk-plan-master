"""Tool implementations. One file per logical group; routed from server.py.

Groups:
    - initiatives     — get_plan_source_info, list_initiatives, fetch_initiative
    - scoring         — score_initiative, rank_backlog
    - bridge          — generate_spec_draft (hand-off to mk-spec-master.parse_spec)
    - roadmap         — generate_roadmap, analyze_roadmap_balance
    - plan_knowledge  — init_plan_knowledge, get_plan_context
    - history         — get_planning_history, get_decision_signature
                        + archive_snapshot (called from rank_backlog)
    - telemetry       — get_telemetry + _Timer (used by server.call_tool)
"""
