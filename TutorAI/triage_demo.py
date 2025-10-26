# chat_triage.py
from agents import Agent, InputGuardrail, GuardrailFunctionOutput, Runner
from agents.exceptions import InputGuardrailTripwireTriggered
from pydantic import BaseModel
import asyncio
import sys

# -------- Guardrail output schema --------
class HomeworkOutput(BaseModel):
    is_homework: bool
    reasoning: str

# -------- Agents --------
guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking about homework. "
                 "Return is_homework=True if the question looks like homework; otherwise False.",
    output_type=HomeworkOutput,
)

math_tutor_agent = Agent(
    name="Math Tutor",
    handoff_description="Specialist agent for math questions",
    instructions="You provide help with math problems. Explain your reasoning step-by-step and include a simple example.",
)

history_tutor_agent = Agent(
    name="History Tutor",
    handoff_description="Specialist agent for historical questions",
    instructions="You provide assistance with history questions. Explain important events and context clearly.",
)

# -------- Input guardrail function --------
async def homework_guardrail(ctx, agent, input_data):
    """
    Runs before triage. If not homework, tripwire triggers and the input is blocked.
    """
    # Ask the guardrail agent to classify the input
    result = await Runner.run(guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(HomeworkOutput)

    # Tripwire triggers when NOT homework
    return GuardrailFunctionOutput(
        output_info=final_output,
        tripwire_triggered=not final_output.is_homework,
    )

# -------- Triage agent with handoffs + guardrail --------
triage_agent = Agent(
    name="Triage Agent",
    instructions="Determine which tutor to use for this homework question (math vs. history). "
                 "If it's math, hand off to Math Tutor. If it's history, hand off to History Tutor.",
    handoffs=[history_tutor_agent, math_tutor_agent],
    input_guardrails=[InputGuardrail(guardrail_function=homework_guardrail)],
)

# -------- Helpers --------
def _render_answer(run_result) -> str:
    """
    Be forgiving about result shape; prefer text if available.
    """
    # Some SDK versions expose final_output_text; others just final_output (str/dict)
    text = getattr(run_result, "final_output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    out = getattr(run_result, "final_output", None)
    if out is None:
        return "(no output)"
    return out if isinstance(out, str) else str(out)

# -------- Chat loop --------
async def chat():
    print("Agent chat ready. Type your question (or 'exit' to quit).")
    print("Note: Non-homework questions will be blocked by the guardrail.\n")

    while True:
        try:
            # Non-blocking input for asyncio
            user_q = await asyncio.to_thread(input, "You: ")
            if not user_q.strip():
                continue
            if user_q.strip().lower() in {"exit", "quit", "q"}:
                print("Bye!")
                return

            try:
                result = await Runner.run(triage_agent, user_q)
                print("Agent:", _render_answer(result), "\n")
            except InputGuardrailTripwireTriggered as e:
                # Input was blocked by the guardrail
                # If the guardrail provided details, show a friendly message.
                msg = str(e) or "Blocked by guardrail (not recognized as homework)."
                print("🚫", msg, "\n")

        except KeyboardInterrupt:
            print("\nInterrupted. Bye!")
            return
        except EOFError:
            print("\nBye!")
            return
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)

# -------- Entry point --------
if __name__ == "__main__":
    asyncio.run(chat())
