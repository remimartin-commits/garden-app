"""Terminal vibe-coding session (style quiz, generate, refine loop)."""

from __future__ import annotations

import sys
from typing import TypeVar

from openai import OpenAI

from app.config import get_settings
from app.style_store import (
    load_saved_style,
    save_style_with_optional_backup,
    style_profile_path,
)
from app.vibe import (
    VibeStyleProfile,
    append_refinement_turn,
    build_style_contract,
    build_vibe_messages,
    guide_intro,
    guide_prompting_cheatsheet,
)

T = TypeVar("T")


def _ask_choice(label: str, options: list[tuple[str, T]], default: int = 1) -> T:
    print(f"\n{label}")
    for i, (title, _) in enumerate(options, start=1):
        print(f"  {i}. {title}")
    while True:
        raw = input(f"Choice [1-{len(options)}] (default {default}): ").strip()
        if not raw:
            return options[default - 1][1]
        if not raw.isdigit():
            print("Enter a number.")
            continue
        n = int(raw)
        if 1 <= n <= len(options):
            return options[n - 1][1]
        print("Out of range.")


def _read_feedback() -> str:
    print("\nFeedback for the model (empty line ends input; blank aborts):")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _want_another_round() -> bool:
    r = input("\nRefine again? [y/N]: ").strip().lower()
    return r in ("y", "yes")


def interactive_profile() -> VibeStyleProfile:
    pace = _ask_choice(
        "Pace — how should the code feel?",
        [
            ("Fast / loose (ship now, note rough edges)", "fast_loose"),
            ("Steady / pragmatic (balance clarity and speed)", "steady_pragmatic"),
            ("Careful (readability and edge cases first)", "careful"),
        ],
    )
    verbosity = _ask_choice(
        "Verbosity — how much explanation?",
        [
            ("Mostly code", "code_only"),
            ("Short comments on tricky bits", "brief_notes"),
            ("Teach along with brief explanations OK", "teach_along"),
        ],
    )
    structure = _ask_choice(
        "Structure — files and modules?",
        [
            ("Single file unless impossible", "one_file"),
            ("Split when it genuinely helps", "split_when_helpful"),
        ],
    )
    types = _ask_choice(
        "Type hints (Python-style; adapt mentally for other langs)?",
        [
            ("Full where helpful", "full"),
            ("Some (public / tricky only)", "some"),
            ("Skip unless forced by language", "none"),
        ],
    )
    naming = _ask_choice(
        "Naming style?",
        [
            ("Short when obvious", "short"),
            ("Balanced readability", "balanced"),
            ("Explicit / verbose names", "explicit"),
        ],
    )
    errors = _ask_choice(
        "Error handling?",
        [
            ("Minimal — fail naturally", "minimal"),
            ("Practical — likely failures", "practical"),
            ("Defensive — guard inputs", "defensive"),
        ],
    )
    deps = _ask_choice(
        "Dependencies?",
        [
            ("Standard library only by default", "stdlib_only"),
            ("Common ecosystem libs OK", "common_libs_ok"),
        ],
    )
    extras = input(
        "\nAny extra vibe notes? (e.g. 'no classes', 'pytest style tests') "
        "[optional]: "
    ).strip()
    change_documentation = _ask_choice(
        "When you refine, should Code Llama explain its own edits step-by-step?",
        [
            ("Yes — ## Changes then ## Updated solution", "step_by_step"),
            ("No — updated solution only", "off"),
        ],
        default=1,
    )
    return VibeStyleProfile(
        pace=pace,
        verbosity=verbosity,
        structure=structure,
        types=types,
        naming=naming,
        errors=errors,
        deps=deps,
        extras=extras,
        change_documentation=change_documentation,
    )


def run_terminal_session() -> None:
    settings = get_settings()
    print(guide_intro())

    saved = load_saved_style(settings)
    if saved is not None:
        path = style_profile_path(settings)
        print(f"\nFound saved style at:\n  {path.resolve()}")
        print("(Same file as the web dashboard uses.)")
        use_saved = (
            input("\nUse saved style? [Y/n]: ").strip().lower()
        )
        if use_saved in ("n", "no"):
            input("\nPress Enter to configure a new style…")
            profile = interactive_profile()
        else:
            profile = saved
    else:
        input("\nPress Enter to configure your style…")
        profile = interactive_profile()

    print("\n--- Your style contract ---")
    print(build_style_contract(profile))

    persist = (
        input(
            "\nSave this style as default (shared with dashboard)? [y/N]: "
        )
        .strip()
        .lower()
    )
    if persist in ("y", "yes"):
        result = save_style_with_optional_backup(settings, profile)
        suffix = "(backup queued)" if result["queued"] else "(local only or backup sent)"
        print(f"Wrote {style_profile_path(settings)} — {suffix}")

    task = input(
        "\nDescribe what you want built (one concrete task):\n> "
    ).strip()
    if not task:
        print("No task given; exiting.")
        sys.exit(1)

    print("\n--- Prompting cheatsheet (save this for later) ---")
    print(guide_prompting_cheatsheet())

    client = OpenAI(
        base_url=settings.ollama_base_url.rstrip("/"),
        api_key=settings.ollama_api_key,
    )
    messages = build_vibe_messages(profile, task)
    round_num = 0
    while True:
        round_num += 1
        label = "initial generation" if round_num == 1 else f"refinement round {round_num - 1}"
        print(f"\nCalling model `{settings.chat_model}` ({label})…\n")
        completion = client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            temperature=0.45,
        )
        out = completion.choices[0].message.content or ""
        print("--- Model output ---")
        print(out.strip())

        if not _want_another_round():
            break
        fb = _read_feedback()
        if not fb:
            print("No feedback; done.")
            break
        messages = append_refinement_turn(
            messages,
            out,
            fb,
            change_documentation=profile.change_documentation,
        )
