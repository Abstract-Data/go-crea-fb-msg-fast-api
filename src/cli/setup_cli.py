"""Typer-based interactive setup CLI."""

import os

os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")

from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
from dotenv import load_dotenv

load_dotenv(_project_root / ".env")
load_dotenv(_project_root / ".env.local")

import asyncio
import questionary
import typer

from src.services.scraper import scrape_website
from src.services.reference_doc import build_reference_document
from src.db.repository import (
    create_bot_configuration,
    create_reference_document,
    create_test_session,
    get_reference_document_by_source_url,
    save_test_message,
)
from src.models.agent_models import AgentContext
from src.services.agent_service import MessengerAgentService

app = typer.Typer()

# Tone choices for arrow-key selection (copy/paste only for URL and Facebook fields).
TONE_CHOICES = ["Professional", "Friendly", "Casual"]

ACTION_CONTINUE = "Continue to tone & Facebook config"
ACTION_TEST_BOT = "Test the bot"
ACTION_EXIT = "Exit"


def _normalize_website_url(url: str) -> str:
    """Normalize URL for lookup and storage (e.g. strip trailing slash)."""
    if not url or not url.strip():
        return url
    u = url.strip()
    return u.rstrip("/") if u != "https://" and u != "http://" else u


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    """Run setup when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(setup)


def _run_async_with_cleanup(coro):
    """
    Run async coroutine with proper cleanup of event loop and resources.

    Ensures all pending tasks are cancelled and the event loop is properly closed
    even when exceptions occur, preventing resource warnings.
    """
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Handle both coroutines and regular values (for testing with mocks)
        if asyncio.iscoroutine(coro):
            result = loop.run_until_complete(coro)
        else:
            # If it's not a coroutine (e.g., from a mock), return it directly
            result = coro
        return result
    finally:
        if loop is not None:
            try:
                # Cancel all pending tasks that aren't done
                try:
                    if not loop.is_closed():
                        pending = [
                            task for task in asyncio.all_tasks(loop) if not task.done()
                        ]
                        for task in pending:
                            task.cancel()
                        # Wait for cancellation to complete, ignoring exceptions
                        if pending:
                            try:
                                loop.run_until_complete(
                                    asyncio.gather(*pending, return_exceptions=True)
                                )
                            except RuntimeError:
                                # Loop might be in a bad state, continue with cleanup
                                pass
                        # Shutdown async generators to close any open resources (sockets, etc.)
                        try:
                            loop.run_until_complete(loop.shutdown_asyncgens())
                        except RuntimeError:
                            # Loop might be in a bad state, continue with cleanup
                            pass
                except RuntimeError:
                    # Loop might be closing or in bad state, continue with cleanup
                    pass
            finally:
                # Always close the loop and clear the event loop
                try:
                    if not loop.is_closed():
                        loop.close()
                except Exception:
                    # Ignore errors during loop closure
                    pass
                finally:
                    try:
                        asyncio.set_event_loop(None)
                    except Exception:
                        # Ignore errors when clearing event loop
                        pass


def _select_tone(message: str = "Select a tone") -> str:
    """Arrow-key selection for tone. Returns chosen tone string."""
    choice = questionary.select(
        message,
        choices=TONE_CHOICES,
    ).ask()
    if choice is None:
        raise typer.Exit(0)
    return choice


def _run_test_repl(
    ref_doc_content: str,
    tone: str,
    reference_doc_id: str,
    source_url: str,
) -> None:
    """
    Run the test REPL: user types messages, agent responds. No Facebook required.
    Uses placeholder bot_config_id; agent only needs reference_doc and tone.
    Persists exchanges to Supabase (test_sessions / test_messages) when available.
    """
    context = AgentContext(
        bot_config_id="cli-test",
        reference_doc=ref_doc_content,
        tone=tone,
        recent_messages=[],
    )
    agent = MessengerAgentService()
    typer.echo(
        "\nTest the bot (type 'quit' or press Enter with empty message to exit).\n"
    )

    session_id: str | None = None
    try:
        session_id = create_test_session(reference_doc_id, source_url, tone)
        typer.echo(
            f"Session ID: {session_id} — view in Supabase: test_sessions / test_messages\n"
        )
    except Exception:
        session_id = None
        typer.echo(
            "Could not create test session (Supabase unavailable). Conversation will not be persisted.\n",
            err=True,
        )

    recent_messages: list[str] = []

    while True:
        user_message = typer.prompt("You (or 'quit' to exit)")
        if not user_message or user_message.strip().lower() == "quit":
            break
        user_message = user_message.strip()
        # Update context with recent conversation for this session
        context.recent_messages = recent_messages[-6:]  # Last 3 exchanges
        try:
            response = _run_async_with_cleanup(agent.respond(context, user_message))
            typer.echo(f"Bot: {response.message}")
            if response.requires_escalation and response.escalation_reason:
                typer.echo(
                    typer.style(
                        f"  [escalation: {response.escalation_reason}]",
                        fg=typer.colors.YELLOW,
                    )
                )
            recent_messages.append(f"User: {user_message}")
            recent_messages.append(f"Bot: {response.message}")
            if session_id is not None:
                save_test_message(
                    test_session_id=session_id,
                    user_message=user_message,
                    response_text=response.message,
                    confidence=response.confidence,
                    requires_escalation=response.requires_escalation,
                    escalation_reason=response.escalation_reason,
                )
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)
    typer.echo("Exiting test.\n")


def _action_menu() -> str | None:
    """Show post-reference-doc action menu (arrow-key). Returns choice or None if Exit."""
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            questionary.Choice(ACTION_CONTINUE, value=ACTION_CONTINUE),
            questionary.Choice(ACTION_TEST_BOT, value=ACTION_TEST_BOT),
            questionary.Choice(ACTION_EXIT, value=ACTION_EXIT),
        ],
    ).ask()
    return choice


@app.command()
def setup():
    """
    Interactive setup:
    1) Ask for website (copy/paste)
    2) Scrape + build reference doc (or resume using existing doc for this URL)
    3) Action menu: Continue to Facebook config, Test the bot, or Exit
    4) If Continue: select tone (arrows), then Facebook credentials (copy/paste), persist bot
    5) If Test the bot: select tone, then REPL to try the agent (no Facebook needed)

    Only website URL and Facebook credential fields use copy/paste; tone and menus use arrow keys.
    """
    import hashlib

    # Step 1: Website URL (copy/paste)
    website_url = typer.prompt("What website should the bot be based on?")
    normalized_url = _normalize_website_url(website_url)

    ref_doc_content: str
    reference_doc_id: str

    # Check for existing reference document (resume path)
    existing_doc = get_reference_document_by_source_url(normalized_url)
    if existing_doc:
        reference_doc_id = existing_doc["id"]
        ref_doc_content = existing_doc["content"]
        typer.echo(f"✓ Found existing reference document for {normalized_url}")
        typer.echo("  Skipping scrape and document generation.")
    else:
        # Step 2a: Scrape
        typer.echo(f"Scraping {normalized_url}...")
        try:
            text_chunks = _run_async_with_cleanup(scrape_website(normalized_url))
            typer.echo(f"✓ Scraped {len(text_chunks)} text chunks")
        except Exception as e:
            typer.echo(f"✗ Error scraping website: {e}", err=True)
            raise typer.Exit(1)

        # Step 2b: Build reference doc
        typer.echo("Generating reference document via PydanticAI Gateway...")
        try:
            markdown_content = _run_async_with_cleanup(
                build_reference_document(normalized_url, text_chunks)
            )
            content_hash = hashlib.sha256(markdown_content.encode()).hexdigest()
            typer.echo("✓ Reference document generated")
        except Exception as e:
            typer.echo(f"✗ Error generating reference doc: {e}", err=True)
            raise typer.Exit(1)

        # Step 2c: Store reference document immediately (so we can resume later)
        typer.echo("Storing reference document...")
        try:
            reference_doc_id = create_reference_document(
                content=markdown_content,
                source_url=normalized_url,
                content_hash=content_hash,
            )
            typer.echo("✓ Reference document stored")
        except Exception as e:
            typer.echo(f"✗ Error storing reference document: {e}", err=True)
            raise typer.Exit(1)
        ref_doc_content = markdown_content

    # Step 3: Action menu (arrow-key); loop so user can Test then Continue or Exit
    while True:
        action = _action_menu()
        if action is None or action == ACTION_EXIT:
            typer.echo("Exiting. Run setup again with the same URL to continue later.")
            return
        if action == ACTION_TEST_BOT:
            tone = _select_tone("Select a tone for testing")
            _run_test_repl(ref_doc_content, tone, reference_doc_id, normalized_url)
            continue
        # ACTION_CONTINUE
        break

    # Step 4: Tone (arrow-key) then Facebook config (copy/paste)
    tone = _select_tone("Select a tone for your bot")
    page_id = typer.prompt("Facebook Page ID")
    page_access_token = typer.prompt("Facebook Page Access Token")
    verify_token = typer.prompt(
        "Verify Token (for webhook)",
        default=typer.style("random-token-123", fg=typer.colors.YELLOW),
    )

    # Step 5: Create bot configuration
    typer.echo("\nCreating bot configuration...")
    try:
        create_bot_configuration(
            page_id=page_id,
            website_url=normalized_url,
            reference_doc_id=reference_doc_id,
            tone=tone,
            facebook_page_access_token=page_access_token,
            facebook_verify_token=verify_token,
        )
        typer.echo("✓ Bot configuration created")
    except Exception as e:
        typer.echo(f"✗ Error creating bot configuration: {e}", err=True)
        raise typer.Exit(1)

    # Step 6: Print webhook URL
    typer.echo("\n" + "=" * 60)
    typer.echo("✓ Setup complete!")
    typer.echo("\nNext steps:")
    typer.echo("1. Configure webhook URL in Facebook App settings:")
    typer.echo("   https://your-railway-url.railway.app/webhook")
    typer.echo(f"2. Set verify token: {verify_token}")
    typer.echo("3. Subscribe to 'messages' events")
    typer.echo("=" * 60)


@app.command()
def test():
    """
    Test the bot using an existing reference document (no Facebook credentials).
    Paste the website URL; if a reference doc exists for that URL, you can chat with the bot.
    """
    website_url = typer.prompt(
        "Website URL (for which you already have a reference document)"
    )
    normalized_url = _normalize_website_url(website_url)
    existing_doc = get_reference_document_by_source_url(normalized_url)
    if not existing_doc:
        typer.echo(
            "No reference document found for this URL. Run setup first to scrape and generate one.",
            err=True,
        )
        raise typer.Exit(1)
    ref_doc_content = existing_doc["content"]
    reference_doc_id = existing_doc["id"]
    tone = _select_tone("Select a tone for testing")
    _run_test_repl(ref_doc_content, tone, reference_doc_id, normalized_url)


if __name__ == "__main__":
    app()
