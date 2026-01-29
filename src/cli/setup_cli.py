"""Typer-based interactive setup CLI."""

import os

os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")

from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
from dotenv import load_dotenv

load_dotenv(_project_root / ".env")
load_dotenv(_project_root / ".env.local")

import asyncio
import hashlib
import re
import time
from datetime import datetime
from typing import Callable

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


def _validate_page_id(page_id: str) -> bool:
    """Validate Facebook Page ID format."""
    return bool(re.match(r"^\d{15,17}$", page_id.strip()))


def _validate_page_access_token(token: str) -> bool:
    """Validate Page Access Token format."""
    token = token.strip()
    return token.startswith("EAAA") and len(token) > 100


def _validate_verify_token(token: str) -> bool:
    """Validate verify token format."""
    token = token.strip()
    return bool(re.match(r"^[a-zA-Z0-9_-]{8,100}$", token))


def _prompt_with_validation(
    message: str,
    validator: Callable[[str], bool],
    error_message: str,
    hide_input: bool = False,
    max_attempts: int = 3,
) -> str:
    """Prompt user with input validation."""
    for attempt in range(max_attempts):
        value = typer.prompt(message, hide_input=hide_input).strip()
        if validator(value):
            return value
        typer.echo(
            typer.style(f"❌ {error_message}", fg=typer.colors.RED),
            err=True,
        )
        if attempt < max_attempts - 1:
            typer.echo(f"  {max_attempts - attempt - 1} attempts remaining\n")
        else:
            typer.echo("❌ Maximum attempts reached. Exiting.")
            raise typer.Exit(1)
    return value  # unreachable but satisfies type checker


def _show_facebook_credential_help(credential_type: str) -> None:
    """Show detailed help for getting specific Facebook credentials."""
    if credential_type == "page_id":
        typer.echo("─" * 60)
        typer.echo("🎯 How to Find Your Facebook Page ID")
        typer.echo("─" * 60)
        typer.echo("")
        typer.echo("Method 1: From Messenger Settings (Easiest)")
        typer.echo("  1. Go to: https://developers.facebook.com/apps")
        typer.echo("  2. Select your app → Messenger → Settings")
        typer.echo("  3. Look at Access Tokens → Page dropdown")
        typer.echo("  4. Page ID is in parentheses: 'Page Name (123456789012345)'")
        typer.echo("")
        typer.echo("Method 2: From Your Page")
        typer.echo("  1. Go to your Facebook Page")
        typer.echo("  2. Click 'About' → 'Page Transparency'")
        typer.echo("  3. Look for 'Page ID' field")
        typer.echo("")
        typer.echo("─" * 60)
    elif credential_type == "access_token":
        typer.echo("─" * 60)
        typer.echo("🔑 How to Get Page Access Token")
        typer.echo("─" * 60)
        typer.echo("")
        typer.echo("Step-by-Step:")
        typer.echo("  1. Go to: https://developers.facebook.com/apps")
        typer.echo("  2. Select your app (or create one)")
        typer.echo("  3. Add Messenger product (if not added)")
        typer.echo("  4. Go to Messenger → Settings")
        typer.echo("  5. Find 'Access Tokens' section")
        typer.echo("  6. Click 'Add or Remove Pages'")
        typer.echo("  7. Select your page and grant permissions")
        typer.echo("  8. Click 'Generate Token'")
        typer.echo("  9. Copy the token immediately! (Won't show again)")
        typer.echo("")
        typer.echo("⚠️  Token starts with 'EAAA' and is very long (100+ chars)")
        typer.echo("")
        typer.echo("─" * 60)
    elif credential_type == "verify_token":
        typer.echo("─" * 60)
        typer.echo("✅ About Verify Token")
        typer.echo("─" * 60)
        typer.echo("")
        typer.echo("What is it?")
        typer.echo("  A secret string YOU create to secure your webhook.")
        typer.echo("  Facebook sends it back during verification.")
        typer.echo("")
        typer.echo("How to create:")
        typer.echo("  Option 1: Use the default we generate for you")
        typer.echo("  Option 2: Type your own (e.g., 'my-bot-token-2024')")
        typer.echo("  Option 3: Generate random in terminal:")
        typer.echo("            openssl rand -base64 32")
        typer.echo("")
        typer.echo("Rules:")
        typer.echo("  • Letters, numbers, dashes, underscores only")
        typer.echo("  • 8-100 characters")
        typer.echo("  • No spaces or special chars (@#$%)")
        typer.echo("  • SAVE IT - you'll need it for webhook setup!")
        typer.echo("")
        typer.echo("─" * 60)


def _prompt_with_help(
    message: str,
    credential_type: str,
    validator: Callable[[str], bool] | None = None,
    **prompt_kwargs: object,
) -> str:
    """Prompt with optional help dialog (type '?' for detailed help)."""
    if credential_type == "page_id":
        typer.echo("💡 Tip: Page ID is a 15-digit number")
    elif credential_type == "access_token":
        typer.echo("💡 Tip: Token starts with EAAA and is very long")
    elif credential_type == "verify_token":
        typer.echo("💡 Tip: Create any secure string (or use default)")
    typer.echo("   Type '?' for detailed help on where to find this\n")

    while True:
        value = typer.prompt(message, **prompt_kwargs).strip()
        if value == "?":
            _show_facebook_credential_help(credential_type)
            typer.echo("")
            continue
        if validator and not validator(value):
            typer.echo(
                typer.style(
                    "❌ Invalid format. Try again or type '?' for help",
                    fg=typer.colors.RED,
                ),
                err=True,
            )
            continue
        return value


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

    # Show Facebook setup instructions
    typer.echo("\n" + "=" * 60)
    typer.echo("📝 Facebook Credentials Needed")
    typer.echo("=" * 60)
    typer.echo("")
    typer.echo("📖 Need help? See: docs/FACEBOOK_SETUP_QUICK.md")
    typer.echo("")
    typer.echo("📌 Quick Reference:")
    typer.echo("  1. Page ID: Find in Messenger Settings → Access Tokens dropdown")
    typer.echo("     Format: 123456789012345 (15 digits)")
    typer.echo("")
    typer.echo("  2. Page Access Token: Messenger Settings → Generate Token")
    typer.echo("     Format: EAAA... (very long)")
    typer.echo("")
    typer.echo("  3. Verify Token: Any string you create (save it!)")
    typer.echo("     Tip: Use 'openssl rand -base64 32' to generate")
    typer.echo("")
    typer.echo("=" * 60)
    typer.echo("")

    default_verify_token = "fb-verify-" + hashlib.md5(
        str(time.time()).encode()
    ).hexdigest()[:12]

    page_id = _prompt_with_help(
        "🎯 Facebook Page ID (15-digit number)",
        "page_id",
        validator=_validate_page_id,
    )
    page_access_token = _prompt_with_help(
        "🔑 Page Access Token (starts with EAAA...)",
        "access_token",
        validator=_validate_page_access_token,
        hide_input=True,
    )
    verify_token = _prompt_with_help(
        "✅ Verify Token (your choice, or press Enter for random)",
        "verify_token",
        validator=_validate_verify_token,
        default=default_verify_token,
    )

    typer.echo("\n✅ Credentials collected:")
    typer.echo(f"  Page ID: {page_id}")
    typer.echo(
        f"  Token: {page_access_token[:20]}...{page_access_token[-10:] if len(page_access_token) > 30 else ''}"
    )
    typer.echo(f"  Verify Token: {verify_token}")
    typer.echo("")

    if not typer.confirm("❓ Do these look correct?", default=True):
        typer.echo("❌ Aborted. Run setup again to re-enter credentials.")
        raise typer.Exit(1)

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

    # Step 6: Print webhook URL and next steps
    typer.echo("\n" + "=" * 60)
    typer.echo("✅ Setup Complete!")
    typer.echo("=" * 60)
    typer.echo("")
    typer.echo("🚀 Your bot configuration is saved.")
    typer.echo("")
    typer.echo("📖 Next Steps (IMPORTANT):")
    typer.echo("")
    typer.echo("1️⃣  Deploy your app to Railway (or hosting platform)")
    typer.echo("   $ railway up")
    typer.echo("")
    typer.echo("2️⃣  Get your deployment URL from Railway dashboard")
    typer.echo("   Format: https://your-app-name.railway.app")
    typer.echo("")
    typer.echo("3️⃣  Configure Facebook Webhook:")
    typer.echo("   • Go to: https://developers.facebook.com/apps")
    typer.echo("   • Your App → Messenger → Settings → Webhooks")
    typer.echo("   • Click 'Add Callback URL'")
    typer.echo("")
    typer.echo("   Callback URL: https://your-app-name.railway.app/webhook")
    typer.echo(f"   Verify Token: {verify_token}")
    typer.echo("")
    typer.echo("   • Click 'Verify and Save'")
    typer.echo("   • Check 'messages' subscription")
    typer.echo("   • Click 'Subscribe' for your page")
    typer.echo("")
    typer.echo("4️⃣  Test your bot:")
    typer.echo("   • Send a message to your Facebook Page")
    typer.echo("   • The bot should respond automatically")
    typer.echo("")
    typer.echo("📖 Full guide: docs/FACEBOOK_SETUP_QUICK.md")
    typer.echo("🐛 Issues? Check RUNBOOK.md")
    typer.echo("")
    typer.echo("=" * 60)

    webhook_info_path = _project_root / "WEBHOOK_INFO.txt"
    try:
        webhook_info_path.write_text(
            f"""FACEBOOK WEBHOOK CONFIGURATION
================================

Callback URL: https://YOUR-APP-NAME.railway.app/webhook
Verify Token: {verify_token}

Page ID: {page_id}

Webhook Subscriptions:
- messages (required)
- messaging_postbacks (optional)

Setup Instructions:
1. Deploy to Railway
2. Replace YOUR-APP-NAME with your actual Railway URL
3. Add webhook in Facebook Developer Console
4. Subscribe your page to the webhook

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""",
            encoding="utf-8",
        )
        typer.echo(f"💾 Webhook info saved to: {webhook_info_path}")
        typer.echo("")
    except OSError as e:
        typer.echo(
            typer.style(f"⚠️  Could not save WEBHOOK_INFO.txt: {e}", fg=typer.colors.YELLOW),
            err=True,
        )


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
